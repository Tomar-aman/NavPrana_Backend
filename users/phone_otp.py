"""
WhatsApp OTPs for phone numbers: OTP login, and verifying the number before a
COD order is accepted.

Every WhatsApp message costs money, so sends are capped per number and per IP.
Otherwise a script could run up the bill, or flood a stranger's WhatsApp.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db.models import F, Q, Value
from django.db.models.functions import Replace
from django.utils import timezone

from users.models import PhoneOTP, User

logger = logging.getLogger(__name__)

RESEND_COOLDOWN = timedelta(seconds=30)
MAX_SENDS_PER_NUMBER_PER_DAY = 5
MAX_SENDS_PER_IP_PER_HOUR = 10

MOBILE_RE = re.compile(r'[6-9]\d{9}')


class PhoneOTPError(Exception):
    """A send or check the customer should be told about. ``status`` is the
    HTTP status the view answers with."""

    def __init__(self, message, status=400, field='otp'):
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field


def normalize_phone(value):
    """Reduce "+91 98765-43210", "09876543210" and the like to ten digits.

    Mirrors normalizePhone() on the frontend. A number that fits none of those
    shapes keeps its digits, so it fails validation instead of being cut down
    to a plausible-looking wrong number.
    """
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    while len(digits) > 10:
        if digits.startswith('91'):
            digits = digits[2:]
        elif digits.startswith('0'):
            digits = digits[1:]
        else:
            break
    return digits


def clean_mobile(value):
    phone = normalize_phone(value)
    if not MOBILE_RE.fullmatch(phone):
        raise PhoneOTPError('Enter a valid 10-digit mobile number.', field='phone_number')
    return phone


def users_with_phone(phone):
    """Accounts holding ``phone`` in any of the shapes it has been stored in.

    Older rows kept whatever the customer typed ("+91 98765…", "098765…").
    """
    digits = F('phone_number')
    for sep in (' ', '-', '+', '(', ')'):
        digits = Replace(digits, Value(sep), Value(''))
    return (
        User.objects.filter(phone_number__isnull=False)
        .annotate(phone_digits=digits)
        .filter(phone_digits__in=[phone, f'91{phone}', f'0{phone}', f'091{phone}'])
    )


def _claimable(queryset):
    """Holders a verified owner may take the number from: guest accounts, and
    signups abandoned at the old email-OTP step. Neither ever proved the
    number was theirs."""
    return queryset.filter(Q(is_guest=True) | Q(is_active=False, email_verified=False))


def held_by_other_account(phone, user):
    """Whether a real account other than ``user`` already holds ``phone``."""
    others = users_with_phone(phone).exclude(pk=user.pk)
    return others.exclude(pk__in=_claimable(others).values('pk')).exists()


def release_from_others(phone, user):
    """Clear ``phone`` from claimable accounts so ``user`` can hold it."""
    others = users_with_phone(phone).exclude(pk=user.pk)
    pks = list(_claimable(others).values_list('pk', flat=True))
    User.objects.filter(pk__in=pks).update(phone_number=None)


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')) or None


def send(phone, purpose, ip=None):
    """Issue a code for ``phone`` and send it on WhatsApp."""
    now = timezone.now()
    recent = PhoneOTP.objects.filter(phone_number=phone)

    latest = recent.filter(purpose=purpose).order_by('-created_at').first()
    if latest and now - latest.created_at < RESEND_COOLDOWN:
        raise PhoneOTPError('Please wait a few seconds before requesting another code.', status=429)
    if recent.filter(created_at__gte=now - timedelta(days=1)).count() >= MAX_SENDS_PER_NUMBER_PER_DAY:
        raise PhoneOTPError('Too many codes sent to this number today. Please try again tomorrow.', status=429)
    if ip and PhoneOTP.objects.filter(
        requested_ip=ip, created_at__gte=now - timedelta(hours=1)
    ).count() >= MAX_SENDS_PER_IP_PER_HOUR:
        raise PhoneOTPError('Too many requests. Please try again in a while.', status=429)

    row, code = PhoneOTP.issue(phone, purpose, requested_ip=ip)

    if not settings.WHATSAPP_ACCESS_TOKEN:
        if settings.DEBUG:
            # Local development without Meta credentials.
            logger.warning('WhatsApp not configured; OTP for %s is %s', phone, code)
            return row
        row.delete()
        raise PhoneOTPError('WhatsApp codes are unavailable right now. Please try again later.', status=503)

    from whatsapp import client

    try:
        row.wa_message_id = client.send_otp_template(f'91{phone}', code)
    except client.WhatsAppError as exc:
        # Nothing reached the customer, so this send must not count against
        # their limits or hold them in the cooldown.
        row.delete()
        logger.warning('WhatsApp OTP to %s failed: %s', phone, exc)
        raise PhoneOTPError(
            'Could not send a WhatsApp message to this number. '
            'Check that the number is correct and uses WhatsApp.',
            status=502,
        )
    row.save(update_fields=['wa_message_id'])
    return row


def check(phone, purpose, code, consume=True):
    """Raise :class:`PhoneOTPError` unless ``code`` is the live one.

    ``consume=False`` checks without using the code up, for OTP login asking a
    new customer for their name before the account is created.
    """
    row = PhoneOTP.live(phone, purpose)
    if row is None or row.expires_at <= timezone.now():
        raise PhoneOTPError('This code has expired. Please request a new one.')
    if row.attempt_count >= PhoneOTP.MAX_ATTEMPTS:
        raise PhoneOTPError('Too many wrong attempts. Please request a new code.')
    if not row.matches(str(code).strip()):
        PhoneOTP.objects.filter(pk=row.pk).update(attempt_count=F('attempt_count') + 1)
        raise PhoneOTPError('Invalid code.')
    if consume:
        row.used_at = timezone.now()
        row.save(update_fields=['used_at'])
    return row
