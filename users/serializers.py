from rest_framework import serializers
from users.models import User, OTP, UserAddress
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
import random
from datetime import timedelta
from users.tasks import send_otp_email
from users.firebase import verify_phone_id_token
import requests
from django.core.files.base import ContentFile


def normalize_phone(value):
    """
    Reduce anything the customer might type ('+91 98765 43210', '098765 43210')
    to the bare 10-digit number this project stores, so the same person always
    maps to one account no matter which form they came through.
    """
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return digits[-10:]


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    # Optional proof, from Firebase, that the customer controls the number they
    # typed. Sent by the "Verify" button next to the phone field.
    firebase_id_token = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'password',
            'firebase_id_token'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'validators': []},  # Remove default unique validator
            'phone_number': {'validators': []}  # Remove default unique validator
        }

    def validate_phone_number(self, value):
        phone = normalize_phone(value)
        if len(phone) < 10:
            raise serializers.ValidationError("Enter a valid 10-digit phone number.")
        return phone

    def validate(self, attrs):
        # Check if email already exists
        if User.objects.filter(email=attrs['email'].lower(), is_active=True).exists():
            raise serializers.ValidationError({
                "email": "Email already exists."
            })

        # Check if phone number already exists
        if User.objects.filter(phone_number=attrs['phone_number'], is_active=True).exists():
            raise serializers.ValidationError({
                "phone_number": "Phone number already exists."
            })

        token = (attrs.pop('firebase_id_token', '') or '').strip()
        if token:
            verified = verify_phone_id_token(token)
            if verified['phone_number'] != attrs['phone_number']:
                raise serializers.ValidationError({
                    "phone_number": "Verify the same number you entered above."
                })
            attrs['_verified_phone'] = verified
        elif settings.REQUIRE_PHONE_VERIFICATION_ON_SIGNUP:
            raise serializers.ValidationError({
                "firebase_id_token": "Please verify your phone number to continue."
            })

        return attrs

    def create(self, validated_data):
        verified = validated_data.pop('_verified_phone', None)
        email = validated_data.get('email').lower()
        phone_number = validated_data.get('phone_number')

        try:
            # Check if inactive user exists with same email or phone number
            user = User.objects.get(email=email, is_active=False)
            # Update user details
            for attr, value in validated_data.items():
                setattr(user, attr, value)
            user.set_password(validated_data['password'])
            user.save()
        except User.DoesNotExist:
            user = User.objects.create_user(**validated_data)
            user.is_active = False
            user.save()

        if verified:
            user.phone_verified = True
            if verified['country_code']:
                user.country_code = verified['country_code']
            # Never take the uid off another account. The phone-number check in
            # validate() already rules out that account being the same person,
            # so leaving the uid unset here loses nothing.
            if not User.objects.filter(firebase_uid=verified['uid']).exclude(pk=user.pk).exists():
                user.firebase_uid = verified['uid']
            user.save(update_fields=['firebase_uid', 'country_code', 'phone_verified'])

        # Generate and save OTP
        otp_code = str(random.randint(100000, 999999))
        OTP.objects.update_or_create(
            user=user,
            defaults={
                'otp_code': otp_code,
                'expires_at': timezone.now() + timedelta(minutes=10)
            }
        )

        # Send OTP
        send_otp_email.delay(
            subject="Your OTP Code",
            template_name="email/otp_email.html",
            user_id=user.id,
            otp_code=otp_code,
        )

        return user


class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        user = self._get_user(attrs)
        otp = self._get_valid_otp(user, attrs['otp'])

        attrs['user'] = user
        return attrs

    def _get_user(self, attrs):
        filters = {'email': attrs.get('email')} if attrs.get('email') else {'phone_number': attrs.get('phone_number')}
        user = User.objects.filter(**filters).first()
        if not user:
            raise serializers.ValidationError({
                'email' if 'email' in filters else 'phone_number': "User not found."
            })
        return user

    def _get_valid_otp(self, user, otp_code):
        otp = OTP.objects.filter(user=user, otp_code=otp_code).order_by('-created_at').first()
        if not otp:
            raise serializers.ValidationError({
                'otp': "Invalid OTP."
            })
        if otp.is_expired():
            raise serializers.ValidationError({
                'otp': "OTP has expired."
            })
        return otp

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.is_active = True
        user.email_verified = True
        user.save()
        OTP.objects.filter(user=user).delete()  # Clean up
        return user
    
class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    # phone_number = serializers.CharField(required=False)
    def validate(self, attrs):
        identifier = attrs.get('email')  # or phone_number
        if not identifier:
            raise serializers.ValidationError("Email is required.")
        return attrs
    
    def save(self, **kwargs):
        try:
            user = User.objects.get(email=self.validated_data['email'])
            # otp_code = ''.join(random.choices('0123456789', k=6))
            otp_code = str(random.randint(100000, 999999))
            otp = OTP.objects.create(user=user, otp_code=otp_code, expires_at=timezone.now() + timedelta(minutes=10))
            send_otp_email.delay(
                subject="Your New OTP Code",
                template_name="email/resend_otp_email.html",
                user_id=user.id,
                otp_code=otp_code,
            )
            return otp
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

class UserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number','profile_picture','is_active',
            'country_code', 'phone_verified', 'email_verified'
        ]
        read_only_fields = ['phone_verified', 'email_verified']

    def validate_phone_number(self, value):
        phone = normalize_phone(value)
        if len(phone) < 10:
            raise serializers.ValidationError("Enter a valid 10-digit phone number.")
        if User.objects.filter(phone_number=phone).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("That phone number is already linked to another account.")
        return phone

    def update(self, instance, validated_data):
        # Editing the number by hand is not proof of anything — drop the
        # verified flag and the Firebase link so the customer has to re-verify.
        new_phone = validated_data.get('phone_number')
        if new_phone and new_phone != instance.phone_number:
            instance.phone_verified = False
            instance.firebase_uid = None
        return super().update(instance, validated_data)
        
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, min_length=8)
    
    def create(self, validated_data):
        email = validated_data.get('email').lower()
        password = validated_data.get('password')

        user = User.objects.filter(email=email).first()

        if not user:
            raise serializers.ValidationError({"email": "User not found."})
        
        if not user.check_password(password):
            raise serializers.ValidationError({"password": "Incorrect password."})

        if not user.is_active:
            raise serializers.ValidationError({"message": "Please verify your account to login."})

        return user

    def save(self, **kwargs):
        return self.create(self.validated_data)

class ForgotPasswordOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    # phone_number = serializers.CharField(required=False)
    def validate(self, attrs):
        identifier = attrs.get('email')  # or phone_number
        if not identifier:
            raise serializers.ValidationError({"email":"Email is required."})
        return attrs
    
    def save(self, **kwargs):
        try:
            user = User.objects.get(email=self.validated_data['email'])
            # otp_code = ''.join(random.choices('0123456789', k=6))
            otp_code = str(random.randint(100000, 999999))
            otp = OTP.objects.create(user=user, otp_code=otp_code, expires_at=timezone.now() + timedelta(minutes=10))
            send_otp_email.delay(
                subject="Reset Your Password - OTP Code",
                template_name="email/forgot_password_otp.html",
                user_id=user.id,
                otp_code=otp_code,
            )
            return otp
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")   

class ForgotPasswordOtpVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6)

    def validate(self, attrs):
        user = User.objects.filter(email=attrs['email']).first()
        if not user:
            raise serializers.ValidationError({"email":"User not found."})
        otp = OTP.objects.filter(user=user, otp_code=attrs['otp']).order_by('-created_at').first()
        if not otp:
            raise serializers.ValidationError({
                'otp': "Invalid OTP."
            })
        if otp.is_expired():
            raise serializers.ValidationError({"otp":"OTP has expired."})
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        # Optionally, you can delete the OTP here
        OTP.objects.filter(user=self.validated_data['user']).delete()
        return self.validated_data['user']

class ForgotPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate(self, attrs):
        user = User.objects.filter(email=attrs['email']).first()
        if not user:
            raise serializers.ValidationError({"email":"User not found."})
        
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password":"Passwords do not match."})
        
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['confirm_password'])
        user.save()
        return user
    

class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get('token')
        if not token:
            raise serializers.ValidationError('Token is required.')

        try:
            # Step 1: Call Google UserInfo API using the access token
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code != 200:
                raise serializers.ValidationError("Invalid Google access token")

            user_info = response.json()
            email = user_info.get("email")
            name = user_info.get("name", "")
            google_id = user_info.get("sub")
            picture_url = user_info.get("picture")

            if not email:
                raise serializers.ValidationError("Email not found in token.")

            first_name = name.split()[0] if name else ""
            last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

            # Step 2: Create or get the user
            user, created = User.objects.get_or_create(
                email=email,
                # google_id=google_id,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "google_id": google_id,
                    "is_active": True,
                    "email_verified": True,
                }
            )
            # Update profile image
            if picture_url:
                if created or not user.profile_picture:
                    img_response = requests.get(picture_url)
                    if img_response.status_code == 200:
                        file_name = f"{google_id}.jpg"
                        user.profile_picture.save(file_name, ContentFile(img_response.content), save=True)

            # Step 4: Update google_id if it's missing
            if not created and not user.google_id:
                user.google_id = google_id
                user.is_active = True  # Ensure user is active if they log in with Google
                user.email_verified = True  # Mark email as verified if logging in with Google
                user.save()
            
            attrs["user"] = user
            attrs["is_new_user"] = created  
            return attrs

        except Exception as e:
            raise serializers.ValidationError(f'Invalid token. {str(e)}',)
        except Exception:
            raise serializers.ValidationError('Authentication failed.')
        
class FacebookAuthSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get("token")
        if not token:
            raise serializers.ValidationError("Token is required.")

        try:
            # Step 1: Call Facebook Graph API using the access token
            response = requests.get(
                "https://graph.facebook.com/me",
                params={
                    "fields": "id,name,email,picture",
                    "access_token": token,
                },
            )
            if response.status_code != 200:
                raise serializers.ValidationError("Invalid Facebook access token")


            user_info = response.json()
            fb_id = user_info.get("id")
            email = user_info.get("email")
            name = user_info.get("name", "")
            picture_data = user_info.get("picture", {}).get("data", {})
            picture_url = picture_data.get("url")

            if not email:
                raise serializers.ValidationError("Email not found in token. Please allow email permission.")

            first_name = name.split()[0] if name else ""
            last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

            # Step 2: Create or get the user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "facebook_id": fb_id,
                }
            )

            # Step 3: Save profile picture if available
            if picture_url:
                if created or not user.profile_picture:
                    img_response = requests.get(picture_url)
                    if img_response.status_code == 200:
                        file_name = f"{fb_id}.jpg"
                        user.profile_picture.save(file_name, ContentFile(img_response.content), save=True)

            # Step 4: Update facebook_id if missing
            if not created and not user.facebook_id:
                user.facebook_id = fb_id
                user.is_active = True  # Ensure user is active if they log in with Facebook

            attrs["user"] = user
            attrs["is_new_user"] = created
            return attrs

        except Exception as e:
            raise serializers.ValidationError(f"Invalid token. {str(e)}")

    
class FirebasePhoneAuthSerializer(serializers.Serializer):
    """
    Sign in with a phone number that Firebase has already verified over SMS.

    Mirrors the Google/Facebook serializers: verify the provider's token, find
    or create the matching account, and hand the view a user to mint JWTs for.
    An unrecognised number creates a phone-only account — no email, no usable
    password — which the customer can fill in later from their profile.
    """
    firebase_id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        verified = verify_phone_id_token(attrs.get('firebase_id_token'))
        uid = verified['uid']
        phone = verified['phone_number']

        # Match on the Firebase account first, then fall back to the number so
        # accounts created by signup or guest checkout are picked up too.
        user = User.objects.filter(firebase_uid=uid).first()
        created = False
        if user is None:
            user = User.objects.filter(
                Q(phone_number=phone) | Q(phone_number=verified['e164'])
            ).first()

        if user is None:
            try:
                with transaction.atomic():
                    user = User.objects.create(
                        phone_number=phone,
                        country_code=verified['country_code'] or None,
                        firebase_uid=uid,
                        phone_verified=True,
                        is_active=True,
                    )
                    # No password is ever valid here until the customer sets one
                    # through the normal forgot-password flow.
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                created = True
            except IntegrityError:
                # Two taps landing at once — the other one won, so use its row.
                user = User.objects.filter(
                    Q(firebase_uid=uid) | Q(phone_number=phone)
                ).first()
                if user is None:
                    raise serializers.ValidationError({
                        'firebase_id_token': 'Could not sign in with that number. '
                                             'Please try again.'
                    })
        else:
            updates = []
            if not user.firebase_uid:
                user.firebase_uid = uid
                updates.append('firebase_uid')
            if user.phone_number != phone:
                user.phone_number = phone
                updates.append('phone_number')
            if verified['country_code'] and user.country_code != verified['country_code']:
                user.country_code = verified['country_code']
                updates.append('country_code')
            if not user.phone_verified:
                user.phone_verified = True
                updates.append('phone_verified')
            if not user.is_active:
                # They proved they own the number, which is as good as the
                # email OTP this account never completed.
                user.is_active = True
                updates.append('is_active')
            if updates:
                user.save(update_fields=updates)

        attrs['user'] = user
        attrs['is_new_user'] = created
        return attrs


class PhoneVerifySerializer(serializers.Serializer):
    """
    Attach a Firebase-verified number to the account that is already signed in.

    Used from the profile page, and by anyone finishing the phone step after
    signing up with an email address.
    """
    firebase_id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        verified = verify_phone_id_token(attrs.get('firebase_id_token'))

        clash = User.objects.filter(
            Q(phone_number=verified['phone_number']) | Q(firebase_uid=verified['uid'])
        ).exclude(pk=user.pk)
        if clash.exists():
            raise serializers.ValidationError({
                'firebase_id_token': 'That number is already linked to another account.'
            })

        attrs['verified'] = verified
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        verified = self.validated_data['verified']

        user.phone_number = verified['phone_number']
        user.country_code = verified['country_code'] or user.country_code
        user.firebase_uid = verified['uid']
        user.phone_verified = True
        user.save(update_fields=[
            'phone_number', 'country_code', 'firebase_uid', 'phone_verified'
        ])
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True)

    
    def create(self, validated_data):
        user = self.context['request'].user
        if not user.check_password(validated_data['old_password']):
            raise serializers.ValidationError("Incorrect old password.")
        if validated_data['new_password'] != validated_data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        user.set_password(validated_data['new_password'])
        user.is_active = True
        user.save()
        return user
    
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = [
            'id', 'user', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country', 'is_default'
        ]
        read_only_fields = ['user']

class GuestCheckoutSerializer(serializers.Serializer):
    """
    Details collected on the checkout page when nobody is signed in.

    Enough to create the order and reach the customer about it — no password,
    no OTP, no signup detour.
    """
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=18)

    address_line1 = serializers.CharField(max_length=255)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=100, required=False, default='India')

    # Optional proof from Firebase that the customer controls the number they
    # typed, so the order actually reaches a reachable phone.
    firebase_id_token = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone_number(self, value):
        # Store the last 10 digits so the same person always maps to one account
        digits = normalize_phone(value)
        if len(digits) < 10:
            raise serializers.ValidationError("Enter a valid phone number.")
        return digits

    def validate(self, attrs):
        token = (attrs.pop('firebase_id_token', '') or '').strip()
        if token:
            verified = verify_phone_id_token(token)
            # Trust the number Firebase proved over the one typed in the form.
            attrs['phone_number'] = verified['phone_number']
            attrs['country_code'] = verified['country_code']
            attrs['firebase_uid'] = verified['uid']
            attrs['phone_verified'] = True
        elif settings.REQUIRE_PHONE_VERIFICATION_ON_GUEST_CHECKOUT:
            raise serializers.ValidationError({
                'firebase_id_token': 'Please verify your phone number to continue.'
            })
        else:
            attrs['phone_verified'] = False
        return attrs
