from django.contrib import admin
from django.contrib.admin.widgets import AdminSplitDateTime
from django import forms
from .models import Product, ProductImage, Category, ProductReview, ProductFeature, ProductSpecification , ProductReviewMedia

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'description')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1
    readonly_fields = ('created_at',)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ('created_at',)

class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1
    readonly_fields = ('created_at',)

class ProductReviewMediaInline(admin.TabularInline):
    model = ProductReviewMedia
    extra = 1
    readonly_fields = ('created_at',)

class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 1
    readonly_fields = ('created_at',)


class ProductReviewAdminForm(forms.ModelForm):
    created_at = forms.SplitDateTimeField(widget=AdminSplitDateTime)
    updated_at = forms.SplitDateTimeField(widget=AdminSplitDateTime)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['created_at'] = self.instance.created_at
            self.initial['updated_at'] = self.instance.updated_at

    class Meta:
        model = ProductReview
        fields = ('product', 'user', 'rating', 'review')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'size', 'category', 'price', 'max_quantity', 'available_quantity', 'created_at', 'updated_at')
    list_filter = ('available_quantity', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'size', 'category', 'description', 'details', 'price','max_price', 'discount_precent', 'max_quantity', 'available_quantity')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    inlines = [ProductImageInline, ProductFeatureInline, ProductSpecificationInline, ProductReviewInline]

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


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    form = ProductReviewAdminForm
    list_display = ('product', 'user', 'rating', 'created_at', 'updated_at')
    list_filter = ('rating', 'created_at', 'updated_at')
    search_fields = ('product__name', 'user__email', 'review_text')
    ordering = ('-created_at',)
    inlines = [ProductReviewMediaInline]

    def get_form(self, request, obj=None, change=False, **kwargs):
        fields = kwargs.get('fields')
        if fields is None:
            fields = ('product', 'user', 'rating', 'review')
        else:
            fields = tuple(
                field for field in fields
                if field not in ('created_at', 'updated_at')
            )
        kwargs['fields'] = fields
        return super().get_form(request, obj, change, **kwargs)

    def save_model(self, request, obj, form, change):
        timestamps = {
            'created_at': form.cleaned_data['created_at'],
            'updated_at': form.cleaned_data['updated_at'],
        }
        super().save_model(request, obj, form, change)
        ProductReview.objects.filter(pk=obj.pk).update(**timestamps)
        obj.created_at = timestamps['created_at']
        obj.updated_at = timestamps['updated_at']

@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'specification', 'created_at')
    search_fields = ('product__name', 'specification')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('product', 'specification')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

@admin.register(ProductReviewMedia)
class ProductReviewMediaAdmin(admin.ModelAdmin):
    list_display = ('review', 'media_type', 'file', 'created_at')
    list_filter = ('media_type', 'created_at')
    search_fields = ('review__product__name', 'review__user__email')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('review', 'media_type', 'file', 'alt_text')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )

@admin.register(ProductFeature)
class ProductFeatureAdmin(admin.ModelAdmin):
    list_display = ('product', 'feature', 'created_at')
    search_fields = ('product__name', 'feature')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('product', 'feature')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
