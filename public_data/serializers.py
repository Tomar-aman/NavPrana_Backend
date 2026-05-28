# serializers.py

from rest_framework import serializers
from .models import InstagramReel


class InstagramReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramReel
        fields = ["id", "instagram_url", "thumbnail", "caption", "sort_order", "created_at"]
