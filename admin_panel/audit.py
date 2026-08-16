"""
Audit trail.

Panel writes are recorded in ``django.contrib.admin.LogEntry`` — the same table
the built-in Django admin already writes to (200 rows and counting in this
database). Reusing it means one chronological history across both admins and,
just as importantly, no new model and no migration.
"""

import logging

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType

from .columns import safe_repr


logger = logging.getLogger(__name__)

ACTION_LABELS = {ADDITION: 'Created', CHANGE: 'Updated', DELETION: 'Deleted'}
ACTION_TONES = {ADDITION: 'success', CHANGE: 'info', DELETION: 'danger'}


def _log(user, obj, action_flag, message):
    """Write one LogEntry, swallowing any failure.

    Audit logging is a side effect of a save that already succeeded; it must
    never be the thing that turns a good write into a 500.
    """
    try:
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj, for_concrete_model=False).pk,
            object_id=obj.pk,
            object_repr=safe_repr(obj, 190),
            action_flag=action_flag,
            change_message=message[:400],
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception('Could not write panel audit entry for %r', obj)


def log_addition(user, obj, message='Added via admin panel.'):
    _log(user, obj, ADDITION, message)


def log_change(user, obj, changed_fields=None):
    if changed_fields:
        message = 'Changed ' + ', '.join(sorted(changed_fields)) + ' via admin panel.'
    else:
        message = 'Updated via admin panel.'
    _log(user, obj, CHANGE, message)


def log_deletion(user, obj, message='Deleted via admin panel.'):
    _log(user, obj, DELETION, message)


def describe(entry: LogEntry) -> dict:
    """Presentation data for one log row."""
    return {
        'label': ACTION_LABELS.get(entry.action_flag, 'Changed'),
        'tone': ACTION_TONES.get(entry.action_flag, 'neutral'),
    }
