from django.urls import path
from .views import ProductListView, ProductDetailView

app_name = 'product'

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
]