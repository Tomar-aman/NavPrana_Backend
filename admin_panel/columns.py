"""
Column specifications for panel list tables.

A :class:`Column` says *what* to pull off a model instance and *how* it should
be presented; :func:`render_cell` turns that pair into a small dict the table
template renders without any further logic. Keeping the formatting decisions
here is what lets one ``crud/list.html`` serve every resource.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.files import FieldFile
from django.utils.text import Truncator


# Semantic badge tones understood by panel.css. Anything not mapped falls back
# to "neutral", so an unexpected value from the database still renders sanely.
BADGE_TONES = ('success', 'warning', 'danger', 'info', 'purple', 'neutral')

ORDER_STATUS_TONES = {
    'pending': 'warning',
    'accepted': 'info',
    'processing': 'info',
    'shipped': 'purple',
    'delivered': 'success',
    'cancelled': 'neutral',
    'failed': 'danger',
}

PAYMENT_STATUS_TONES = {
    'paid': 'success',
    'pending': 'warning',
    'failed': 'danger',
    'refunded': 'neutral',
}

TRANSACTION_STATUS_TONES = {
    'success': 'success',
    'pending': 'warning',
    'failed': 'danger',
    'cancelled': 'neutral',
    'refunded': 'info',
}

BOOLEAN_TONES = {True: 'success', False: 'neutral'}


MISSING = object()


@dataclass(frozen=True)
class Column:
    """One column of a resource list table.

    ``name`` doubles as the accessor path and the sort key. Traversal accepts
    both ``user__email`` and ``user.email``, and falls back to a no-argument
    method of the same name, so ``get_status_display`` works as a column.
    """

    name: str
    label: str = ''
    kind: str = 'text'
    sortable: bool = True
    sort_field: str = ''
    align: str = ''
    accessor: Optional[Callable[[Any], Any]] = None
    tones: Optional[Mapping[Any, str]] = None
    truncate: int = 0
    empty: str = '—'
    prefix: str = ''
    suffix: str = ''
    is_link: bool = False
    css_class: str = ''

    def header(self) -> str:
        if self.label:
            return self.label
        return self.name.replace('__', ' ').replace('_', ' ').strip().title()

    def order_by(self) -> str:
        """Database field this column sorts on ('' when not sortable)."""
        if not self.sortable:
            return ''
        return self.sort_field or self.name.replace('.', '__')

    def alignment(self) -> str:
        if self.align:
            return self.align
        if self.kind in ('currency', 'number'):
            return 'right'
        if self.kind in ('bool', 'image'):
            return 'center'
        return 'left'


@dataclass(frozen=True)
class Cell:
    """Pre-rendered cell handed to the template."""

    kind: str
    display: str = ''
    tone: str = 'neutral'
    url: str = ''
    title: str = ''
    align: str = 'left'
    css_class: str = ''
    is_empty: bool = False


def resolve_value(obj: Any, path: str, default: Any = MISSING) -> Any:
    """Walk ``path`` across relations, calling zero-argument callables.

    Returns ``default`` (``None`` unless overridden) as soon as any hop is
    missing, so a null FK or an unsaved reverse one-to-one never explodes a
    whole table render.
    """
    current = obj
    for part in path.replace('__', '.').split('.'):
        if current is None:
            return None if default is MISSING else default
        try:
            current = getattr(current, part)
        except (AttributeError, ObjectDoesNotExist):
            return None if default is MISSING else default
        if callable(current) and not isinstance(current, type):
            try:
                current = current()
            except TypeError:
                # A method that needs arguments is not a usable accessor.
                return None if default is MISSING else default
    return current


def format_currency(value: Any) -> str:
    """Indian-rupee formatting with lakh/crore digit grouping."""
    if value in (None, ''):
        return ''
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    negative = amount < 0
    amount = abs(amount).quantize(Decimal('0.01'))
    whole, _, fraction = f'{amount:.2f}'.partition('.')

    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ','.join(groups + [tail])

    rendered = f'₹{whole}.{fraction}'
    return f'-{rendered}' if negative else rendered


def format_number(value: Any) -> str:
    if value in (None, ''):
        return ''
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return str(value)


def _display_for(obj: Any, column: Column) -> Any:
    """Prefer Django's ``get_<field>_display`` when the field has choices."""
    if column.accessor is not None:
        return column.accessor(obj)

    if '__' not in column.name and '.' not in column.name:
        getter = getattr(obj, f'get_{column.name}_display', None)
        if callable(getter) and column.kind in ('badge', 'text'):
            try:
                return getter()
            except Exception:  # pragma: no cover - defensive
                pass
    return resolve_value(obj, column.name)


def render_cell(obj: Any, column: Column, detail_url: str = '') -> Cell:
    """Turn ``obj[column]`` into a ready-to-print :class:`Cell`."""
    raw = _display_for(obj, column)
    align = column.alignment()
    url = detail_url if column.is_link else ''

    if column.kind == 'bool':
        truthy = bool(raw)
        return Cell(
            kind='bool',
            display='Yes' if truthy else 'No',
            tone=BOOLEAN_TONES[truthy],
            align=align,
            css_class=column.css_class,
        )

    if raw in (None, '', []):
        return Cell(
            kind='empty',
            display=column.empty,
            align=align,
            is_empty=True,
            css_class=column.css_class,
        )

    if column.kind == 'currency':
        display = format_currency(raw)
    elif column.kind == 'number':
        display = format_number(raw)
    elif column.kind == 'image':
        source = raw.url if isinstance(raw, FieldFile) and raw else ''
        return Cell(
            kind='image',
            display=source,
            url=source,
            align=align,
            is_empty=not source,
            css_class=column.css_class,
        )
    elif column.kind == 'file':
        source = raw.url if isinstance(raw, FieldFile) and raw else ''
        return Cell(
            kind='file',
            display='Download' if source else column.empty,
            url=source,
            align=align,
            is_empty=not source,
            css_class=column.css_class,
        )
    else:
        display = str(raw)

    title = display
    if column.truncate and len(display) > column.truncate:
        display = Truncator(display).chars(column.truncate)

    tone = 'neutral'
    if column.kind == 'badge':
        lookup = resolve_value(obj, column.name) if column.accessor is None else raw
        tones = column.tones or {}
        tone = tones.get(lookup, tones.get(str(lookup).lower(), 'neutral'))

    return Cell(
        kind=column.kind,
        display=f'{column.prefix}{display}{column.suffix}',
        tone=tone,
        url=url,
        title=title,
        align=align,
        css_class=column.css_class,
    )


# Never rendered on a detail page, whatever the model declares. Password
# hashes and gateway secrets have no business being on screen.
SENSITIVE_FIELD_NAMES = frozenset(
    {'password', 'secret', 'secret_key', 'api_key', 'signing_key', 'order_token'}
)

_KIND_BY_FIELD_CLASS = {
    'DateTimeField': 'datetime',
    'DateField': 'date',
    'TimeField': 'text',
    'BooleanField': 'bool',
    'ImageField': 'image',
    'FileField': 'file',
    'IntegerField': 'number',
    'PositiveIntegerField': 'number',
    'PositiveSmallIntegerField': 'number',
    'BigIntegerField': 'number',
    'SmallIntegerField': 'number',
}

# Decimal fields whose name contains one of these read as money.
_MONEY_HINTS = ('amount', 'price', 'fee', 'total', 'revenue')


def infer_kind(field) -> str:
    """Best-guess column kind for a model field."""
    class_name = type(field).__name__

    if class_name == 'DecimalField':
        name = field.name.lower()
        return 'currency' if any(hint in name for hint in _MONEY_HINTS) else 'number'
    if getattr(field, 'choices', None):
        return 'badge'
    return _KIND_BY_FIELD_CLASS.get(class_name, 'text')


def auto_columns(model, exclude=()) -> tuple:
    """Columns for every concrete field on ``model``, minus the excluded ones.

    Used by detail pages that have not declared explicit panels, so a newly
    registered model still shows something complete and correctly formatted.
    """
    skip = set(exclude) | SENSITIVE_FIELD_NAMES
    built = []
    for field in model._meta.fields:
        if field.name in skip or not getattr(field, 'concrete', True):
            continue
        label = str(getattr(field, 'verbose_name', field.name)).strip()
        built.append(
            Column(
                name=field.name,
                label=label[:1].upper() + label[1:],
                kind=infer_kind(field),
                truncate=160,
                sortable=False,
            )
        )
    return tuple(built)


def safe_repr(obj: Any, limit: int = 190) -> str:
    """``str(obj)`` that survives a broken ``__str__``.

    Several models in this project build their ``__str__`` from fields that no
    longer exist, and audit logging must never be the thing that 500s a save.
    """
    try:
        text = str(obj)
    except Exception:  # pragma: no cover - depends on model bugs
        text = f'{obj.__class__.__name__} #{getattr(obj, "pk", "?")}'
    return Truncator(text).chars(limit)
