from django.contrib import admin
from .models import Coupon, CouponUsage

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'coupon_id', 'coupon_code', 'amount', 'percent',
        'start_date', 'end_date', 'used', 'max_use', 'status'
    ]
    list_filter = ['status', 'start_date', 'end_date']
    search_fields = ['coupon_id', 'coupon_code']
    readonly_fields = ['coupon_id', 'used', 'created_at', 'updated_at']
    list_editable = ['status']
    
    fieldsets = (
        ('Coupon Information', {
            'fields': ('coupon_code', 'coupon_id','minimum_cart_amount','discount_type')
        }),
        ('Discount Details', {
            'fields': ('amount', 'percent')
        }),
        ('Validity Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Usage Limits', {
            'fields': ('max_use', 'used', 'uses_per_user')
        }),
        ('Status', {
            'fields': ('status','free_shipping')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_delete_permission(self, request, obj=None):
        if obj and obj.used > 0:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.used > 0:
            return self.readonly_fields + ['max_use']
        return self.readonly_fields

@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'coupon' ]
    search_fields = ['user__full_name', 'coupon__coupon_code']
    readonly_fields = ['id', 'user', 'coupon', 'first_used_at', 'last_used_at']
    list_filter = ['coupon', 'user']
    fieldsets = (
        ('Usage Information', {
            'fields': ('user', 'coupon', 'used_count')
        }),
        ('Timestamps', {
            'fields': ('first_used_at', 'last_used_at'),
            'classes': ('collapse',)
        }),
    )