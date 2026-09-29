from rest_framework import serializers
from users.models import User, OTP, UserAddress
from users.tasks import send_otp_email
import requests
from django.core.files.base import ContentFile

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'password'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'validators': []},  # Remove default unique validator
            'phone_number': {'validators': []}  # Remove default unique validator
        }
    
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
        
        return attrs
    
    def create(self, validated_data):
        # Signup no longer waits on an emailed OTP: customers were dropping off
        # when the mail arrived late or went to spam. The account is active at
        # once and the email can be verified later from the profile page.
        email = validated_data['email'] = validated_data['email'].lower()
        phone_number = validated_data.get('phone_number')

        # Inactive, unverified rows are signups abandoned at the old OTP step.
        # Reuse the one holding this email, and release this phone number from
        # any other, or the unique constraint on phone_number rejects the retry
        # of someone who first typed a wrong email.
        abandoned = User.objects.filter(is_active=False, email_verified=False)
        user = abandoned.filter(email=email).first()
        if phone_number:
            stale_phone_holders = abandoned.filter(phone_number=phone_number)
            if user:
                stale_phone_holders = stale_phone_holders.exclude(pk=user.pk)
            stale_phone_holders.update(phone_number=None)

        if user:
            for attr, value in validated_data.items():
                setattr(user, attr, value)
            user.set_password(validated_data['password'])
            user.is_active = True
            user.save()
        else:
            user = User.objects.create_user(**validated_data, is_active=True)

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

    # This endpoint signs the user in, so an uncapped 6-digit code could be
    # brute-forced into anyone's account.
    MAX_ATTEMPTS = 5

    def _get_valid_otp(self, user, otp_code):
        live = OTP.objects.filter(user=user).order_by('-created_at').first()
        if live is not None and live.attempt_count >= self.MAX_ATTEMPTS:
            raise serializers.ValidationError({'otp': "Too many wrong attempts. Please request a new OTP."})
        otp = OTP.objects.filter(user=user, otp_code=otp_code).order_by('-created_at').first()
        if not otp:
            OTP.record_failed_attempt(user)
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
            otp = OTP.issue_for(user)
            send_otp_email.delay(
                subject="Your New OTP Code",
                template_name="email/resend_otp_email.html",
                user_id=user.id,
                otp_code=otp.otp_code,
            )
            return otp
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

class UserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone_number','profile_picture','is_active',
            'email_verified', 'phone_verified',
        ]
        # This serializer also backs the profile PATCH. Without these a
        # customer could mark their own email verified, or change the email
        # and keep the verified flag from the old address.
        read_only_fields = ['is_active', 'email_verified', 'phone_verified']

    def validate_email(self, value):
        value = (value or '').strip().lower() or None
        if value and User.objects.filter(email__iexact=value).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def update(self, instance, validated_data):
        from users.phone_otp import normalize_phone

        # An email can be added to an account that has none (OTP sign-up
        # leaves it optional), but not changed once set: it is what password
        # login and order mail go to, and it may already be verified.
        if instance.email:
            validated_data.pop('email', None)

        # Verification belongs to the number, not the account. A new number
        # has to be proved again before it can place a COD order.
        if 'phone_number' in validated_data and (
            normalize_phone(validated_data['phone_number']) != normalize_phone(instance.phone_number)
        ):
            instance.phone_verified = False
        return super().update(instance, validated_data)


class EmailVerificationOTPSerializer(serializers.Serializer):
    """Check a code sent to the signed-in user's email from the profile page."""
    otp = serializers.CharField(min_length=6, max_length=6)

    # A 6-digit code has a million values; without a cap it can be guessed.
    MAX_ATTEMPTS = 5

    def validate(self, attrs):
        user = self.context['request'].user
        otp = OTP.objects.filter(user=user).order_by('-created_at').first()
        if not otp or otp.is_expired():
            raise serializers.ValidationError({'otp': "OTP has expired. Please request a new one."})
        if otp.attempt_count >= self.MAX_ATTEMPTS:
            raise serializers.ValidationError({'otp': "Too many wrong attempts. Please request a new OTP."})
        if otp.otp_code != attrs['otp']:
            OTP.record_failed_attempt(user)
            raise serializers.ValidationError({'otp': "Invalid OTP."})
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        OTP.objects.filter(user=user).delete()
        return user

class LoginSerializer(serializers.Serializer):
    # Email or mobile number. The key stays "email" so older frontends keep
    # working; accounts made with OTP login may have no email at all.
    email = serializers.CharField(required=True)
    password = serializers.CharField(required=True, min_length=8)

    def create(self, validated_data):
        from users.phone_otp import normalize_phone, users_with_phone

        identifier = validated_data.get('email').strip()
        password = validated_data.get('password')

        if '@' in identifier:
            user = User.objects.filter(email=identifier.lower()).first()
        else:
            # Real accounts before guest ones, which have no password anyway.
            user = users_with_phone(normalize_phone(identifier)).order_by('is_guest', '-date_joined').first()

        if not user:
            raise serializers.ValidationError({"email": "User not found."})
        
        if not user.check_password(password):
            raise serializers.ValidationError({"password": "Incorrect password."})

        if not user.is_active:
            # Signups left at the old email-OTP step were never activated.
            # Signup no longer needs the OTP, so let them in now that they have
            # proved the password; they can verify the email from the profile.
            if user.email_verified:
                raise serializers.ValidationError({"message": "This account is disabled. Please contact support."})
            user.is_active = True
            user.save(update_fields=['is_active'])

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
            user = User.objects.get(email__iexact=self.validated_data['email'])
            otp = OTP.issue_for(user)
            send_otp_email.delay(
                subject="Reset Your Password - OTP Code",
                template_name="email/forgot_password_otp.html",
                user_id=user.id,
                otp_code=otp.otp_code,
            )
            return otp
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")   

class ForgotPasswordOtpVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True, min_length=6)

    # A 6-digit code has a million values; without a cap it can be guessed.
    MAX_ATTEMPTS = 5

    def validate(self, attrs):
        user = User.objects.filter(email__iexact=attrs['email']).first()
        if not user:
            raise serializers.ValidationError({"email":"User not found."})
        live = OTP.objects.filter(user=user).order_by('-created_at').first()
        if live is None or live.is_expired():
            raise serializers.ValidationError({"otp": "OTP has expired. Please request a new one."})
        if live.attempt_count >= self.MAX_ATTEMPTS:
            raise serializers.ValidationError({"otp": "Too many wrong attempts. Please request a new OTP."})
        if live.otp_code != attrs['otp']:
            OTP.record_failed_attempt(user)
            raise serializers.ValidationError({'otp': "Invalid OTP."})
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        OTP.objects.filter(user=user).delete()
        # The code reached this inbox, so the address is proven.
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        return user


class ForgotPasswordResetSerializer(serializers.Serializer):
    """
    Set the new password with the token handed out once the OTP checked out.

    This used to take just an email, so anyone could reset anyone's password
    without ever seeing an OTP. Django's reset token is tied to the current
    password hash, so it stops working the moment the password is changed:
    one reset per verified OTP.
    """
    uid = serializers.IntegerField()
    token = serializers.CharField()
    password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate(self, attrs):
        from django.contrib.auth.tokens import default_token_generator

        user = User.objects.filter(pk=attrs['uid']).first()
        if user is None or not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "This reset session has expired. Please start again."})
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password":"Passwords do not match."})
        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['confirm_password'])
        # A guest account turns into a real one once it has a password.
        user.is_guest = False
        user.save(update_fields=['password', 'is_guest'])
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

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone_number(self, value):
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) < 10:
            raise serializers.ValidationError("Enter a valid phone number.")
        # Store the last 10 digits so the same person always maps to one account
        return digits[-10:]
