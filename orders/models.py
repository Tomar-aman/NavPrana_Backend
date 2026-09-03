from django.db import models, transaction
from decimal import Decimal
from config import settings
from django.utils.translation import gettext_lazy as _
from coupon.models import Coupon
from product.models import Product
from users.models import UserAddress
from .couriers import COURIER_CHOICES, build_tracking_url, get_courier

class Order(models.Model):
    COD_HANDLING_FEE = Decimal('49.00')
    SHIPPING_FEE = Decimal('50.00')
    # Orders above this subtotal ship free (see the public Shipping Policy page)
    FREE_SHIPPING_THRESHOLD = Decimal('599.00')

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

    PAYMENT_METHOD_CHOICES = (
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('card', 'Card Payment'),
        ('cod', 'Cash on Delivery'),
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
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='upi',
        help_text=_('Payment method selected for this order'),
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

    shipping_fee = models.DecimalField(
        _('shipping fee'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text=_('Shipping charge applied to this order')
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

    # --- Shipping / tracking (filled in by staff from the admin) ---
    courier = models.CharField(
        _('courier'),
        max_length=32,
        choices=COURIER_CHOICES,
        blank=True,
        help_text=_('Shipping partner carrying this order')
    )
    awb_number = models.CharField(
        _('AWB / tracking number'),
        max_length=64,
        blank=True,
        help_text=_('Tracking number printed on the shipping label'),
        db_index=True
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
            return round((self.total_amount * self.coupon.percent) / 100)
        else:
            return self.coupon.amount
    
    def calculate_tax(self):
        """Calculate tax amount"""
        if self.tax_percentage:
            discounted_amount = self.total_amount - self.discount_amount
            return round((discounted_amount * self.tax_percentage) / 100)        
        return 0
    
    def calculate_shipping(self):
        """
        Shipping charge for this order.

        Free on an empty cart, above FREE_SHIPPING_THRESHOLD, or when the
        applied coupon grants free shipping. Otherwise a flat SHIPPING_FEE.
        """
        if self.total_amount <= 0:
            return Decimal('0.00')
        if self.total_amount > self.FREE_SHIPPING_THRESHOLD:
            return Decimal('0.00')
        if self.coupon_id and getattr(self.coupon, 'free_shipping', False):
            return Decimal('0.00')
        return self.SHIPPING_FEE

    def calculate_final_amount(self):
        """Calculate final amount after discount, shipping and fees"""
        amount_after_discount = self.total_amount - self.discount_amount
        final = Decimal(str(round(amount_after_discount)))

        final += self.shipping_fee
        final += self.get_handling_fee()

        # final = amount_after_discount + self.tax_amount
        return max(final, Decimal('0.00'))

    def get_handling_fee(self):
        """Return handling fee based on payment method."""
        if self.payment_method == 'cod':
            return self.COD_HANDLING_FEE
        return Decimal('0.00')

    @property
    def courier_label(self):
        """Display name of the shipping partner, e.g. 'Delhivery'."""
        return get_courier(self.courier)['label'] if self.courier else ''

    @property
    def tracking_url(self):
        """Courier's own tracking page for this AWB, or '' if unavailable."""
        return build_tracking_url(self.courier, self.awb_number)

    def save(self, *args, **kwargs):
        if self.awb_number:
            self.awb_number = self.awb_number.strip().upper()

        # Calculate discount
        self.discount_amount = self.calculate_discount()
        
        # Calculate tax
        self.tax_amount = self.calculate_tax()

        # Calculate shipping (must run before final amount)
        self.shipping_fee = self.calculate_shipping()

        # Calculate final amount
        self.final_amount = self.calculate_final_amount()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def create_order(
        cls,
        user,
        address,
        products_data,
        coupon_code=None,
        tax_percentage=None,
        notes=None,
        payment_method='upi',
        initial_status='pending'
    ):
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
                from coupon.models import TempCoupon
                try:
                    temp = TempCoupon.objects.get(coupon_code=coupon_code, user=user, is_used=False)
                    # Convert TempCoupon to a permanent database Coupon to satisfy the Order ForeignKey schema
                    if temp.coupon_code.startswith("NAV-FREE500-"):
                        from cart.models import Cart
                        cart_items = Cart.objects.filter(user=user, product__size='500ml')
                        discount_val = cart_items.first().product.price if cart_items.exists() else Decimal('1119.00')
                        applied_coupon = Coupon.objects.create(
                            coupon_code=coupon_code,
                            discount_type='amount',
                            amount=discount_val,
                            max_use=1,
                            uses_per_user=1,
                            status=True
                        )
                    else:
                        applied_coupon = Coupon.objects.create(
                            coupon_code=coupon_code,
                            discount_type=temp.discount_type,
                            amount=temp.amount,
                            percent=temp.percent,
                            free_shipping=temp.free_shipping,
                            max_use=1,
                            uses_per_user=1,
                            status=True
                        )
                    # Mark temp coupon as used
                    temp.is_used = True
                    temp.save()
                except TempCoupon.DoesNotExist:
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
            tax_percentage=tax_percentage or Decimal('5.00'), # Default tax percentage 5% if not provided
            notes=notes,
            status=initial_status or 'pending',
            payment_status='pending',
            payment_method=payment_method or 'cashfree'
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
        # Payment webhooks are retried by the gateway, so this can run more than
        # once for the same order. Read the stored status before overwriting it
        # so the customer emails only go out on the first successful call.
        already_paid = self.pk and Order.objects.filter(
            pk=self.pk, payment_status='paid'
        ).exists()

        self.payment_status = 'paid'
        self.status = 'accepted'
        self.transaction_id = transaction_id
        
        self.save()
        
        # Generate invoice PDF
        self.generate_invoice()

        if not already_paid:
            self.send_payment_emails(transaction_id)
        
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
    
    def send_payment_emails(self, transaction_id):
        """Queue the payment confirmation and invoice emails for this order."""
        from orders.tasks import send_payment_success_email, send_invoice_email

        order_id = self.pk

        def _dispatch():
            send_payment_success_email.delay(order_id, transaction_id)
            send_invoice_email.delay(order_id)

        transaction.on_commit(_dispatch)

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
    
    def generate_invoice(self):
        """Generate and save invoice PDF"""
        try:
            from .invoice_utils import generate_invoice_pdf
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Skip if invoice already exists
            if self.invoice:
                logger.info(f'Invoice already exists for order {self.id}')
                return True
            
            # Generate PDF
            pdf_file = generate_invoice_pdf(self)
            
            # Save to order
            self.invoice.save(pdf_file.name, pdf_file, save=True)
            
            logger.info(f'Invoice generated and saved for order {self.id}')
            return True
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to generate invoice for order {self.id}: {str(e)}', exc_info=True)
            return False


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
    total_price = models.DecimalField(
        _('total price'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('Total price for this item (price * quantity)')
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
        self.total_price = self.price * self.quantity
        super().save(*args, **kwargs)

