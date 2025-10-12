from django.db import models
from django.utils.translation import gettext_lazy as _

class Product(models.Model):
    name = models.CharField(
        _('product name'),
        max_length=255,
        help_text=_('Enter the product name'),
        db_index=True,
        null=True,
        blank=True

    )
    details = models.CharField(
        _('product details'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Enter the product details')
    )
    description = models.TextField(
        _('description'),
        blank=True,
        null=True,
        help_text=_('Enter the product description')
    )
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Enter the product price')
    )
    max_quantity = models.PositiveIntegerField(
        _('maximum quantity'),
        default=25,
        help_text=_('Enter the maximum quantity available for the product') 
    )
    available_quantity = models.PositiveIntegerField(
        _('available quantity'),
        help_text=_('Enter the available quantity for the product')
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Designates whether this product should be treated as active')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
        db_index=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name or str(self.id)
        
    def save(self, *args, **kwargs):
        if self.price < 0:
            raise ValueError(_("Price cannot be negative"))
        if self.available_quantity < 0:
            raise ValueError(_("Available quantity cannot be negative"))
        if self.available_quantity > self.max_quantity:
            raise ValueError(_("Available quantity cannot exceed maximum quantity"))
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('product')
    )
    image = models.ImageField(
        _('image'),
        upload_to='products/%Y/%m/%d/',
        help_text=_('Upload a product image')
    )
    alt_text = models.CharField(
        _('alternative text'),
        max_length=255,
        blank=True,
        help_text=_('Alternative text for image accessibility')
    )
    is_feature = models.BooleanField(
        _('feature image'),
        default=False,
        help_text=_('Set this image as a feature image')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('product image')
        verbose_name_plural = _('product images')
        ordering = ['-created_at']

    def __str__(self):
        return f'Image for {self.product.name}'
