from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
# from django_filters import rest_framework as filters
from .models import Product
from .serializers import ProductSerializer
# from .filters import ProductFilter
from rest_framework.response import Response
from rest_framework import status


class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    # filter_backends = [filters.DjangoFilterBackend, SearchFilter, OrderingFilter]
    # filterset_class = ProductFilter
    search_fields = ['name', 'description',]
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']



class ProductDetailView(RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'

