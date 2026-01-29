from django.db import models
from django.utils.translation import gettext_lazy as _
from config.models import BaseModel
from django.core.validators import MinValueValidator, MaxValueValidator

class Category(BaseModel):
    name = models.CharField(
        _('category name'),
        max_length=100,
        unique=True,
        help_text=_('Enter the category name'),
        db_index=True
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Enter the category description')
    )

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    SIZE_CHOICES = [
        ('500ml', '500 milliliters'),
        ('1L', '1 liter'),
    ]
    name = models.CharField(
        _('product name'),
        max_length=255,
        help_text=_('Enter the product name'),
        db_index=True,
        null=True,
        blank=True

    )
    size = models.CharField(
        _('size'),
        max_length=50,
        blank=True,
        choices=SIZE_CHOICES,
        help_text=_('Enter the product size')
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
        verbose_name=_('category'),
        help_text=_('Select the category for this product')
    )
    details = models.TextField(
        _('product details'),
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
    max_price = models.DecimalField(
        _('maximum price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Enter the maximum retail price of the product'),
        null=True,
        blank=True
    )
    discount_precent = models.DecimalField(
        _('discount percent'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Enter the discount percentage for the product')
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
        if self.discount_precent < 0 or self.discount_precent > 100:
            raise ValueError(_("Discount percent must be between 0 and 100"))
        self.price = round(self.max_price - (self.max_price * self.discount_precent / 100))
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

class ProductReview(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('product')
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='product_reviews',
        verbose_name=_('user')
    )
    rating = models.PositiveIntegerField(
        _('rating'),
        help_text=_('Enter a rating between 1 and 5'),
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )
    review = models.TextField(
        _('review'),
        blank=True,
        help_text=_('Write your review here')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('product review')
        verbose_name_plural = _('product reviews')
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f'Review by {self.user.email} for {self.product.name}'


class ProductFeature(BaseModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='features',
        verbose_name=_('product')
    )
    feature = models.CharField(
        _('feature name'),
        max_length=100,
        help_text=_('Enter the feature name')
    )
    class Meta:
        verbose_name = _('product feature')
        verbose_name_plural = _('product features')
        ordering = ['feature']

    def __str__(self):
        return f'{self.feature}'
    
class ProductSpecification(BaseModel):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name=_('product')
    )
    specification = models.TextField(
        _('specification name'),
        help_text=_('Enter the specification name')
    )
    class Meta:
        verbose_name = _('product specification')
        verbose_name_plural = _('product specifications')
        ordering = ['specification']

    def __str__(self):
        return f'{self.pk}'