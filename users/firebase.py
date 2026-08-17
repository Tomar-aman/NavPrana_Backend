"""
Firebase phone-authentication support.

The browser runs the whole SMS round trip through the Firebase JS SDK and ends
up with a Firebase ID token. Everything here exists to turn that token back
into a phone number we are willing to trust, so the rest of the app can keep
issuing its own SimpleJWT tokens exactly as it does for Google and Facebook.

Nothing initialises at import time — a missing or broken service account must
surface as a clean API error, never as a crash while Django is booting.
"""

import json
import logging
import threading
from pathlib import Path

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from django.conf import settings
from rest_framework import serializers

logger = logging.getLogger('django')

_init_lock = threading.Lock()
_app = None

# Name it explicitly rather than using the default app, so a future Firebase
# feature (FCM, say) can initialise its own app without colliding with ours.
_APP_NAME = 'navprana-auth'


class FirebaseNotConfigured(Exception):
    """Raised when FIREBASE_CREDENTIALS_JSON is missing or unreadable."""


def _load_credentials():
    raw = (getattr(settings, 'FIREBASE_CREDENTIALS_JSON', '') or '').strip()
    if not raw:
        raise FirebaseNotConfigured(
            'FIREBASE_CREDENTIALS_JSON is not set. Point it at the '
            'service-account JSON from the Firebase console, or paste the JSON '
            'itself into the environment variable.'
        )

    # Raw JSON pasted straight into the env var.
    if raw.startswith('{'):
        try:
            return credentials.Certificate(json.loads(raw))
        except (ValueError, KeyError) as exc:
            raise FirebaseNotConfigured(
                f'FIREBASE_CREDENTIALS_JSON is not a valid service account: {exc}'
            ) from exc

    path = Path(raw)
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    if not path.is_file():
        raise FirebaseNotConfigured(
            f'Firebase service account file not found at {path}.'
        )
    try:
        return credentials.Certificate(str(path))
    except (ValueError, KeyError) as exc:
        raise FirebaseNotConfigured(
            f'{path} is not a valid Firebase service account: {exc}'
        ) from exc


def get_firebase_app():
    """Initialise the Firebase app once per process and reuse it after that."""
    global _app
    if _app is not None:
        return _app

    with _init_lock:
        if _app is None:
            try:
                _app = firebase_admin.get_app(_APP_NAME)
            except ValueError:
                _app = firebase_admin.initialize_app(_load_credentials(), name=_APP_NAME)
    return _app


def split_e164(e164):
    """
    Split '+919876543210' into ('+91', '9876543210').

    Signup and guest checkout both store a bare 10-digit number in
    User.phone_number with the dialling prefix in User.country_code, so a
    Firebase login has to be reduced the same way to match accounts that
    already exist.
    """
    digits = ''.join(ch for ch in e164 if ch.isdigit())
    national = digits[-10:]
    prefix = digits[:-10]
    return (f'+{prefix}' if prefix else ''), national


def verify_phone_id_token(id_token):
    """
    Verify a Firebase ID token and return the phone number it proves.

    Returns ``{'uid', 'e164', 'country_code', 'phone_number'}`` where
    ``phone_number`` is the 10-digit national part this project stores.

    Raises DRF ValidationError on anything we should not trust, so callers can
    use it straight from ``Serializer.validate()``.
    """
    if not id_token:
        raise serializers.ValidationError(
            {'firebase_id_token': 'Phone verification token is required.'}
        )

    try:
        app = get_firebase_app()
    except FirebaseNotConfigured as exc:
        # A configuration problem is ours, not the customer's — say so plainly
        # in the logs while keeping the API message free of internal detail.
        logger.error('Firebase phone auth is misconfigured: %s', exc)
        raise serializers.ValidationError({
            'firebase_id_token': 'Phone verification is unavailable right now. '
                                 'Please try another sign-in method.'
        }) from exc

    try:
        # verify_id_token checks the signature, expiry and audience (the
        # audience being this project, taken from the service account above).
        decoded = firebase_auth.verify_id_token(id_token, app=app)
    except firebase_auth.ExpiredIdTokenError as exc:
        raise serializers.ValidationError({
            'firebase_id_token': 'This verification has expired. '
                                 'Please request a new OTP.'
        }) from exc
    except (firebase_auth.InvalidIdTokenError, firebase_auth.RevokedIdTokenError,
            firebase_auth.CertificateFetchError, ValueError) as exc:
        raise serializers.ValidationError({
            'firebase_id_token': 'Could not verify that phone number. '
                                 'Please try again.'
        }) from exc

    e164 = decoded.get('phone_number')
    if not e164:
        # Firebase only puts phone_number in the token once a number has been
        # verified over SMS, so its presence is the security property we rely
        # on — a token from any other sign-in method simply will not carry one.
        raise serializers.ValidationError({
            'firebase_id_token': 'That sign-in did not verify a phone number.'
        })

    country_code, national = split_e164(e164)
    if len(national) < 10:
        raise serializers.ValidationError({
            'firebase_id_token': 'The verified number is not a valid mobile number.'
        })

    return {
        'uid': decoded['uid'],
        'e164': e164,
        'country_code': country_code,
        'phone_number': national,
    }
