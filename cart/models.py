from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import User
from product.models import Product

class Cart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='carts',
        verbose_name=_('User'),
        help_text=_('The user to whom this cart belongs')
    )
    products = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='carts',
        verbose_name=_('Products'),
        help_text=_('Products in the cart')
    )
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Quantity'),
        help_text=_('Quantity of the product in the cart'),
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('The date and time when the cart was created')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
        help_text=_('The date and time when the cart was last updated')
    )

    class Meta:
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        ordering = ['-created_at']

    def __str__(self):
        return f"Cart of {self.user.email} - Created at {self.created_at}"