from django.db import models
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
    firebase_uid = models.CharField(
        _('firebase uid'),
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Firebase account that verified this phone number over SMS.'),
        error_messages={
            'unique': _("A user with that Firebase account already exists."),
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
