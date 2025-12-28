from django.db import models
from django.utils.translation import gettext_lazy as _

class BaseModel(models.Model):
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        help_text=_('The date and time when the record was created')
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
        help_text=_('The date and time when the record was last updated')
    )

    class Meta:
        abstract = True