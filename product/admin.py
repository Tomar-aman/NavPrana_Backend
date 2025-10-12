from django.contrib import admin
from .models import Product, ProductImage

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ('created_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'max_quantity', 'available_quantity', 'created_at', 'updated_at')
    list_filter = ('available_quantity', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'description', 'price', 'max_quantity', 'available_quantity')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    inlines = [ProductImageInline]

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image', 'is_feature', 'created_at')
    list_filter = ('is_feature', 'created_at')
    search_fields = ('product__name',)
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('product', 'image', 'is_feature')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

