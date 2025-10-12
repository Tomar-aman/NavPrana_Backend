from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from users.serializers import FacebookAuthSerializer, LogoutSerializer, SignupSerializer, OTPVerificationSerializer, ResendOTPSerializer, UserDetailsSerializer, LoginSerializer, ForgotPasswordOTPSerializer, ForgotPasswordOtpVerifySerializer, ForgotPasswordResetSerializer, GoogleAuthSerializer, ChangePasswordSerializer
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, TokenError, AccessToken

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