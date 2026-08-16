"""
Access control and shared page context for panel views.

Two rules hold everywhere:

* :class:`PanelAccessMixin` — only active staff reach any panel URL.
* :class:`ResourceViewMixin` — every resource view re-checks the Django model
  permission for the verb it performs, *before* the view body runs. Hiding a
  sidebar link is presentation; this is the part that makes typing the URL fail.
"""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property

from .navigation import build_navigation
from .registry import registry


class PanelAccessMixin:
    """Require an authenticated, active staff account.

    Subclasses extend :meth:`check_permissions` rather than ``dispatch`` so the
    check always lands before the handler, whatever the MRO looks like.
    """

    def check_permissions(self, request):
        """Raise :class:`PermissionDenied` to reject an authenticated user."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('admin_panel:login'), 'next')
        if not (user.is_active and user.is_staff):
            raise PermissionDenied('An admin panel account is required.')
        self.check_permissions(request)
        return super().dispatch(request, *args, **kwargs)


class PanelContextMixin(PanelAccessMixin):
    """Adds the chrome every panel page renders: nav, breadcrumbs, alerts."""

    page_title = ''
    page_subtitle = ''
    nav_key = ''

    def get_breadcrumbs(self):
        """``[(label, url or '')]``; the final entry renders as plain text."""
        return []

    def get_page_title(self):
        return self.page_title

    def get_page_subtitle(self):
        return self.page_subtitle

    def get_nav_key(self):
        return self.nav_key

    def get_context_data(self, **kwargs):
        from .metrics import get_alerts

        context = super().get_context_data(**kwargs)
        active = self.get_nav_key()
        context.update(
            {
                'panel_nav': build_navigation(self.request.user, active),
                'panel_nav_key': active,
                'page_title': self.get_page_title(),
                'page_subtitle': self.get_page_subtitle(),
                'breadcrumbs': self.get_breadcrumbs(),
                'panel_alerts': get_alerts(self.request.user),
            }
        )
        return context


class ResourceViewMixin(PanelContextMixin):
    """Resolves ``<resource>`` from the URL and enforces its permissions."""

    #: ``view`` / ``add`` / ``change`` / ``delete``
    required_verb = 'view'

    @cached_property
    def resource(self):
        resource = registry.get(self.kwargs.get('resource', ''))
        if resource is None:
            raise Http404('Unknown panel section.')
        return resource

    def check_permissions(self, request):
        super().check_permissions(request)
        resource = self.resource
        if not resource.user_can(request.user, self.required_verb):
            verb = {'view': 'view', 'add': 'create', 'change': 'edit', 'delete': 'delete'}[self.required_verb]
            raise PermissionDenied(
                f'You do not have permission to {verb} {resource.label_plural.lower()}.'
            )

    def get_nav_key(self):
        return self.resource.key

    def get_queryset(self):
        return self.resource.get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        resource = self.resource
        context.update(
            {
                'resource': resource,
                'can_add': resource.user_can(user, 'add'),
                'can_edit': resource.user_can(user, 'change'),
                'can_delete': resource.user_can(user, 'delete'),
                'can_export': resource.can_export and resource.user_can(user, 'view'),
            }
        )
        return context
