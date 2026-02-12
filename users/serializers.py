from rest_framework import serializers
from users.models import User, OTP, UserAddress
from django.utils import timezone
import random
from datetime import timedelta
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
            'id', 'first_name', 'last_name', 'email', 'phone_number','profile_picture','is_active'
        ]
        
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