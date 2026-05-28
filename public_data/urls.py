# urls.py (in the social app)

from django.urls import path
from .views import InstagramReelListView

urlpatterns = [
    path("reels/", InstagramReelListView.as_view(), name="instagram-reels"),
]
