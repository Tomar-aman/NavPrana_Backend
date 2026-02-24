from django.urls import path
from .views import BlogListView, BlogDetailView, BlogCategoryListView

urlpatterns = [
    path('', BlogListView.as_view(), name='blog-list'),
    path('categories/', BlogCategoryListView.as_view(), name='blog-categories'),
    path('<slug:slug>/', BlogDetailView.as_view(), name='blog-detail'),
]