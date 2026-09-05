"""
Generic CRUD views driven by the resource registry.

One view class per action serves every registered model. What differs per model
comes from its :class:`~admin_panel.registry.PanelResource`, not from a
copy-pasted view, and each class re-checks the Django permission for the verb it
performs before doing anything.
"""

import csv
import logging

from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView, View

from ..audit import log_addition, log_change, log_deletion
from ..columns import render_cell, safe_repr
from ..metrics import invalidate_alerts
from ..mixins import ResourceViewMixin
from ..resources import annotate_queryset
from ..utils import (
    PAGE_SIZES,
    csv_value,
    drop_params,
    merged_query,
    resolve_page_size,
    safe_redirect_target,
)


logger = logging.getLogger(__name__)

#: Hard ceiling on a CSV export. Reaching it is reported in the file itself.
EXPORT_ROW_LIMIT = 50_000


class FilteredQuerysetMixin:
    """Shared search / filter / sort pipeline for lists and exports."""

    def get_filtered_queryset(self):
        params = self.request.GET
        resource = self.resource

        queryset = annotate_queryset(resource, resource.get_queryset())
        queryset = resource.apply_search(queryset, (params.get('q') or '').strip())
        queryset = resource.apply_filters(queryset, params)
        return resource.apply_ordering(queryset, params.get('sort', ''))

    def has_active_filters(self) -> bool:
        params = self.request.GET
        if (params.get('q') or '').strip():
            return True
        return any(list_filter.is_active(params) for list_filter in self.resource.filters)


class ResourceListView(FilteredQuerysetMixin, ResourceViewMixin, ListView):
    """Searchable, filterable, sortable, paginated table for one resource."""

    required_verb = 'view'
    context_object_name = 'objects'

    def get_template_names(self):
        return [self.resource.list_template]

    def get_paginate_by(self, queryset):
        return resolve_page_size(self.request.GET, self.resource.per_page)

    def get_queryset(self):
        return self.get_filtered_queryset()

    def get_page_title(self):
        return self.resource.label_plural

    def get_page_subtitle(self):
        return self.resource.description

    def get_breadcrumbs(self):
        return [(self.resource.group, ''), (self.resource.label_plural, '')]

    # -- table construction -------------------------------------------------

    def build_rows(self, objects):
        resource = self.resource
        rows = []
        for obj in objects:
            detail_url = resource.detail_url(obj)
            rows.append(
                {
                    'obj': obj,
                    'pk': obj.pk,
                    'detail_url': detail_url,
                    'edit_url': resource.url('edit', obj.pk),
                    'delete_url': resource.url('delete', obj.pk),
                    'cells': [render_cell(obj, column, detail_url) for column in resource.columns],
                }
            )
        return rows

    def build_sort_state(self):
        """Per-column sort URL plus the current direction, for the header row."""
        current = self.request.GET.get('sort', '')
        current_field = current.lstrip('-')
        descending = current.startswith('-')

        state = []
        for column in self.resource.columns:
            field = column.order_by()
            if not field:
                state.append({'column': column, 'url': '', 'direction': ''})
                continue
            is_current = field == current_field
            # Clicking the active column flips it; a new column starts ascending.
            next_sort = f'-{field}' if (is_current and not descending) else field
            state.append(
                {
                    'column': column,
                    'url': merged_query(self.request.GET, sort=next_sort, page=None),
                    'direction': ('desc' if descending else 'asc') if is_current else '',
                }
            )
        return state

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resource = self.resource
        params = self.request.GET
        user = self.request.user

        context.update(
            {
                'rows': self.build_rows(context['objects']),
                'sort_state': self.build_sort_state(),
                'search_term': (params.get('q') or '').strip(),
                'filter_contexts': [f.context(params) for f in resource.filters],
                'has_filters': bool(resource.filters),
                'filters_applied': self.has_active_filters(),
                'clear_filters_url': drop_params(
                    params, ['q', 'page'] + [key for f in resource.filters for key in f.clear_params()]
                ),
                'page_sizes': PAGE_SIZES,
                'current_page_size': resolve_page_size(params, resource.per_page),
                'page_size_urls': {
                    size: merged_query(params, per_page=size, page=None) for size in PAGE_SIZES
                },
                'export_url': resource.url('export') + merged_query(params, page=None),
                'bulk_actions': [
                    action
                    for action in resource.bulk_actions
                    if resource.user_can(user, action.permission)
                ],
                'current_query': merged_query(params, page=None),
                'new_label': f'Add {resource.label.lower()}',
                'total_count': context['paginator'].count if context.get('paginator') else len(context['objects']),
            }
        )
        page_obj, paginator = context.get('page_obj'), context.get('paginator')
        if page_obj and paginator:
            context['page_links'] = self.build_page_links(paginator, page_obj)
            context['prev_url'] = (
                merged_query(params, page=page_obj.previous_page_number())
                if page_obj.has_previous() else ''
            )
            context['next_url'] = (
                merged_query(params, page=page_obj.next_page_number())
                if page_obj.has_next() else ''
            )
        return context

    def build_page_links(self, paginator, page_obj):
        """Elided page range, pre-rendered so the template stays declarative."""
        params = self.request.GET
        links = []
        for entry in paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1):
            if entry == paginator.ELLIPSIS:
                links.append({'is_gap': True, 'label': str(paginator.ELLIPSIS)})
                continue
            links.append(
                {
                    'is_gap': False,
                    'label': str(entry),
                    'url': merged_query(params, page=entry),
                    'is_current': entry == page_obj.number,
                }
            )
        return links

    # -- bulk actions -------------------------------------------------------

    def post(self, request, *args, **kwargs):
        resource = self.resource
        action_key = request.POST.get('action', '')
        action = next((a for a in resource.bulk_actions if a.key == action_key), None)
        back = safe_redirect_target(request, resource.url('list'))

        if action is None:
            messages.error(request, 'That action is not available for this section.')
            return redirect(back)

        if not resource.user_can(request.user, action.permission):
            raise PermissionDenied(f'You do not have permission to run "{action.label}".')

        selected = request.POST.getlist('selected')
        if not selected:
            messages.warning(request, 'Select at least one row first.')
            return redirect(back)

        queryset = resource.get_queryset().filter(pk__in=selected)
        try:
            result = action.handler(request, queryset)
        except Exception:
            logger.exception('Panel bulk action %s failed on %s', action_key, resource.key)
            messages.error(request, 'That action could not be completed. The error has been logged.')
            return redirect(back)

        invalidate_alerts()

        if isinstance(result, (HttpResponse, StreamingHttpResponse)):
            return result

        messages.success(request, result or f'"{action.label}" completed.')
        return redirect(back)


class SingletonListView(ResourceViewMixin, View):
    """List page for a resource that only ever holds one row.

    A settings model has nothing to list: a table of exactly one row, with a
    search box and a pagination bar around it, is two clicks of ceremony in
    front of the only thing anyone came for. So the section opens the row
    itself — the edit form for staff who may change it, the read-only detail
    page for everyone else.
    """

    required_verb = 'view'

    def get(self, request, *args, **kwargs):
        resource = self.resource
        obj = resource.get_queryset().first()
        if obj is None:
            raise Http404(f'{resource.label_plural} has no record to open.')
        action = 'edit' if resource.user_can(request.user, 'change') else 'detail'
        return redirect(resource.url(action, obj.pk))


class ResourceDetailView(ResourceViewMixin, DetailView):
    """Read-only record view built from the resource's detail panels."""

    required_verb = 'view'
    context_object_name = 'object'

    def get_template_names(self):
        return [self.resource.detail_template]

    def get_page_title(self):
        return self.resource.object_title(self.object)

    def get_breadcrumbs(self):
        return [
            (self.resource.group, ''),
            (self.resource.label_plural, self.resource.url('list')),
            (self.resource.object_title(self.object), ''),
        ]

    def build_panels(self):
        return [
            {
                'title': panel.title,
                'icon': panel.icon,
                'rows': [
                    {'label': column.header(), 'cell': render_cell(self.object, column)}
                    for column in panel.columns
                ],
            }
            for panel in self.resource.get_detail_panels()
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resource = self.resource
        context.update(
            {
                'panels': self.build_panels(),
                'edit_url': resource.url('edit', self.object.pk),
                'delete_url': resource.url('delete', self.object.pk),
                'list_url': resource.url('list'),
            }
        )
        return context


class ResourceFormView(ResourceViewMixin, TemplateView):
    """Shared create/update handling.

    Kept as a plain ``TemplateView`` rather than ``ModelFormMixin`` so create
    and edit share one code path and both can pass ``panel_request`` into the
    form for permission-aware fields.
    """

    is_create = True

    def get_template_names(self):
        return [self.resource.form_template]

    def get_object(self):
        if self.is_create:
            return None
        return get_object_or_404(self.resource.get_queryset(), pk=self.kwargs['pk'])

    def get_form(self, data=None, files=None):
        form_class = self.resource.get_form_class()
        return form_class(
            data=data,
            files=files,
            instance=self.object,
            panel_request=self.request,
        )

    def get_page_title(self):
        if self.is_create:
            return f'New {self.resource.label.lower()}'
        return f'Edit {self.resource.object_title(self.object)}'

    def get_breadcrumbs(self):
        crumbs = [
            (self.resource.group, ''),
            (self.resource.label_plural, self.resource.url('list')),
        ]
        if self.is_create:
            crumbs.append(('New', ''))
        else:
            crumbs.append((self.resource.object_title(self.object), self.resource.url('detail', self.object.pk)))
            crumbs.append(('Edit', ''))
        return crumbs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data(form=self.get_form()))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form(data=request.POST, files=request.FILES)

        if not form.is_valid():
            messages.error(request, 'Please correct the highlighted fields.')
            return self.render_to_response(self.get_context_data(form=form))

        try:
            instance = self.resource.save_form(form, request, created=self.is_create)
        except ValidationError as exc:
            # Model-level validation that the form could not anticipate.
            form.add_error(None, exc)
            return self.render_to_response(self.get_context_data(form=form))
        except (ValueError, TypeError) as exc:
            # Several models raise bare ValueError from save(); surface it as a
            # form error instead of a 500.
            logger.warning('Panel save rejected by %s.save(): %s', self.resource.key, exc)
            form.add_error(None, str(exc) or 'This record could not be saved.')
            return self.render_to_response(self.get_context_data(form=form))

        if self.is_create:
            log_addition(request.user, instance)
            messages.success(request, f'{self.resource.label} created.')
        else:
            log_change(request.user, instance, form.changed_data)
            if form.changed_data:
                messages.success(request, f'{self.resource.label} updated.')
            else:
                messages.info(request, 'No changes were made.')

        invalidate_alerts()

        if '_addanother' in request.POST and self.resource.user_can(request.user, 'add'):
            return redirect(self.resource.url('add'))
        return redirect(self.resource.url('detail', instance.pk))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context.get('form')
        context.update(
            {
                'object': self.object,
                'is_create': self.is_create,
                'fieldsets': form.visible_fieldsets(self.resource.fieldsets) if form else [],
                'cancel_url': (
                    self.resource.url('list') if self.is_create
                    else self.resource.url('detail', self.object.pk)
                ),
                'delete_url': '' if self.is_create else self.resource.url('delete', self.object.pk),
            }
        )
        return context


class ResourceCreateView(ResourceFormView):
    required_verb = 'add'
    is_create = True


class ResourceUpdateView(ResourceFormView):
    required_verb = 'change'
    is_create = False


class ResourceDeleteView(ResourceViewMixin, TemplateView):
    """Confirmation page that spells out what else will be removed."""

    required_verb = 'delete'
    template_name = 'panel/crud/delete.html'

    def get_object(self):
        return get_object_or_404(self.resource.get_queryset(), pk=self.kwargs['pk'])

    def get_page_title(self):
        return f'Delete {self.resource.object_title(self.object)}'

    def get_breadcrumbs(self):
        return [
            (self.resource.group, ''),
            (self.resource.label_plural, self.resource.url('list')),
            (self.resource.object_title(self.object), self.resource.url('detail', self.object.pk)),
            ('Delete', ''),
        ]

    def collect_related(self):
        """Summarise the cascade so nobody deletes an order and loses its items."""
        collector = NestedObjects(using=router.db_for_write(self.resource.model))
        collector.collect([self.object])
        summary = []
        for model, instances in collector.model_objs.items():
            if model is self.resource.model and len(instances) == 1:
                continue
            summary.append(
                {
                    'label': model._meta.verbose_name_plural.title(),
                    'count': len(instances),
                    'samples': [safe_repr(obj, 60) for obj in list(instances)[:4]],
                }
            )
        return sorted(summary, key=lambda row: -row['count'])

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        title = self.resource.object_title(self.object)

        try:
            log_deletion(request.user, self.object)
            self.object.delete()
        except Exception:
            logger.exception('Panel delete failed for %s #%s', self.resource.key, self.kwargs['pk'])
            messages.error(
                request,
                'This record could not be deleted, most likely because other data depends on it.',
            )
            return redirect(self.resource.url('detail', self.kwargs['pk']))

        invalidate_alerts()
        messages.success(request, f'{self.resource.label} "{title}" was deleted.')
        return redirect(self.resource.url('list'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'object': self.object,
                'object_title': self.resource.object_title(self.object),
                'related': self.collect_related(),
                'cancel_url': self.resource.url('detail', self.object.pk),
            }
        )
        return context


class _CSVBuffer:
    """Write target that hands each row straight to the streaming response."""

    def write(self, value):
        return value


class ResourceExportView(FilteredQuerysetMixin, ResourceViewMixin, View):
    """Stream the current, filtered list as CSV."""

    required_verb = 'view'

    def check_permissions(self, request):
        super().check_permissions(request)
        if not self.resource.can_export:
            raise PermissionDenied('This section cannot be exported.')

    def get(self, request, *args, **kwargs):
        resource = self.resource
        columns = resource.export_columns
        writer = csv.writer(_CSVBuffer())
        queryset = self.get_filtered_queryset()

        def rows():
            yield writer.writerow([column.header() for column in columns])
            exported = 0
            for obj in queryset.iterator(chunk_size=500):
                if exported >= EXPORT_ROW_LIMIT:
                    # Never truncate silently — say so in the file itself.
                    yield writer.writerow(
                        [f'Export stopped at the {EXPORT_ROW_LIMIT:,} row limit. Narrow the filters for the rest.']
                    )
                    break
                yield writer.writerow([csv_value(render_cell(obj, column)) for column in columns])
                exported += 1

        stamp = timezone.localtime().strftime('%Y%m%d-%H%M')
        response = StreamingHttpResponse(rows(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{resource.key}-{stamp}.csv"'
        return response
