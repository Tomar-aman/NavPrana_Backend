import random
from datetime import timedelta

from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from users.managers import UserManager

class User(AbstractUser):
    username = None
    first_name = models.CharField(
        _('first name'),    
        max_length=150,
        blank=True,
        help_text=_('Optional first name of the user.')
    )
    last_name = models.CharField(
        _('last name'),
        max_length=150,
        blank=True,
        help_text=_('Optional last name of the user.')
    )
    country_code = models.CharField(
        _('country code'),
        max_length=5,
        null=True,
        blank=True,
    )
    phone_number = models.CharField(
        _('phone number'),
        max_length=18,
        unique=True,
        null=True,
        blank=True,
        error_messages={
            'unique': _("A user with that phone number already exists."),
        },
    )
    email = models.EmailField(
        _("email"),
        unique=True,
        error_messages={
            'unique': _("A user with that email already exists."),
            'invalid': _("Invalid email address."),
            },
        null=True,
        blank=True 
        )
    profile_picture = models.ImageField(
        _('profile picture'),
        upload_to='profile_pictures/',
        null=True,
        blank=True
    )
    google_id = models.CharField(
        _('google id'),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        error_messages={
            'unique': _("A user with that Google ID already exists."),
        },
    )
    facebook_id = models.CharField(
        _('facebook id'),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        error_messages={
            'unique': _("A user with that Facebook ID already exists."),
        },
    )
    email_verified = models.BooleanField(
        _('email verified'),
        default=False,
        help_text=_('Designates whether the user has verified their email address.')
    )
    phone_verified = models.BooleanField(
        _('phone verified'),
        default=False,
        help_text=_('Designates whether the user has verified their phone number.')
    )
    is_guest = models.BooleanField(
        _('guest account'),
        default=False,
        help_text=_(
            'Account created silently during guest checkout. It has no usable '
            'password, so guest checkout may sign it in from an email/phone '
            'alone. Clears once the customer sets a password.'
        )
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return f"{self.first_name} - {self.email}"


class UserAddress(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name=_('user'),
        help_text=_('The user associated with this address')
    )
    address_line1 = models.CharField(
        _('address line 1'),
        max_length=255,
        help_text=_('Primary address line')
    )
    address_line2 = models.CharField(
        _('address line 2'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Secondary address line (optional)')
    )
    city = models.CharField(
        _('city'),
        max_length=100,
        help_text=_('City of the address')
    )
    state = models.CharField(
        _('state'),
        max_length=100,
        help_text=_('State or province of the address')
    )
    postal_code = models.CharField(
        _('postal code'),
        max_length=20,
        help_text=_('Postal or ZIP code of the address')
    )
    country = models.CharField(
        _('country'),
        max_length=100,
        help_text=_('Country of the address')
    )
    is_default = models.BooleanField(
        _('is default'),
        default=False,
        db_index=True,
        help_text=_('Designates whether this address is the default for the user')
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Designates whether this address is active')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('user address')
        verbose_name_plural = _('user addresses')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.first_name} - {self.address_line1}, {self.city}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            # Unset other default addresses for the user
            UserAddress.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class OTP(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_('user'),
        help_text=_('The user associated with this OTP')
    )
    otp_code = models.CharField(
        _('OTP code'),
        max_length=6,
        help_text=_('One-time password code for verification')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    expires_at = models.DateTimeField(
        _('expires at'),
        null=True,
        blank=True,
        help_text=_('Expiration time for the OTP code')
    )
    send_count = models.PositiveIntegerField(
        _('send count'),
        default=1,
        help_text=_('How many codes have been issued to this user in the current cycle')
    )
    attempt_count = models.PositiveIntegerField(
        _('failed attempts'),
        default=0,
        help_text=_('How many wrong codes have been submitted against this OTP')
    )

    class Meta:
        verbose_name = _('OTP')
        verbose_name_plural = _('OTPs')

    def __str__(self):
        return f"OTP for {self.user.first_name} - {self.otp_code}"
    
    def is_expired(self):
        """
        Check if the OTP has expired.
        """
        from django.utils import timezone
        return timezone.now() > self.expires_at if self.expires_at else True

    @classmethod
    def issue_for(cls, user, ttl_minutes=10):
        """
        Replace any code this user already holds with a fresh one.

        Every OTP path goes through here so a user never accumulates more than
        one live code. Signup used to call update_or_create while resend and
        forgot-password called create, so rows piled up until the next signup
        raised MultipleObjectsReturned.
        """
        from django.utils import timezone

        with transaction.atomic():
            # The row is about to be deleted, so carry its tally forward or the
            # resend count would reset to 1 on every resend.
            previous = cls.objects.select_for_update().filter(
                user=user
            ).order_by('-created_at').first()
            send_count = previous.send_count + 1 if previous else 1

            cls.objects.filter(user=user).delete()
            return cls.objects.create(
                user=user,
                otp_code=str(random.randint(100000, 999999)),
                expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
                send_count=send_count,
            )

    @classmethod
    def record_failed_attempt(cls, user):
        """
        Count one wrong code against this user's live OTP.

        F() keeps concurrent submissions from losing an increment.
        """
        cls.objects.filter(user=user).update(attempt_count=F('attempt_count') + 1)
