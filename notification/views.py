from .serializers import NotificationSerializer, NotificationReadSerializer
from .models import Notification 
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status

class NotificationListView(GenericAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get(self, request, *args, **kwargs):
        notifications = self.get_queryset()
        serializer = self.get_serializer(notifications, many=True)

        # calculate unread count
        unread_count = notifications.filter(is_read=False).count()

        return Response({
            "notifications": serializer.data,
            "unread_count": unread_count
        }, status=status.HTTP_200_OK)

class MarkAsReadView(GenericAPIView):
    serializer_class = NotificationReadSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)
        message = "All notifications marked as read."
        return Response({"message": message}, status=status.HTTP_200_OK)