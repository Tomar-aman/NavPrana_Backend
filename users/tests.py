from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User, OTP


SIGNUP = {
    'first_name': 'Asha',
    'last_name': 'Rao',
    'email': 'Asha@Example.com',
    'phone_number': '9876543210',
    'password': 'strongpass1',
}


@mock.patch('users.views.send_welcome_email.delay')
class SignupWithoutOTPTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_activates_account_and_returns_tokens(self, _welcome):
        res = self.client.post('/api/v1/user/signup/', SIGNUP, format='json')

        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data)
        self.assertFalse(res.data['email_verified'])
        user = User.objects.get(email='asha@example.com')
        self.assertTrue(user.is_active)
        self.assertFalse(OTP.objects.filter(user=user).exists())

    def test_signup_reuses_abandoned_row_and_frees_its_phone(self, _welcome):
        # Someone typed a wrong email at the old OTP step and never finished.
        User.objects.create_user(email='typo@example.com', password='x' * 8, phone_number='9876543210')

        res = self.client.post('/api/v1/user/signup/', SIGNUP, format='json')

        self.assertEqual(res.status_code, 201)
        self.assertTrue(User.objects.get(email='asha@example.com').is_active)
        self.assertIsNone(User.objects.get(email='typo@example.com').phone_number)

    def test_abandoned_signup_can_log_in(self, _welcome):
        User.objects.create_user(email='old@example.com', password='strongpass1')

        res = self.client.post('/api/v1/user/login/', {'email': 'old@example.com', 'password': 'strongpass1'}, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(User.objects.get(email='old@example.com').is_active)

    def test_disabled_verified_account_still_blocked(self, _welcome):
        User.objects.create_user(email='banned@example.com', password='strongpass1', email_verified=True)

        res = self.client.post('/api/v1/user/login/', {'email': 'banned@example.com', 'password': 'strongpass1'}, format='json')

        self.assertEqual(res.status_code, 400)


@mock.patch('users.views.send_otp_email.delay')
class ProfileEmailVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='asha@example.com', password='strongpass1', is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_send_then_verify(self, send):
        self.assertEqual(self.client.post('/api/v1/user/email-verification/send/').status_code, 200)
        send.assert_called_once()
        code = OTP.objects.get(user=self.user).otp_code

        res = self.client.post('/api/v1/user/email-verification/verify/', {'otp': code}, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_verified'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_resend_cooldown(self, _send):
        self.client.post('/api/v1/user/email-verification/send/')
        self.assertEqual(self.client.post('/api/v1/user/email-verification/send/').status_code, 429)

    def test_wrong_codes_are_capped(self, _send):
        self.client.post('/api/v1/user/email-verification/send/')
        code = OTP.objects.get(user=self.user).otp_code
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.client.post('/api/v1/user/email-verification/verify/', {'otp': wrong}, format='json')

        res = self.client.post('/api/v1/user/email-verification/verify/', {'otp': code}, format='json')

        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_profile_patch_cannot_self_verify(self, _send):
        self.client.patch('/api/v1/user/profile/', {'email_verified': True, 'email': 'x@example.com'}, format='json')

        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)
        self.assertEqual(self.user.email, 'asha@example.com')
