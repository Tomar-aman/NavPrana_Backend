from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta
from django.utils import timezone
from users.models import User, UserAddress, OTP, PhoneOTP
from users import phone_otp
from rest_framework import serializers
from users.serializers import FacebookAuthSerializer, LogoutSerializer, SignupSerializer, OTPVerificationSerializer, ResendOTPSerializer, UserDetailsSerializer, LoginSerializer, ForgotPasswordOTPSerializer, ForgotPasswordOtpVerifySerializer, ForgotPasswordResetSerializer, GoogleAuthSerializer, ChangePasswordSerializer, UserAddressSerializer, GuestCheckoutSerializer, EmailVerificationOTPSerializer
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError, AccessToken
from django.db import transaction, IntegrityError
from django.db.models import Q
from users.tasks import send_welcome_email, send_otp_email

class SignupView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SignupSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            transaction.on_commit(lambda: send_welcome_email.delay(user.id))
            user_data = UserDetailsSerializer(user, context={'request': request}).data
            user_data["refresh"] = str(refresh)
            user_data["access"] = str(refresh.access_token)
            user_data['message'] = "Account created. Welcome to NavPrana!"
            return Response(user_data, status=status.HTTP_201_CREATED)

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
    

def _account_for_phone(phone):
    """The account a reset for ``phone`` applies to. Guests count: setting a
    password is how a guest account becomes a real one."""
    return phone_otp.users_with_phone(phone).order_by('is_guest', '-date_joined').first()


class ForgotpasswordOTPView(GenericAPIView):
    """
    POST /api/v1/user/forgot-password-otp/
         {"email": "…"}          → code by email
         {"phone_number": "…"}   → code on WhatsApp
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ForgotPasswordOTPSerializer

    def post(self, request, *args, **kwargs):
        if request.data.get('phone_number'):
            try:
                phone = phone_otp.clean_mobile(request.data['phone_number'])
                # Checked before sending so no paid WhatsApp message goes to a
                # number that has no account to reset.
                if _account_for_phone(phone) is None:
                    raise phone_otp.PhoneOTPError(
                        'No account found with this number.', status=404, field='phone_number')
                phone_otp.send(phone, PhoneOTP.RESET, ip=phone_otp.client_ip(request))
            except phone_otp.PhoneOTPError as exc:
                return _otp_error(exc)
            return Response({"message": "OTP sent on your WhatsApp."}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset OTP sent to your email."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordOTPVerifyView(GenericAPIView):
    """
    POST /api/v1/user/forgot-password-otp-verify/
         {"email": "…", "otp": "…"}  or  {"phone_number": "…", "otp": "…"}

    Answers with {"uid", "token"}, which forgot-password-reset/ requires.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ForgotPasswordOtpVerifySerializer

    def post(self, request, *args, **kwargs):
        if request.data.get('phone_number'):
            try:
                phone = phone_otp.clean_mobile(request.data['phone_number'])
                user = _account_for_phone(phone)
                if user is None:
                    raise phone_otp.PhoneOTPError(
                        'No account found with this number.', status=404, field='phone_number')
                phone_otp.check(phone, PhoneOTP.RESET, request.data.get('otp', ''))
            except phone_otp.PhoneOTPError as exc:
                return _otp_error(exc)
            # The code reached this phone, so the number is proven.
            if not user.phone_verified:
                user.phone_verified = True
                user.save(update_fields=['phone_verified'])
        else:
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            user = serializer.save()

        from django.contrib.auth.tokens import default_token_generator

        return Response({
            "message": "OTP verified. You can reset your password.",
            "uid": user.pk,
            "token": default_token_generator.make_token(user),
        }, status=status.HTTP_200_OK)

class ForgotPasswordResetView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
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

class SendEmailVerificationView(GenericAPIView):
    """Email the signed-in user a code to verify their address (profile page)."""

    # Matches the resend countdown on the frontend.
    RESEND_COOLDOWN_SECONDS = 60

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.email_verified:
            return Response({"message": "Email is already verified."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.email:
            return Response({"message": "Add an email address first."}, status=status.HTTP_400_BAD_REQUEST)

        latest = OTP.objects.filter(user=user).order_by('-created_at').first()
        if latest and timezone.now() - latest.created_at < timedelta(seconds=self.RESEND_COOLDOWN_SECONDS):
            return Response(
                {"message": "Please wait a few seconds before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = OTP.issue_for(user)
        send_otp_email.delay(
            subject="Verify your email - NavPrana",
            template_name="email/verify_email_otp.html",
            user_id=user.id,
            otp_code=otp.otp_code,
        )
        return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)


class VerifyEmailView(GenericAPIView):
    serializer_class = EmailVerificationOTPSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user_data = UserDetailsSerializer(user, context={'request': request}).data
            user_data['message'] = "Email verified."
            return Response(user_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
                    user.save(update_fields=[
                        'first_name', 'last_name', 'email', 'phone_number'
                    ])
                else:
                    user = User.objects.create(
                        email=email,
                        phone_number=phone,
                        first_name=data['first_name'],
                        last_name=data.get('last_name', ''),
                        is_guest=True,
                        is_active=True,
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
            },
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# WhatsApp phone OTP
# ---------------------------------------------------------------------------

def _otp_error(exc):
    # Field key for forms, `message` for toasts — the frontend reads either.
    return Response({exc.field: [exc.message], 'message': exc.message}, status=exc.status)


def _auth_response(user, request, message, status_code=status.HTTP_200_OK, **extra):
    refresh = RefreshToken.for_user(user)
    data = UserDetailsSerializer(user, context={'request': request}).data
    data.update(refresh=str(refresh), access=str(refresh.access_token), message=message, **extra)
    return Response(data, status=status_code)


class PhoneVerificationSendView(GenericAPIView):
    """
    Send a WhatsApp code to verify the signed-in user's phone.

    POST /api/v1/user/phone-verification/send/   {"phone_number": "98765…"}  (optional)

    Leaving phone_number out verifies the number already on the account.
    Sending one lets a customer without a number (Google sign-up) or with a
    wrong one fix it at checkout; it is only saved once the code checks out.
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            phone = phone_otp.clean_mobile(request.data.get('phone_number') or user.phone_number)
            if user.phone_verified and phone == phone_otp.normalize_phone(user.phone_number):
                return Response({'message': 'Phone number is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
            if phone_otp.held_by_other_account(phone, user):
                raise phone_otp.PhoneOTPError(
                    'This number is linked to another account. Sign in with it instead.',
                    status=409, field='phone_number',
                )
            phone_otp.send(phone, PhoneOTP.VERIFY, ip=phone_otp.client_ip(request))
        except phone_otp.PhoneOTPError as exc:
            return _otp_error(exc)
        return Response({'message': 'Code sent on WhatsApp.', 'phone_number': phone}, status=status.HTTP_200_OK)


class PhoneVerificationConfirmView(GenericAPIView):
    """
    POST /api/v1/user/phone-verification/verify/   {"phone_number": "…", "otp": "123456"}
    """

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            phone = phone_otp.clean_mobile(request.data.get('phone_number') or user.phone_number)
            if phone_otp.held_by_other_account(phone, user):
                raise phone_otp.PhoneOTPError(
                    'This number is linked to another account. Sign in with it instead.',
                    status=409, field='phone_number',
                )
            phone_otp.check(phone, PhoneOTP.VERIFY, request.data.get('otp', ''))
        except phone_otp.PhoneOTPError as exc:
            return _otp_error(exc)

        try:
            with transaction.atomic():
                phone_otp.release_from_others(phone, user)
                user.phone_number = phone
                user.phone_verified = True
                # A guest who proves their number becomes a real account they
                # can sign in to with OTP. It also closes a gap: guest checkout
                # signs guests in from a typed phone alone, so a guest account
                # must never carry a verified number someone else could reuse.
                user.is_guest = False
                user.save(update_fields=['phone_number', 'phone_verified', 'is_guest'])
        except IntegrityError:
            return Response(
                {'phone_number': ['This number is linked to another account.'],
                 'message': 'This number is linked to another account.'},
                status=status.HTTP_409_CONFLICT,
            )

        data = UserDetailsSerializer(user, context={'request': request}).data
        data['message'] = 'Phone number verified.'
        return Response(data, status=status.HTTP_200_OK)


class OTPLoginSendView(GenericAPIView):
    """
    POST /api/v1/user/otp-login/send/   {"phone_number": "98765…"}

    Works whether or not the number has an account, so the response never
    reveals which numbers are registered.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        try:
            phone = phone_otp.clean_mobile(request.data.get('phone_number'))
            phone_otp.send(phone, PhoneOTP.LOGIN, ip=phone_otp.client_ip(request))
        except phone_otp.PhoneOTPError as exc:
            return _otp_error(exc)
        return Response({'message': 'Code sent on WhatsApp.', 'phone_number': phone}, status=status.HTTP_200_OK)


class OTPLoginVerifyView(GenericAPIView):
    """
    POST /api/v1/user/otp-login/verify/
         {"phone_number": "…", "otp": "123456",
          "first_name": "…", "last_name": "…", "email": "…"}   <- new numbers only

    A number with an account signs straight in. A new number gets
    {"needs_details": true} first (the code is checked but not used up), and
    the account is created when the same code comes back with a name. Email is
    optional: without one the customer simply gets no order mail.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        code = request.data.get('otp', '')
        try:
            phone = phone_otp.clean_mobile(request.data.get('phone_number'))
            # A real account wins over a guest one holding the same number.
            user = phone_otp.users_with_phone(phone).order_by('is_guest', '-date_joined').first()

            if user is not None:
                phone_otp.check(phone, PhoneOTP.LOGIN, code)
                return self._sign_in(request, user)

            first_name = str(request.data.get('first_name') or '').strip()
            email = str(request.data.get('email') or '').strip().lower()
            if not first_name:
                phone_otp.check(phone, PhoneOTP.LOGIN, code, consume=False)
                return Response({'needs_details': True}, status=status.HTTP_200_OK)

            if email:
                try:
                    email = serializers.EmailField().run_validation(email)
                except serializers.ValidationError:
                    return Response({'email': ['Enter a valid email address.']}, status=status.HTTP_400_BAD_REQUEST)
                if User.objects.filter(email__iexact=email).exists():
                    return Response(
                        {'email': ['This email is already registered. Sign in with your password, or use another email.']},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            phone_otp.check(phone, PhoneOTP.LOGIN, code)
        except phone_otp.PhoneOTPError as exc:
            return _otp_error(exc)

        try:
            # Built directly: UserManager.create_user insists on an email.
            user = User(
                email=email or None,  # NULL, not "", so many email-less rows fit the unique index
                first_name=first_name[:150],
                last_name=str(request.data.get('last_name') or '').strip()[:150],
                phone_number=phone,
                is_active=True,
                phone_verified=True,
            )
            user.set_unusable_password()  # signs in with OTP, or sets a password later
            user.save()
        except IntegrityError:
            return Response({'message': 'Could not create the account. Please try again.'}, status=status.HTTP_400_BAD_REQUEST)
        transaction.on_commit(lambda: send_welcome_email.delay(user.id))
        return _auth_response(user, request, 'Account created. Welcome to NavPrana!',
                              status.HTTP_201_CREATED, is_new_user=True)

    def _sign_in(self, request, user):
        # Same rule as password login: an unverified inactive row is a signup
        # abandoned at the old email-OTP step; a verified one was disabled.
        if not user.is_active and user.email_verified:
            return Response({'message': 'This account is disabled. Please contact support.'}, status=status.HTTP_403_FORBIDDEN)
        user.is_active = True
        user.phone_verified = True
        user.is_guest = False
        user.save(update_fields=['is_active', 'phone_verified', 'is_guest'])
        return _auth_response(user, request, 'Login successful. Welcome back!', is_new_user=False)
