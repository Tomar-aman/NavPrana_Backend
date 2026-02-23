from django.contrib import admin
from .models import BlogCategory, Blog

@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'slug')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'created_at')
    search_fields = ('title', 'slug', 'excerpt', 'content')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'excerpt', 'content', 'meta_title', 'meta_description', 'thumbnail', 'category', 'is_featured', 'read_time')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )