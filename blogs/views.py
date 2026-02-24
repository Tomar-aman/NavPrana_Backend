from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from .models import Blog, BlogCategory
from .serializers import BlogListSerializer, BlogDetailSerializer, BlogCategorySerializer
from rest_framework.permissions import AllowAny

class BlogListView(GenericAPIView):
    """GET /api/v1/blogs/"""
    serializer_class = BlogListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Blog.objects.filter(
            is_active=True
        ).select_related('category')

    def get(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BlogDetailView(GenericAPIView):
    """GET /api/v1/blogs/<slug>/"""
    serializer_class = BlogDetailSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]
    def get_queryset(self):
        return Blog.objects.filter(is_active=True)

    def get(self, request, slug):
        blog = self.get_object()
        serializer = self.get_serializer(blog)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BlogCategoryListView(GenericAPIView):
    """GET /api/v1/blogs/categories/"""
    serializer_class = BlogCategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return BlogCategory.objects.filter(is_active=True)

    def get(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)