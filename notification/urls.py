from django.urls import path
from .views import NotificationListView, MarkAsReadView

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/mark-as-read/', MarkAsReadView.as_view(), name='mark-as-read'),
]