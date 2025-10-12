from django.contrib import admin
from .models import User, UserAddress

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'profile_picture', 'country_code', 'phone_number', 'google_id')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser','phone_verified','email_verified')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_line1', 'city', 'state', 'postal_code', 'country', 'is_default')
    list_filter = ('is_default', 'country')
    search_fields = ('user__email', 'address_line1', 'city', 'state', 'postal_code', 'country')
    ordering = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('user', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country', 'is_default')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('user',)
        return self.readonly_fields