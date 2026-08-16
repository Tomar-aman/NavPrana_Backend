"""
Activity log and global search.

The log reads ``django.contrib.admin.LogEntry``, so it covers actions taken in
this panel *and* in ``/admin/`` — one history rather than two partial ones.
"""

from urllib.parse import urlencode

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.views.generic import ListView, TemplateView

from ..audit import describe
from ..filters import ChoiceFilter, DateRangeFilter
from ..mixins import PanelContextMixin
from ..registry import registry
from ..utils import drop_params, merged_query, resolve_page_size, PAGE_SIZES


User = get_user_model()

ACTION_CHOICES = (
    (str(ADDITION), 'Created'),
    (str(CHANGE), 'Updated'),
    (str(DELETION), 'Deleted'),
)


def _content_type_choices():
    """Only the content types that actually appear in the log."""
    used = LogEntry.objects.values_list('content_type_id', flat=True).distinct()
    types = ContentType.objects.filter(id__in=list(used)).order_by('app_label', 'model')
    return [(str(ct.pk), f'{ct.app_label} · {ct.model}') for ct in types]


def _actor_choices():
    used = LogEntry.objects.values_list('user_id', flat=True).distinct()
    return [
        (str(user.pk), user.email or f'User #{user.pk}')
        for user in User.objects.filter(id__in=list(used)).order_by('email')
    ]


class ActivityLogView(PanelContextMixin, ListView):
    """Chronological, filterable record of administrative changes."""

    template_name = 'panel/activity.html'
    context_object_name = 'entries'
    nav_key = 'activity'
    page_title = 'Activity Log'
    page_subtitle = 'Every create, update and delete made by an administrator'

    filters = (
        ChoiceFilter('action', 'Action', ACTION_CHOICES, field='action_flag'),
        ChoiceFilter('model', 'Record type', _content_type_choices, field='content_type_id'),
        ChoiceFilter('actor', 'Administrator', _actor_choices, field='user_id'),
        DateRangeFilter('when', 'Date', field='action_time'),
    )

    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm('admin.view_logentry'):
            raise PermissionDenied('You do not have permission to view the activity log.')

    def get_breadcrumbs(self):
        return [('System', ''), ('Activity Log', '')]

    def get_paginate_by(self, queryset):
        return resolve_page_size(self.request.GET, 40)

    def get_queryset(self):
        params = self.request.GET
        queryset = LogEntry.objects.select_related('user', 'content_type')

        term = (params.get('q') or '').strip()
        if term:
            queryset = queryset.filter(
                Q(object_repr__icontains=term)
                | Q(change_message__icontains=term)
                | Q(user__email__icontains=term)
            )

        for log_filter in self.filters:
            queryset = log_filter.apply(queryset, params)
        return queryset.order_by('-action_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET

        rows = []
        for entry in context['entries']:
            rows.append(
                {
                    'entry': entry,
                    'target_url': self._target_url(entry),
                    **describe(entry),
                }
            )

        context.update(
            {
                'rows': rows,
                'search_term': (params.get('q') or '').strip(),
                'filter_contexts': [f.context(params) for f in self.filters],
                'filters_applied': any(f.is_active(params) for f in self.filters)
                or bool((params.get('q') or '').strip()),
                'clear_filters_url': drop_params(
                    params, ['q', 'page'] + [key for f in self.filters for key in f.clear_params()]
                ),
                'page_sizes': PAGE_SIZES,
                'current_page_size': resolve_page_size(params, 40),
            }
        )

        page_obj, paginator = context.get('page_obj'), context.get('paginator')
        if page_obj and paginator:
            context['page_links'] = [
                {'is_gap': True, 'label': str(paginator.ELLIPSIS)}
                if entry == paginator.ELLIPSIS
                else {
                    'is_gap': False,
                    'label': str(entry),
                    'url': merged_query(params, page=entry),
                    'is_current': entry == page_obj.number,
                }
                for entry in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
            ]
            context['prev_url'] = (
                merged_query(params, page=page_obj.previous_page_number()) if page_obj.has_previous() else ''
            )
            context['next_url'] = (
                merged_query(params, page=page_obj.next_page_number()) if page_obj.has_next() else ''
            )
        return context

    def _target_url(self, entry):
        """Link the logged object to its panel page, when one exists.

        Log rows outlive the objects they describe, so a missing record simply
        renders without a link rather than producing a broken one.
        """
        if entry.action_flag == DELETION or not entry.object_id:
            return ''
        content_type = entry.content_type
        if content_type is None:
            return ''
        for resource in registry:
            if (
                resource.model._meta.app_label == content_type.app_label
                and resource.model._meta.model_name == content_type.model
            ):
                if not resource.user_can(self.request.user, 'view'):
                    return ''
                return resource.url('detail', entry.object_id)
        return ''


class GlobalSearchView(PanelContextMixin, TemplateView):
    """One search box across the records staff look up most often.

    Each section is skipped unless the user may view it, so search never
    discloses the existence of records they cannot open.
    """

    template_name = 'panel/search.html'
    nav_key = ''
    page_title = 'Search'
    RESULT_LIMIT = 6
    SEARCHABLE = ('orders', 'users', 'products', 'coupons', 'transactions', 'queries')

    def get_breadcrumbs(self):
        return [('Search', '')]

    def get_page_subtitle(self):
        term = (self.request.GET.get('q') or '').strip()
        return f'Results for "{term}"' if term else 'Search orders, customers, products and more'

    def get_context_data(self, **kwargs):
        from ..columns import safe_repr

        context = super().get_context_data(**kwargs)
        term = (self.request.GET.get('q') or '').strip()
        groups, total = [], 0

        if len(term) >= 2:
            for key in self.SEARCHABLE:
                resource = registry.get(key)
                if resource is None or not resource.user_can(self.request.user, 'view'):
                    continue

                matches = resource.apply_search(resource.get_queryset(), term)
                found = list(matches.order_by(resource.default_ordering)[: self.RESULT_LIMIT + 1])
                if not found:
                    continue

                has_more = len(found) > self.RESULT_LIMIT
                found = found[: self.RESULT_LIMIT]
                total += len(found)
                groups.append(
                    {
                        'resource': resource,
                        'items': [
                            {'label': resource.object_title(obj), 'sub': safe_repr(obj, 70),
                             'url': resource.detail_url(obj)}
                            for obj in found
                        ],
                        'more_url': f'{resource.url("list")}?{urlencode({"q": term})}' if has_more else '',
                    }
                )

        context.update({'term': term, 'groups': groups, 'result_count': total})
        return context
