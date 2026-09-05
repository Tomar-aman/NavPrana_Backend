"""
Declarative list filters.

Every filter reads its own querystring parameter, validates it, and narrows a
queryset. Validation matters here: the value reaches the ORM, so each filter
only ever applies a lookup it built itself from a known-good choice list or a
parsed date.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Callable, Iterable, Optional, Sequence

from django.db.models import Q, QuerySet
from django.utils import timezone


@dataclass
class FilterOption:
    """One selectable value, ready for a ``<select>``."""

    value: str
    label: str
    selected: bool = False


class BaseFilter:
    """Common plumbing: read a param, expose it, apply it."""

    template = 'select'

    def __init__(self, param: str, label: str, field: str = ''):
        self.param = param
        self.label = label
        self.field = field or param

    def raw_value(self, params) -> str:
        return (params.get(self.param) or '').strip()

    def is_active(self, params) -> bool:
        return bool(self.raw_value(params))

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        raise NotImplementedError

    def context(self, params) -> dict:
        raise NotImplementedError

    def clear_params(self) -> Sequence[str]:
        """Querystring keys this filter owns, dropped when clearing filters."""
        return (self.param,)


class ChoiceFilter(BaseFilter):
    """Single-select over a fixed or lazily-computed choice list.

    ``choices`` may be a callable so a filter can reflect what is actually in
    the table rather than only what the model's ``choices`` declare — the
    orders table, for instance, is full of ``payment_method='cashfree'`` values
    that never made it into ``PAYMENT_METHOD_CHOICES``.
    """

    def __init__(
        self,
        param: str,
        label: str,
        choices: Any,
        field: str = '',
        blank_label: str = 'All',
    ):
        super().__init__(param, label, field)
        self._choices = choices
        self.blank_label = blank_label

    def resolve_choices(self) -> Sequence[tuple]:
        choices = self._choices() if callable(self._choices) else self._choices
        return list(choices or ())

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        value = self.raw_value(params)
        if not value:
            return queryset
        valid = {str(key) for key, _ in self.resolve_choices()}
        if value not in valid:
            return queryset
        return queryset.filter(**{self.field: value})

    def context(self, params) -> dict:
        current = self.raw_value(params)
        options = [FilterOption('', self.blank_label, not current)]
        options += [
            FilterOption(str(key), str(label), str(key) == current)
            for key, label in self.resolve_choices()
        ]
        return {
            'template': self.template,
            'param': self.param,
            'label': self.label,
            'options': options,
            'value': current,
        }


class BooleanFilter(BaseFilter):
    """Yes / No / All over a ``BooleanField``."""

    def __init__(
        self,
        param: str,
        label: str,
        field: str = '',
        true_label: str = 'Yes',
        false_label: str = 'No',
        blank_label: str = 'All',
    ):
        super().__init__(param, label, field)
        self.true_label = true_label
        self.false_label = false_label
        self.blank_label = blank_label

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        value = self.raw_value(params)
        if value == 'yes':
            return queryset.filter(**{self.field: True})
        if value == 'no':
            return queryset.filter(**{self.field: False})
        return queryset

    def context(self, params) -> dict:
        current = self.raw_value(params)
        options = [
            FilterOption('', self.blank_label, not current),
            FilterOption('yes', self.true_label, current == 'yes'),
            FilterOption('no', self.false_label, current == 'no'),
        ]
        return {
            'template': self.template,
            'param': self.param,
            'label': self.label,
            'options': options,
            'value': current,
        }


class RelationFilter(BaseFilter):
    """Select over a related table, capped so a huge FK never bloats the page."""

    def __init__(
        self,
        param: str,
        label: str,
        queryset_factory: Callable[[], QuerySet],
        field: str = '',
        label_attr: str = '',
        limit: int = 200,
        blank_label: str = 'All',
    ):
        super().__init__(param, label, field)
        self.queryset_factory = queryset_factory
        self.label_attr = label_attr
        self.limit = limit
        self.blank_label = blank_label

    def _objects(self) -> Iterable:
        return self.queryset_factory()[: self.limit]

    def _label_for(self, obj) -> str:
        if self.label_attr:
            return str(getattr(obj, self.label_attr, obj.pk))
        from .columns import safe_repr

        return safe_repr(obj, 60)

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        value = self.raw_value(params)
        if not value.isdigit():
            return queryset
        return queryset.filter(**{f'{self.field}_id': int(value)})

    def context(self, params) -> dict:
        current = self.raw_value(params)
        options = [FilterOption('', self.blank_label, not current)]
        options += [
            FilterOption(str(obj.pk), self._label_for(obj), str(obj.pk) == current)
            for obj in self._objects()
        ]
        return {
            'template': self.template,
            'param': self.param,
            'label': self.label,
            'options': options,
            'value': current,
        }


class DateRangeFilter(BaseFilter):
    """``<param>_from`` / ``<param>_to`` pair over a date or datetime field.

    Datetime fields get the whole ``to`` day included and are made timezone
    aware, so "1 Jan to 1 Jan" returns that day's rows rather than nothing.
    """

    template = 'daterange'

    def __init__(self, param: str, label: str, field: str = '', is_datetime: bool = True):
        super().__init__(param, label, field)
        self.is_datetime = is_datetime

    @property
    def from_param(self) -> str:
        return f'{self.param}_from'

    @property
    def to_param(self) -> str:
        return f'{self.param}_to'

    def clear_params(self) -> Sequence[str]:
        return (self.from_param, self.to_param)

    @staticmethod
    def _parse(value: str) -> Optional[date]:
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def is_active(self, params) -> bool:
        return bool(params.get(self.from_param) or params.get(self.to_param))

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        start = self._parse((params.get(self.from_param) or '').strip())
        end = self._parse((params.get(self.to_param) or '').strip())

        if start and end and start > end:
            start, end = end, start

        if not self.is_datetime:
            if start:
                queryset = queryset.filter(**{f'{self.field}__gte': start})
            if end:
                queryset = queryset.filter(**{f'{self.field}__lte': end})
            return queryset

        current_tz = timezone.get_current_timezone()
        if start:
            lower = datetime.combine(start, time.min)
            if timezone.is_naive(lower):
                lower = timezone.make_aware(lower, current_tz)
            queryset = queryset.filter(**{f'{self.field}__gte': lower})
        if end:
            upper = datetime.combine(end, time.max)
            if timezone.is_naive(upper):
                upper = timezone.make_aware(upper, current_tz)
            queryset = queryset.filter(**{f'{self.field}__lte': upper})
        return queryset

    def context(self, params) -> dict:
        return {
            'template': self.template,
            'label': self.label,
            'from_param': self.from_param,
            'to_param': self.to_param,
            'from_value': (params.get(self.from_param) or '').strip(),
            'to_value': (params.get(self.to_param) or '').strip(),
        }


class ExpiryFilter(BaseFilter):
    """Live / expired over an expiry timestamp.

    A row whose expiry is NULL counts as expired, matching what the models
    using this field already decide — ``OTP.is_expired()`` treats a missing
    timestamp as no longer valid, and a filter that disagreed with the column
    printed beside it would be worse than no filter at all.
    """

    def __init__(
        self,
        param: str,
        label: str,
        field: str = '',
        live_label: str = 'Live',
        expired_label: str = 'Expired',
        blank_label: str = 'All',
    ):
        super().__init__(param, label, field)
        self.live_label = live_label
        self.expired_label = expired_label
        self.blank_label = blank_label

    def apply(self, queryset: QuerySet, params) -> QuerySet:
        value = self.raw_value(params)
        now = timezone.now()
        if value == 'live':
            return queryset.filter(**{f'{self.field}__gt': now})
        if value == 'expired':
            return queryset.filter(
                Q(**{f'{self.field}__lte': now}) | Q(**{f'{self.field}__isnull': True})
            )
        return queryset

    def context(self, params) -> dict:
        current = self.raw_value(params)
        options = [
            FilterOption('', self.blank_label, not current),
            FilterOption('live', self.live_label, current == 'live'),
            FilterOption('expired', self.expired_label, current == 'expired'),
        ]
        return {
            'template': self.template,
            'param': self.param,
            'label': self.label,
            'options': options,
            'value': current,
        }


def build_search_q(term: str, search_fields: Sequence[str]) -> Q:
    """OR ``icontains`` across ``search_fields`` for every whitespace token.

    Tokens are ANDed together so "raj delhi" narrows rather than widens.
    Numeric-only fields (``id``) are matched exactly and skipped for
    non-numeric tokens, which keeps Postgres from erroring on ``id__icontains``.
    """
    query = Q()
    for token in term.split():
        token_query = Q()
        for path in search_fields:
            if path.endswith('__exact_int'):
                base = path[: -len('__exact_int')]
                if token.isdigit():
                    token_query |= Q(**{base: int(token)})
                continue
            token_query |= Q(**{f'{path}__icontains': token})
        if token_query:
            query &= token_query
    return query
