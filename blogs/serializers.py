from rest_framework import serializers
from .models import Blog, BlogCategory


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug']


class BlogListSerializer(serializers.ModelSerializer):
    """For blog listing — no full content"""
    category = BlogCategorySerializer(read_only=True)

    class Meta:
        model = Blog
        fields = [
            'id', 'title', 'slug', 'excerpt', 'thumbnail',
            'category', 'read_time', 'is_featured',
            'created_at'
        ]


class BlogDetailSerializer(serializers.ModelSerializer):
    """For single blog — includes full content"""
    category = BlogCategorySerializer(read_only=True)

    class Meta:
        model = Blog
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'thumbnail',
            'category', 'read_time', 'is_featured',
            'meta_title', 'meta_description', 'created_at', 'updated_at'
        ]