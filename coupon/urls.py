from django.urls import path
from .views import (
    ApplyCouponView,
    SpinWheelCheckView,
    SpinWheelSpinView,
    MyCouponsView,
    AdminUserSpinListView,
    AdminResetSpinView,
)

app_name = 'coupon'

urlpatterns = [
    path('apply/', ApplyCouponView.as_view(), name='apply_coupon'),
    path('spin-check/', SpinWheelCheckView.as_view(), name='spin_check'),
    path('spin/', SpinWheelSpinView.as_view(), name='spin'),
    path('my-coupons/', MyCouponsView.as_view(), name='my_coupons'),
    path('admin/spins/', AdminUserSpinListView.as_view(), name='admin_spins'),
    path('admin/reset-spin/', AdminResetSpinView.as_view(), name='admin_reset_spin'),
]