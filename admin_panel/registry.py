"""
The resource registry.

A :class:`PanelResource` is a declarative description of how one model should
behave inside the panel: its columns, filters, searchable fields, editable
fields, permissions and bulk actions. Generic views read these descriptions, so
adding a model to the panel is a registration rather than five new views.

Permissions deliberately reuse Django's own ``app_label.verb_model`` codenames,
which already exist in this database (196 ``auth.Permission`` rows). Nothing new
is invented, and a group configured for the Django admin works here unchanged.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from django.db.models import QuerySet
from django.urls import reverse

from .columns import Column
from .filters import BaseFilter, build_search_q


@dataclass(frozen=True)
class BulkAction:
    """A checkbox-driven action on a list page.

    ``handler(request, queryset)`` returns a human-readable result message. The
    action is hidden and rejected unless the user holds ``permission``.
    """

    key: str
    label: str
    handler: Callable[[Any, QuerySet], str]
    permission: str = 'change'
    tone: str = 'default'
    confirm: str = ''


@dataclass(frozen=True)
class DetailPanel:
    """A card on the detail page, listing ``(label, column)`` rows."""

    title: str
    columns: Sequence[Column]
    icon: str = ''


class PanelResource:
    """Configuration for a single model in the panel."""

    #: Overridden by subclasses that need bespoke templates.
    detail_template = 'panel/crud/detail.html'
    form_template = 'panel/crud/form.html'
    list_template = 'panel/crud/list.html'

    def __init__(
        self,
        *,
        key: str,
        model: type,
        group: str,
        icon: str = 'box',
        label: str = '',
        label_plural: str = '',
        description: str = '',
        columns: Sequence[Column] = (),
        search_fields: Sequence[str] = (),
        search_hint: str = '',
        filters: Sequence[BaseFilter] = (),
        default_ordering: str = '-pk',
        ordering_fields: Sequence[str] = (),
        select_related: Sequence[str] = (),
        prefetch_related: Sequence[str] = (),
        only_fields: Sequence[str] = (),
        form_fields: Sequence[str] = (),
        fieldsets: Sequence[tuple] = (),
        readonly_fields: Sequence[str] = (),
        detail_panels: Sequence[DetailPanel] = (),
        bulk_actions: Sequence[BulkAction] = (),
        can_add: bool = True,
        can_edit: bool = True,
        can_delete: bool = True,
        can_export: bool = True,
        export_columns: Sequence[Column] = (),
        per_page: int = 25,
        form_class: Optional[type] = None,
        form_template: str = '',
        detail_template: str = '',
        empty_message: str = '',
        help_text: str = '',
    ):
        self.key = key
        self.model = model
        self.group = group
        self.icon = icon
        self.description = description
        self.columns = tuple(columns)
        self.search_fields = tuple(search_fields)
        self.search_hint = search_hint
        self.filters = tuple(filters)
        self.default_ordering = default_ordering
        self.select_related = tuple(select_related)
        self.prefetch_related = tuple(prefetch_related)
        self.only_fields = tuple(only_fields)
        self.form_fields = tuple(form_fields)
        self.fieldsets = tuple(fieldsets)
        self.readonly_fields = tuple(readonly_fields)
        self.detail_panels = tuple(detail_panels)
        self.bulk_actions = tuple(bulk_actions)
        self.can_add = can_add
        self.can_edit = can_edit
        self.can_delete = can_delete
        self.can_export = can_export
        self.export_columns = tuple(export_columns) or self.columns
        self.per_page = per_page
        self.form_class = form_class
        self.empty_message = empty_message
        self.help_text = help_text
        if form_template:
            self.form_template = form_template
        if detail_template:
            self.detail_template = detail_template

        meta = model._meta
        self.label = label or meta.verbose_name.title()
        self.label_plural = label_plural or meta.verbose_name_plural.title()
        self.app_label = meta.app_label
        self.model_name = meta.model_name

        # Sortable columns plus any explicit extras, used to validate ?sort=.
        allowed = {column.order_by() for column in self.columns if column.order_by()}
        allowed.update(ordering_fields)
        allowed.add('pk')
        self.ordering_fields = frozenset(allowed)

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def perm(self, verb: str) -> str:
        """Django permission codename for ``view``/``add``/``change``/``delete``."""
        return f'{self.app_label}.{verb}_{self.model_name}'

    def user_can(self, user, verb: str) -> bool:
        """Permission check that also honours the resource's own switches."""
        if verb == 'add' and not self.can_add:
            return False
        if verb == 'change' and not self.can_edit:
            return False
        if verb == 'delete' and not self.can_delete:
            return False
        return user.has_perm(self.perm(verb))

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def base_queryset(self) -> QuerySet:
        """Hook for resources that need a scoped or annotated base set."""
        return self.model._default_manager.all()

    def get_queryset(self) -> QuerySet:
        queryset = self.base_queryset()
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)
        return queryset

    def apply_search(self, queryset: QuerySet, term: str) -> QuerySet:
        if not term or not self.search_fields:
            return queryset
        return queryset.filter(build_search_q(term, self.search_fields))

    def apply_filters(self, queryset: QuerySet, params) -> QuerySet:
        for list_filter in self.filters:
            queryset = list_filter.apply(queryset, params)
        return queryset

    def apply_ordering(self, queryset: QuerySet, sort: str) -> QuerySet:
        """Order by ``sort`` only when it names a column we published."""
        field = (sort or '').lstrip('-')
        if field and field in self.ordering_fields:
            return queryset.order_by(sort)
        return queryset.order_by(self.default_ordering)

    # ------------------------------------------------------------------
    # URLs
    # ------------------------------------------------------------------

    def url(self, action: str, pk: Any = None) -> str:
        names = {
            'list': 'resource_list',
            'add': 'resource_add',
            'detail': 'resource_detail',
            'edit': 'resource_edit',
            'delete': 'resource_delete',
            'export': 'resource_export',
        }
        name = f'admin_panel:{names[action]}'
        if pk is None:
            return reverse(name, kwargs={'resource': self.key})
        return reverse(name, kwargs={'resource': self.key, 'pk': pk})

    def detail_url(self, obj) -> str:
        return self.url('detail', obj.pk)

    # Templates cannot call ``url()`` with an argument, so the argument-free
    # entry points are exposed as properties.
    @property
    def url_list(self) -> str:
        return self.url('list')

    @property
    def url_add(self) -> str:
        return self.url('add')

    @property
    def url_export(self) -> str:
        return self.url('export')

    def object_title(self, obj) -> str:
        """Heading for detail/edit/delete pages."""
        from .columns import safe_repr

        return safe_repr(obj, 80)

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------

    def get_detail_panels(self) -> Sequence[DetailPanel]:
        """Declared panels, or one auto-built from the model's own fields."""
        if self.detail_panels:
            return self.detail_panels

        from .columns import auto_columns

        return (DetailPanel(title='Details', columns=auto_columns(self.model)),)

    # ------------------------------------------------------------------
    # Forms
    # ------------------------------------------------------------------

    def get_form_class(self):
        from .forms import build_resource_form

        if self.form_class is not None:
            return self.form_class
        return build_resource_form(self)

    def save_form(self, form, request, created: bool):
        """Hook for post-save side effects. Returns the saved instance."""
        return form.save()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f'<PanelResource {self.key}>'


class ResourceRegistry:
    """Ordered ``key -> PanelResource`` map."""

    def __init__(self):
        self._resources: Dict[str, PanelResource] = {}

    def register(self, resource: PanelResource) -> PanelResource:
        if resource.key in self._resources:
            raise ValueError(f'Panel resource "{resource.key}" is already registered')
        self._resources[resource.key] = resource
        return resource

    def get(self, key: str) -> Optional[PanelResource]:
        return self._resources.get(key)

    def all(self) -> Sequence[PanelResource]:
        return tuple(self._resources.values())

    def __contains__(self, key: str) -> bool:
        return key in self._resources

    def __iter__(self):
        return iter(self._resources.values())


registry = ResourceRegistry()
