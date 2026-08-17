from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from users.models import User, UserAddress
from users.serializers import FacebookAuthSerializer, LogoutSerializer, SignupSerializer, OTPVerificationSerializer, ResendOTPSerializer, UserDetailsSerializer, LoginSerializer, ForgotPasswordOTPSerializer, ForgotPasswordOtpVerifySerializer, ForgotPasswordResetSerializer, GoogleAuthSerializer, ChangePasswordSerializer, UserAddressSerializer, GuestCheckoutSerializer, FirebasePhoneAuthSerializer, PhoneVerifySerializer
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError, AccessToken
from django.db import transaction, IntegrityError
from django.db.models import Q
from users.tasks import send_welcome_email

class SignupView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User created. OTP sent to your email."}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ResendOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ResendOTPSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            otp = serializer.save()
            return Response({"message": "OTP resent to your email."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OTPVerifyView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = OTPVerificationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            transaction.on_commit(lambda: send_welcome_email.delay(user.id))
            user_data = SignupSerializer(user).data
            user_data["refresh"] = str(refresh)
            user_data["access"] = str(refresh.access_token)
            user_data['message'] = "OTP verified. Your account is now active."
            return Response(user_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            user_data = UserDetailsSerializer(user, context={'request': request}).data
            user_data["refresh"] = str(refresh)
            user_data["access"] = str(refresh.access_token)
            user_data['message'] = "Login successful. Welcome back!"
            return Response(user_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ForgotpasswordOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordOTPSerializer
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset OTP sent to your email."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordOTPVerifyView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordOtpVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            otp = serializer.save()
            return Response({"message": "OTP verified. You can reset your password."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ForgotPasswordResetView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordResetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successful. You can login with your new password."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(GenericAPIView):
    """
    Google Login View
    """
    serializer_class = GoogleAuthSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        is_new_user = serializer.validated_data['is_new_user']  # 🔑 get flag
        refresh = RefreshToken.for_user(user)

        user_data = UserDetailsSerializer(user, context={'request': request}).data
        user_data["refresh"] = str(refresh)
        user_data["access"] = str(refresh.access_token)
        user_data["is_new_user"] = is_new_user  # ✅ add in response
        user_data["message"] = (
            "Signup successful. Welcome!" if is_new_user
            else "Login successful. Welcome back!"
        )
        if is_new_user:
            transaction.on_commit(lambda: send_welcome_email.delay(user.id))

        return Response(user_data, status=status.HTTP_200_OK)


class FacebookLoginView(GenericAPIView):
    """
    Facebook Login View
    """
    serializer_class = FacebookAuthSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        is_new_user = serializer.validated_data['is_new_user']
        refresh = RefreshToken.for_user(user)

        user_data = UserDetailsSerializer(user, context={'request': request}).data
        user_data["refresh"] = str(refresh)
        user_data["access"] = str(refresh.access_token)
        user_data["is_new_user"] = is_new_user
        user_data["message"] = (
            "Signup successful. Welcome!" if is_new_user
            else "Login successful. Welcome back!"
        )
        if is_new_user:
            transaction.on_commit(lambda: send_welcome_email.delay(user.id))

        return Response(user_data, status=status.HTTP_200_OK)


class FirebasePhoneAuthView(GenericAPIView):
    """
    Sign in with a phone number verified through Firebase.

    POST /api/v1/user/firebase-phone-auth/  {"firebase_id_token": "..."}

    The browser runs the SMS round trip with the Firebase JS SDK; this endpoint
    only ever sees the resulting ID token. An unknown number creates a
    phone-only account and signs it straight in, the same way Google login does.
    """
    serializer_class = FirebasePhoneAuthSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        is_new_user = serializer.validated_data['is_new_user']
        refresh = RefreshToken.for_user(user)

        user_data = UserDetailsSerializer(user, context={'request': request}).data
        user_data["refresh"] = str(refresh)
        user_data["access"] = str(refresh.access_token)
        user_data["is_new_user"] = is_new_user
        user_data["message"] = (
            "Signup successful. Welcome!" if is_new_user
            else "Login successful. Welcome back!"
        )
        # Only mail a welcome when we actually have somewhere to send it —
        # phone-only signups have no email address yet.
        if is_new_user and user.email:
            transaction.on_commit(lambda: send_welcome_email.delay(user.id))

        return Response(user_data, status=status.HTTP_200_OK)


class PhoneVerifyView(GenericAPIView):
    """
    Attach a Firebase-verified phone number to the signed-in account.

    POST /api/v1/user/verify-phone/  {"firebase_id_token": "..."}
    """
    serializer_class = PhoneVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "message": "Phone number verified.",
            "user": UserDetailsSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)


class ProfileView(GenericAPIView):

    serializer_class = UserDetailsSerializer

    def patch(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ChangePasswordView(GenericAPIView):
    """
    View for changing the password of the authenticated user.
    """
    serializer_class = ChangePasswordSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LogoutView(GenericAPIView):
    """
    View for logging out the authenticated user.
    """
    serializer_class = LogoutSerializer
    permission_classes = [AllowAny]
    def post(self, request):
        try:
            refresh_token = request.data['refresh']

            # Blacklist refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logout successful."}, status=status.HTTP_205_RESET_CONTENT)
        except KeyError:
            return Response({"error": "Refresh token required."}, status=status.HTTP_400_BAD_REQUEST)
        except TokenError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
class UserAddressView(GenericAPIView):
    serializer_class = UserAddressSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        addresses = user.addresses.all()
        serializer = self.get_serializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserAddressDetailView(GenericAPIView):
    serializer_class = UserAddressSerializer

    def patch(self, request, pk, *args, **kwargs):
        user = request.user
        try:
            address = user.addresses.get(pk=pk)
            serializer = self.get_serializer(address, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserAddress.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk, *args, **kwargs):
        user = request.user
        try:
            address = user.addresses.get(pk=pk)
            address.delete()
            return Response({"message": "Address deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
        except UserAddress.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)


class GuestCheckoutView(GenericAPIView):
    """
    Start a checkout without signing in.

    POST /api/v1/user/guest-checkout/

    Creates (or reuses) a lightweight guest account from the contact details
    typed at checkout, saves the delivery address, and returns JWT tokens so
    the rest of the normal checkout flow works unchanged.

    Security: an email/phone alone is NOT proof of identity, so this only ever
    signs in accounts that are themselves guests. If the details match a real
    registered account, we refuse and ask the customer to log in — otherwise
    anyone could take over an account by typing its email address.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = GuestCheckoutSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email']
        phone = data['phone_number']
        phone_verified = data.get('phone_verified', False)
        firebase_uid = data.get('firebase_uid')
        # Never take a uid off another account — it would break that customer's
        # phone login. Without it the number still matches on its own.
        if firebase_uid and User.objects.filter(firebase_uid=firebase_uid).exclude(
            Q(email__iexact=email) | Q(phone_number=phone)
        ).exists():
            firebase_uid = None

        existing = User.objects.filter(Q(email__iexact=email) | Q(phone_number=phone)).first()

        if existing and not existing.is_guest:
            return Response({
                'success': False,
                'code': 'account_exists',
                'error': 'You already have an account with these details. '
                         'Please sign in to continue.',
            }, status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                if existing:
                    user = existing
                    user.first_name = data['first_name']
                    user.last_name = data.get('last_name', '')
                    user.email = email
                    user.phone_number = phone
                    update_fields = [
                        'first_name', 'last_name', 'email', 'phone_number'
                    ]
                    # Only ever add verification, never take it away — a guest
                    # who skipped the OTP this time may have verified before.
                    if phone_verified:
                        user.phone_verified = True
                        user.country_code = data.get('country_code') or user.country_code
                        update_fields += ['phone_verified', 'country_code']
                        if firebase_uid and not user.firebase_uid:
                            user.firebase_uid = firebase_uid
                            update_fields.append('firebase_uid')
                    user.save(update_fields=update_fields)
                else:
                    user = User.objects.create(
                        email=email,
                        phone_number=phone,
                        first_name=data['first_name'],
                        last_name=data.get('last_name', ''),
                        is_guest=True,
                        is_active=True,
                        phone_verified=phone_verified,
                        country_code=data.get('country_code') or None,
                        firebase_uid=firebase_uid if phone_verified else None,
                    )
                    # No password is ever valid for this account until the
                    # customer sets one via the normal forgot-password flow.
                    user.set_unusable_password()
                    user.save(update_fields=['password'])

                address_fields = {
                    'address_line1': data['address_line1'],
                    'address_line2': data.get('address_line2', ''),
                    'city': data['city'],
                    'state': data['state'],
                    'postal_code': data['postal_code'],
                    'country': data.get('country') or 'India',
                }
                address, _created = UserAddress.objects.get_or_create(
                    user=user, **address_fields, defaults={'is_default': True}
                )
                if not address.is_default:
                    user.addresses.exclude(pk=address.pk).update(is_default=False)
                    address.is_default = True
                    address.save(update_fields=['is_default'])
        except IntegrityError:
            return Response({
                'success': False,
                'error': 'Could not start checkout with these details. '
                         'Please check your email and phone number.',
            }, status=status.HTTP_400_BAD_REQUEST)

        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'address_id': address.id,
            'is_guest': user.is_guest,
            'user': {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone_number': user.phone_number,
                'phone_verified': user.phone_verified,
            },
        }, status=status.HTTP_200_OK)
