# from django_filters import rest_framework as filters
# from .models import Product
# from django.db import models
# class ProductFilter(filters.FilterSet):
#     min_price = filters.NumberFilter(field_name='price', lookup_expr='gte')
#     max_price = filters.NumberFilter(field_name='price', lookup_expr='lte')
#     name = filters.CharFilter(method='filter_name')

#     def filter_name(self, queryset, name, value):
#         return queryset.filter(
#             models.Q(name__icontains=value)
#         )

#     class Meta:
#         model = Product
#         fields = ['min_price', 'max_price', 'is_active']