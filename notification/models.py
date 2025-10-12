from django.db import models
from users.models import User
from django.utils.translation import gettext_lazy as _

class Notification(models.Model):
    title = models.CharField(
        max_length=255,
        verbose_name=_('Notification Title'),
        help_text=_('Enter the title of the notification')
    )
    message = models.TextField(
        verbose_name=_('Notification Message'),
        help_text=_('Enter the message of the notification')
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('User'),
        help_text=_('Select the user for this notification')
    )    
    is_read = models.BooleanField(
        default=False,
        verbose_name=_('Is Read'),
        help_text=_('Check this box if the notification has been read')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('The date and time when the notification was created')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
        help_text=_('The date and time when the notification was last updated')
    )

    class Meta:
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']
