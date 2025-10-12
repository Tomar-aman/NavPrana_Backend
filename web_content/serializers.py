from rest_framework import serializers
from web_content.models import SocialLinks, WebContent


class SocialLinksSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLinks
        fields = ['twitter', 'instagram', 'linkedin', 'facebook']

class WebContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebContent
        fields = ['content_type', 'title', 'content']