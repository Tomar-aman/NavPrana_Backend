from web_content.models import SocialLinks, WebContent
from web_content.serializers import SocialLinksSerializer , WebContentSerializer
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
# Create your views here.

class SocialLinksView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SocialLinksSerializer
    queryset = SocialLinks.objects.all()
    def get(self, request, *args, **kwargs):
        """ Retrieve the active social links.
        """
        social_links = self.get_queryset().filter(is_active=True).first()
        if social_links:
            serializer = self.get_serializer(social_links)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"error": "No active social links found."}, status=status.HTTP_404_NOT_FOUND)

class WebContentView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = WebContentSerializer

    def get_queryset(self):
        return WebContent.objects.filter(is_active=True).order_by('-created_at')

    def get(self, request, *args, **kwargs):
        """ Retrieve all active web content.
        """
        web_contents = self.get_queryset()
        content_type = request.query_params.get('content_type')
        if content_type:
            web_contents = web_contents.filter(content_type=content_type).first()
            serializer = self.get_serializer(web_contents)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({"error": "No active web content found."}, status=status.HTTP_404_NOT_FOUND)