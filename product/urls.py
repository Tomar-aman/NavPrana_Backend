from django.urls import path
from .views import ProductListView, ProductDetailView ,ProductReviewCreateView, ProductReviewListView, ProductReviewDetailView

app_name = 'product'

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('reviews/',ProductReviewCreateView.as_view(),name='product-review-create'), 
    path('<int:product_id>/reviews/',
        ProductReviewListView.as_view(),
        name='product-review-list'
    ),
    path(
        'reviews/<int:pk>/',
        ProductReviewDetailView.as_view(),
        name='product-review-detail'
    ),
]