from django.urls import path
from users.views import SignupView, OTPVerifyView, ResendOTPView, LoginView, ForgotpasswordOTPView, ForgotPasswordOTPVerifyView, ForgotPasswordResetView, ProfileView, ChangePasswordView, LogoutView, GoogleLoginView, FacebookLoginView, UserAddressView, UserAddressDetailView, GuestCheckoutView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-otp/', OTPVerifyView.as_view(), name='verify_otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('guest-checkout/', GuestCheckoutView.as_view(), name='guest_checkout'),
    path('google-auth/', GoogleLoginView.as_view(), name='google_auth'),
    path('facebook-auth/', FacebookLoginView.as_view(), name='facebook_auth'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('forgot-password-otp/', ForgotpasswordOTPView.as_view(), name='forgot_password_otp'),
    path('forgot-password-otp-verify/', ForgotPasswordOTPVerifyView.as_view(), name='forgot_password_otp_verify'),
    path('forgot-password-reset/', ForgotPasswordResetView.as_view(), name='forgot_password_reset'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('addresses/', UserAddressView.as_view(), name='user_addresses'),
    path('addresses/<int:pk>/', UserAddressDetailView.as_view(), name='user_address_detail'),

]