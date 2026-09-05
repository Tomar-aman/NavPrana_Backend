"""
Panel URL map.

Static routes are declared before the ``<slug:resource>`` catch-alls so a
resource key can never shadow ``login``, ``search`` or ``activity``. Unknown
resource keys 404 in :class:`~admin_panel.mixins.ResourceViewMixin`.
"""

from django.urls import path

from . import views


app_name = 'admin_panel'

urlpatterns = [
    # Session
    path('login/', views.PanelLoginView.as_view(), name='login'),
    path('logout/', views.PanelLogoutView.as_view(), name='logout'),

    # Overview
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('search/', views.GlobalSearchView.as_view(), name='search'),
    path('activity/', views.ActivityLogView.as_view(), name='activity'),

    # Own account
    path('account/', views.PanelProfileView.as_view(), name='profile'),
    path('account/password/', views.PanelPasswordChangeView.as_view(), name='password_change'),

    # Order-specific action
    path('orders/<int:pk>/status/', views.OrderStatusUpdateView.as_view(), name='order_status'),

    # User-specific action
    path('users/<int:pk>/set-password/', views.UserSetPasswordView.as_view(), name='user_set_password'),

    # Generic resource CRUD
    path('<slug:resource>/', views.resource_list, name='resource_list'),
    path('<slug:resource>/export/', views.ResourceExportView.as_view(), name='resource_export'),
    path('<slug:resource>/new/', views.ResourceCreateView.as_view(), name='resource_add'),
    path('<slug:resource>/<int:pk>/', views.resource_detail, name='resource_detail'),
    path('<slug:resource>/<int:pk>/edit/', views.ResourceUpdateView.as_view(), name='resource_edit'),
    path('<slug:resource>/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),
]
