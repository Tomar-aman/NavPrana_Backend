from django.db import models
from django.utils.translation import gettext_lazy as _

class SMTPSettings(models.Model):
    host = models.CharField(
        _('SMTP Host'),
        max_length=255,
        help_text=_('SMTP server hostname')
    )
    port = models.IntegerField(
        _('SMTP Port'),
        help_text=_('SMTP server port number')
    )
    username = models.CharField(
        _('SMTP Username'),
        max_length=255,
        help_text=_('SMTP authentication username')
    )
    password = models.CharField(
        _('SMTP Password'),
        max_length=255,
        help_text=_('SMTP authentication password')
    )
    from_email = models.EmailField(
        _('From Email'),
        help_text=_('Default sender email address')
    )
    use_tls = models.BooleanField(
        _('Use TLS'),
        default=True,
        help_text=_('Enable TLS encryption for SMTP connection')
    )
    created_at = models.DateTimeField(
        _('Created At'), 
        auto_now_add=True
        )
    updated_at = models.DateTimeField(
        _('Updated At'), 
        auto_now=True
        )

    class Meta:
        verbose_name = _('SMTP Setting')
        verbose_name_plural = _('SMTP Settings')
        ordering = ['-updated_at']

    def __str__(self):
        return f"SMTP Settings - {self.host} ({self.username})"
