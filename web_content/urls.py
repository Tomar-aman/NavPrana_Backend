from django.urls import path
from . import views

urlpatterns = [
    path('social-links/', views.SocialLinksView.as_view(), name='get_social_links'),
    path('', views.WebContentView.as_view(), name='get_web_content'),
]