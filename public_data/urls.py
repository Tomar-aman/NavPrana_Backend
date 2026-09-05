# urls.py (in the social app)

from django.urls import path
from .views import InstagramReelListView, PricingSettingsView

urlpatterns = [
    path("reels/", InstagramReelListView.as_view(), name="instagram-reels"),
    path("pricing/", PricingSettingsView.as_view(), name="public-pricing"),
]
