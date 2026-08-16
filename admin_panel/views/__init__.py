"""Panel views, plus the dispatcher that lets a resource override a page."""

from .activity import ActivityLogView, GlobalSearchView
from .auth import (
    PanelLoginView,
    PanelLogoutView,
    PanelPasswordChangeView,
    PanelProfileView,
    UserSetPasswordView,
)
from .crud import (
    ResourceCreateView,
    ResourceDeleteView,
    ResourceDetailView,
    ResourceExportView,
    ResourceListView,
    ResourceUpdateView,
)
from .dashboard import DashboardView
from .orders import OrderDetailView, OrderStatusUpdateView


#: Resources whose detail page needs more than the generic field dump.
#: Declared here rather than on the resource itself so ``resources.py`` never
#: has to import views (which import resources).
DETAIL_VIEW_OVERRIDES = {
    'orders': OrderDetailView,
}


def resource_detail(request, resource, pk):
    """Route to a resource's bespoke detail view, or the generic one."""
    view_class = DETAIL_VIEW_OVERRIDES.get(resource, ResourceDetailView)
    return view_class.as_view()(request, resource=resource, pk=pk)


__all__ = [
    'ActivityLogView',
    'DashboardView',
    'GlobalSearchView',
    'OrderDetailView',
    'OrderStatusUpdateView',
    'PanelLoginView',
    'PanelLogoutView',
    'PanelPasswordChangeView',
    'PanelProfileView',
    'ResourceCreateView',
    'ResourceDeleteView',
    'ResourceDetailView',
    'ResourceExportView',
    'ResourceListView',
    'ResourceUpdateView',
    'UserSetPasswordView',
    'resource_detail',
]
