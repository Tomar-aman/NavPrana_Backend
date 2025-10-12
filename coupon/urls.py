from django.urls import path
from .views import ApplyCouponView

app_name = 'coupon'

urlpatterns = [
    path('apply/', ApplyCouponView.as_view(), name='apply_coupon'),
]