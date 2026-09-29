from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import PhoneOTP, User
from whatsapp.client import WhatsAppError

LOGIN_SEND = '/api/v1/user/otp-login/send/'
LOGIN_VERIFY = '/api/v1/user/otp-login/verify/'
PHONE_SEND = '/api/v1/user/phone-verification/send/'
PHONE_VERIFY = '/api/v1/user/phone-verification/verify/'
CREATE_ORDER = '/api/v1/transaction/cashfree/create-order/'


class SentCodes:
    """Stands in for the WhatsApp send and remembers the last code."""

    def __init__(self):
        self.last = None
        self.to = None

    def __call__(self, to, code):
        self.to, self.last = to, code
        return 'wamid.test'


@override_settings(WHATSAPP_ACCESS_TOKEN='test-token')
class PhoneOTPTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.sent = SentCodes()
        patcher = mock.patch('whatsapp.client.send_otp_template', side_effect=self.sent)
        self.send_mock = patcher.start()
        self.addCleanup(patcher.stop)
        welcome = mock.patch('users.views.send_welcome_email.delay')
        welcome.start()
        self.addCleanup(welcome.stop)


class OTPLoginTests(PhoneOTPTestCase):
    def test_new_number_asks_for_details_then_creates_account(self):
        self.assertEqual(self.client.post(LOGIN_SEND, {'phone_number': '+91 98765 43210'}, format='json').status_code, 200)
        self.assertEqual(self.sent.to, '919876543210')

        first = self.client.post(LOGIN_VERIFY, {'phone_number': '9876543210', 'otp': self.sent.last}, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data['needs_details'])

        res = self.client.post(LOGIN_VERIFY, {
            'phone_number': '9876543210', 'otp': self.sent.last,
            'first_name': 'Asha', 'email': 'Asha@Example.com',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data)
        user = User.objects.get(phone_number='9876543210')
        self.assertTrue(user.phone_verified)
        self.assertEqual(user.email, 'asha@example.com')
        self.assertFalse(user.has_usable_password())

    def test_email_is_optional_and_can_be_added_later(self):
        self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')
        res = self.client.post(LOGIN_VERIFY, {
            'phone_number': '9876543210', 'otp': self.sent.last, 'first_name': 'Asha',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(phone_number='9876543210')
        self.assertIsNone(user.email)

        # A second email-less account must fit the unique index too.
        self.client.post(LOGIN_SEND, {'phone_number': '9123456780'}, format='json')
        res = self.client.post(LOGIN_VERIFY, {
            'phone_number': '9123456780', 'otp': self.sent.last, 'first_name': 'Ravi',
        }, format='json')
        self.assertEqual(res.status_code, 201)

        self.client.force_authenticate(user)
        self.client.patch('/api/v1/user/profile/', {'email': 'Asha@Example.com'}, format='json')
        user.refresh_from_db()
        self.assertEqual(user.email, 'asha@example.com')
        # ...but not changed once set.
        self.client.patch('/api/v1/user/profile/', {'email': 'other@example.com'}, format='json')
        user.refresh_from_db()
        self.assertEqual(user.email, 'asha@example.com')

    def test_password_login_with_phone_number(self):
        User.objects.create_user(email='a@example.com', password='strongpass1',
                                 phone_number='9876543210', is_active=True)

        res = self.client.post('/api/v1/user/login/', {'email': '+91 98765 43210', 'password': 'strongpass1'}, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)

    def test_existing_account_signs_in_even_with_old_phone_format(self):
        user = User.objects.create_user(email='a@example.com', password='x' * 8,
                                        phone_number='+91 98765-43210', is_active=True)
        self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')

        res = self.client.post(LOGIN_VERIFY, {'phone_number': '9876543210', 'otp': self.sent.last}, format='json')

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['id'], user.id)
        user.refresh_from_db()
        self.assertTrue(user.phone_verified)

    def test_code_is_single_use(self):
        User.objects.create_user(email='a@example.com', password='x' * 8, phone_number='9876543210', is_active=True)
        self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')
        body = {'phone_number': '9876543210', 'otp': self.sent.last}
        self.assertEqual(self.client.post(LOGIN_VERIFY, body, format='json').status_code, 200)
        self.assertEqual(self.client.post(LOGIN_VERIFY, body, format='json').status_code, 400)

    def test_wrong_codes_are_capped(self):
        self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')
        right = self.sent.last
        wrong = '000000' if right != '000000' else '111111'
        for _ in range(PhoneOTP.MAX_ATTEMPTS):
            self.client.post(LOGIN_VERIFY, {'phone_number': '9876543210', 'otp': wrong}, format='json')

        res = self.client.post(LOGIN_VERIFY, {'phone_number': '9876543210', 'otp': right}, format='json')

        self.assertEqual(res.status_code, 400)
        self.assertIn('Too many', res.data['message'])

    def test_resend_cooldown_and_daily_cap(self):
        self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')
        self.assertEqual(self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json').status_code, 429)

        # Five sends earlier today: past the cooldown, but at the daily cap.
        PhoneOTP.objects.all().delete()
        for _ in range(5):
            PhoneOTP.issue('9876543210', PhoneOTP.LOGIN)
        PhoneOTP.objects.update(created_at=timezone.now() - timedelta(hours=1))
        res = self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')
        self.assertEqual(res.status_code, 429)
        self.assertIn('today', res.data['message'])

    def test_failed_whatsapp_send_does_not_count(self):
        self.send_mock.side_effect = WhatsAppError('not a WhatsApp number')

        res = self.client.post(LOGIN_SEND, {'phone_number': '9876543210'}, format='json')

        self.assertEqual(res.status_code, 502)
        self.assertFalse(PhoneOTP.objects.exists())

    def test_rejects_invalid_number(self):
        res = self.client.post(LOGIN_SEND, {'phone_number': '12345'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.send_mock.assert_not_called()


class PhoneVerificationTests(PhoneOTPTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email='g@example.com', password='x' * 8, is_active=True)
        self.client.force_authenticate(self.user)

    def verify(self, phone):
        self.client.post(PHONE_SEND, {'phone_number': phone}, format='json')
        return self.client.post(PHONE_VERIFY, {'phone_number': phone, 'otp': self.sent.last}, format='json')

    def test_adds_and_verifies_a_number_for_an_account_without_one(self):
        res = self.verify('9876543210')

        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone_number, '9876543210')
        self.assertTrue(self.user.phone_verified)

    def test_takes_number_from_guest_and_converts_guest(self):
        User.objects.create_user(email='old-guest@example.com', phone_number='9876543210', is_guest=True, is_active=True)
        self.user.is_guest = True
        self.user.save()

        self.assertEqual(self.verify('9876543210').status_code, 200)

        self.assertIsNone(User.objects.get(email='old-guest@example.com').phone_number)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_guest)

    def test_refuses_number_of_another_real_account(self):
        User.objects.create_user(email='owner@example.com', password='x' * 8, phone_number='9876543210', is_active=True)

        res = self.client.post(PHONE_SEND, {'phone_number': '9876543210'}, format='json')

        self.assertEqual(res.status_code, 409)
        self.send_mock.assert_not_called()

    def test_profile_phone_change_clears_verification(self):
        self.verify('9876543210')

        self.client.patch('/api/v1/user/profile/', {'phone_number': '9123456780'}, format='json')

        self.user.refresh_from_db()
        self.assertFalse(self.user.phone_verified)


class CODGateTests(PhoneOTPTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email='c@example.com', password='x' * 8,
                                             phone_number='9876543210', is_active=True)
        self.client.force_authenticate(self.user)

    def test_cod_blocked_until_phone_verified(self):
        res = self.client.post(CREATE_ORDER, {'payment_method': 'cod', 'products': []}, format='json')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data['code'], 'phone_not_verified')

        self.user.phone_verified = True
        self.user.save()
        res = self.client.post(CREATE_ORDER, {'payment_method': 'cod', 'products': []}, format='json')
        # Past the gate: now it fails on the empty basket instead.
        self.assertNotEqual(res.status_code, 403)

    def test_prepaid_not_gated(self):
        res = self.client.post(CREATE_ORDER, {'payment_method': 'upi', 'products': []}, format='json')
        self.assertNotEqual(res.status_code, 403)

    @override_settings(REQUIRE_PHONE_VERIFICATION_FOR_COD=False)
    def test_gate_can_be_switched_off(self):
        res = self.client.post(CREATE_ORDER, {'payment_method': 'cod', 'products': []}, format='json')
        self.assertNotEqual(res.status_code, 403)


class ForgotPasswordTests(PhoneOTPTestCase):
    SEND = '/api/v1/user/forgot-password-otp/'
    VERIFY = '/api/v1/user/forgot-password-otp-verify/'
    RESET = '/api/v1/user/forgot-password-reset/'

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email='a@example.com', password='oldpass123',
                                             phone_number='9876543210', is_active=True)

    def reset(self, uid, token, password='newpass123'):
        return self.client.post(self.RESET, {
            'uid': uid, 'token': token, 'password': password, 'confirm_password': password,
        }, format='json')

    def test_reset_by_phone(self):
        self.assertEqual(self.client.post(self.SEND, {'phone_number': '9876543210'}, format='json').status_code, 200)
        res = self.client.post(self.VERIFY, {'phone_number': '9876543210', 'otp': self.sent.last}, format='json')
        self.assertEqual(res.status_code, 200)

        self.assertEqual(self.reset(res.data['uid'], res.data['token']).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))
        self.assertTrue(self.user.phone_verified)

    @mock.patch('users.serializers.send_otp_email.delay')
    def test_reset_by_email(self, _mail):
        self.client.post(self.SEND, {'email': 'A@example.com'}, format='json')
        code = self.user.otp_set.get().otp_code
        res = self.client.post(self.VERIFY, {'email': 'a@example.com', 'otp': code}, format='json')

        self.assertEqual(self.reset(res.data['uid'], res.data['token']).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

    def test_reset_needs_a_verified_otp(self):
        # The old endpoint reset any account from its email alone.
        res = self.client.post(self.RESET, {
            'email': 'a@example.com', 'password': 'hacked123', 'confirm_password': 'hacked123',
        }, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.reset(self.user.pk, 'forged-token').status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))

    def test_token_works_once(self):
        self.client.post(self.SEND, {'phone_number': '9876543210'}, format='json')
        res = self.client.post(self.VERIFY, {'phone_number': '9876543210', 'otp': self.sent.last}, format='json')
        self.reset(res.data['uid'], res.data['token'])

        self.assertEqual(self.reset(res.data['uid'], res.data['token'], 'again12345').status_code, 400)

    def test_unknown_number_gets_no_message(self):
        res = self.client.post(self.SEND, {'phone_number': '9123456780'}, format='json')
        self.assertEqual(res.status_code, 404)
        self.send_mock.assert_not_called()
