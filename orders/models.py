from django.db import models
from config import settings
from django.utils.translation import gettext_lazy as _
from coupon.models import Coupon
from product.models import Product
from users.models import UserAddress

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('processing', 'Processing'),
        ('failed', 'Failed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name=_('user'),
        help_text=_('User who placed the order')
    )
    address = models.ForeignKey(
        UserAddress,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders',
        verbose_name=_('address'),
    )
 
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Current status of the order'),
        db_index=True
    )

    total_amount = models.DecimalField(
        _('total amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Total amount of the order')
    )
    
    notes = models.TextField(
        _('notes'),
        blank=True,
        null=True,
        help_text=_('Additional notes for the order')
    )
    
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name=_('coupon'),
        help_text=_('Coupon applied to this order')
    )
    
    discount_amount = models.DecimalField(
        _('discount amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Calculated discount amount from coupon')
    )
    
    payment_status = models.CharField(
        _('payment status'),
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        help_text=_('Current payment status of the order'),
        db_index=True
    )
    tax_percentage = models.DecimalField(
        _('tax percentage'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        null=True,
        blank=True,
        help_text=_('Percentage of tax to be applied')
    )
    
    tax_amount = models.DecimalField(
        _('tax amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Calculated tax amount')
    )
    
    final_amount = models.DecimalField(
        _('final amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Final amount after discount and tax')
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
    
    transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        help_text=_('Unique identifier for the payment transaction')
    )
    
    invoice = models.FileField(
        _('invoice'),
        upload_to='invoices/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Generated invoice PDF for this order')
    )
    
    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.id} - {self.user.username} - ₹{self.final_amount} - {self.status}"
    
    def calculate_discount(self):
        """Calculate discount amount based on coupon"""
        if not self.coupon:
            return 0
        if self.coupon.percent > 0:
            return (self.total_amount * self.coupon.percent) / 100
        else:
            return self.coupon.amount
    
    def calculate_tax(self):
        """Calculate tax amount"""
        if self.tax_percentage:
            discounted_amount = self.total_amount - self.discount_amount
            return (discounted_amount * self.tax_percentage) / 100
        return 0
    
    def calculate_final_amount(self):
        """Calculate final amount after discount and tax"""
        amount_after_discount = self.total_amount - self.discount_amount
        final = amount_after_discount + self.tax_amount
        return max(final, 0)
    
    def save(self, *args, **kwargs):
        # Calculate discount
        self.discount_amount = self.calculate_discount()
        
        # Calculate tax
        self.tax_amount = self.calculate_tax()
        
        # Calculate final amount
        self.final_amount = self.calculate_final_amount()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def create_order(cls, user, address, products_data, coupon_code=None, tax_percentage=None, notes=None):
        """
        Class method to create an order with items
        
        Args:
            user: User instance
            products_data: List of dicts [{'product_id': 1, 'quantity': 2}, ...]
            coupon_code: Optional coupon code string
            tax_percentage: Optional tax percentage
            notes: Optional order notes
            
        Returns:
            Order instance
        """
        from decimal import Decimal
        
        # Calculate total from products
        total_amount = Decimal('0.00')
        order_items_data = []
        
        for item_data in products_data:
            product = Product.objects.get(id=item_data['product_id'])
            quantity = item_data['quantity']
            item_total = product.price * quantity
            total_amount += item_total
            order_items_data.append({
                'product': product,
                'quantity': quantity,
                'price': product.price
            })
        
        # Get coupon if provided
        applied_coupon = None
        if coupon_code:
            try:
                applied_coupon = Coupon.objects.get(coupon_code=coupon_code)
            except Coupon.DoesNotExist:
                raise ValueError("Invalid coupon code")
        
        # Resolve address
        if isinstance(address, int):
            shipping_address = user.addresses.get(id=address)
        elif address:
            shipping_address = address
        else:
            shipping_address = user.addresses.filter(is_default=True).first()
            
        if not shipping_address:
            raise ValueError("No valid address found for order")
        
        # Create order
        order = cls.objects.create(
            user=user,
            address=shipping_address,
            total_amount=total_amount,
            coupon=applied_coupon,
            tax_percentage=tax_percentage or Decimal('0.00'),
            notes=notes,
            status='pending',
            payment_status='pending'
        )
        
        # Create order items
        for item_data in order_items_data:
            OrderItem.objects.create(
                order=order,
                product=item_data['product'],
                quantity=item_data['quantity'],
                price=item_data['price']
            )
        
        return order
    
    def mark_as_paid(self, transaction_id):
        """Mark order as paid and generate invoice"""
        self.payment_status = 'paid'
        self.status = 'accepted'
        self.transaction_id = transaction_id
        
        self.save()
        
        # Record coupon usage if not already recorded
        if self.coupon:
            from coupon.models import CouponUsage
            usage, created = CouponUsage.objects.get_or_create(
                coupon=self.coupon,
                user=self.user
            )
            # Only increment if this is the first time marking as paid
            if not created and usage.used_count == 0:
                self.coupon.used += 1
                self.coupon.save()
                self.coupon.record_usage(self.user)
            elif created:
                self.coupon.used += 1
                self.coupon.save()
                self.coupon.record_usage(self.user)
    
    def mark_as_failed(self):
        """Mark order as failed"""
        self.payment_status = 'failed'
        self.status = 'failed'
        self.save()
    
    def mark_as_completed(self):
        """Mark order as completed"""
        self.status = 'completed'
        self.save()
    
    def mark_as_shipped(self):
        """Mark order as shipped"""
        self.status = 'shipped'
        self.save()
    
    def mark_as_delivered(self):
        """Mark order as delivered"""
        self.status = 'delivered'
        self.save()


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('order'),
        help_text=_('Order this item belongs to')
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name=_('product'),
        help_text=_('Product being ordered')
    )
    quantity = models.PositiveIntegerField(
        _('quantity'),
        default=1,
        help_text=_('Quantity of the product')
    )
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Price of the product at time of order')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('order item')
        verbose_name_plural = _('order items')
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order #{self.order.id}"

    def save(self, *args, **kwargs):
        if self.quantity < 1:
            raise ValueError(_("Quantity must be positive"))
        super().save(*args, **kwargs)