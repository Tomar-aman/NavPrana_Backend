from django.db import models
from orders.models import Order
from django.utils.translation import gettext_lazy as _
from users.models import User


class TransactionLog(models.Model):
    PAYMENT_METHODS = (
        ('phonepe', 'PhonePe'),
        ('cashfree', 'Cashfree'),
        ('stripe', 'Stripe'),
        ('upi', 'UPI'),
        ('card', 'Card'),
        ('netbanking', 'Net Banking'),
    )
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_INSTRUMENT_TYPES = (
        ('UPI', 'UPI'),
        ('CARD', 'Card'),
        ('NETBANKING', 'Net Banking'),
        ('WALLET', 'Wallet'),
        ('PAY_PAGE', 'Pay Page'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transaction_logs',
        verbose_name=_('User')
    )
    
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE,
        related_name='transaction_logs',
        verbose_name=_('Order')
    )
    
    payment_method = models.CharField(
        _('Payment Method'),
        max_length=20,
        choices=PAYMENT_METHODS,
        default='phonepe'
    )
    
    payment_instrument_type = models.CharField(
        _('Payment Instrument Type'),
        max_length=20,
        choices=PAYMENT_INSTRUMENT_TYPES,
        blank=True,
        null=True,
        help_text=_('Type of payment instrument used')
    )
    
    amount = models.DecimalField(
        _('Amount'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Amount in INR')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='INR'
    )
    
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Transaction status')
    )
    
    transaction_order_id = models.CharField(
        _('Transaction Order ID'),
        max_length=255,
        unique=True,
        null=True,  # Temporarily nullable for migration
        blank=True,
        db_index=True,
        help_text=_('Our internal order/transaction reference (e.g., NAV_ORDER_16_xxx)')
    )
    
    gateway_payment_id = models.CharField(
        _('Gateway Payment ID'),
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text=_('Payment gateway internal payment ID (PhonePe/Cashfree transaction ID)')
    )
    
    # Cashfree specific fields
    cashfree_order_id = models.CharField(
        _('Cashfree Order ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Cashfree internal order ID (cf_order_id)')
    )
    
    payment_session_id = models.CharField(
        _('Payment Session ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Cashfree payment session ID')
    )
    
    order_token = models.TextField(
        _('Order Token'),
        blank=True,
        null=True,
        help_text=_('Cashfree order token for SDK integration')
    )
    
    payment_group = models.CharField(
        _('Payment Group'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('Payment group (credit_card, upi, net_banking, etc.)')
    )
    
    bank_reference = models.CharField(
        _('Bank Reference'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Bank reference number')
    )
    
    auth_id = models.CharField(
        _('Auth ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Payment gateway authorization ID')
    )
    
    payment_details = models.JSONField(
        _('Payment Details'),
        default=dict,
        blank=True,
        help_text=_('Complete gateway response for audit trail')
    )
    
    error_message = models.TextField(
        _('Error Message'),
        blank=True,
        null=True
    )
    
    upi_id = models.CharField(
        _('UPI ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('UPI ID used for payment')
    )
    
    card_type = models.CharField(
        _('Card Type'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('Type of card used (DEBIT/CREDIT)')
    )
    
    card_network = models.CharField(
        _('Card Network'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('Card network (VISA, MASTERCARD, etc.)')
    )
    
    bank_name = models.CharField(
        _('Bank Name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Bank used for payment')
    )
    
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('Transaction Log')
        verbose_name_plural = _('Transaction Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_order_id']),
            models.Index(fields=['gateway_payment_id']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['cashfree_order_id']),
        ]

    def __str__(self):
        return f"{self.get_payment_method_display()} - {self.transaction_order_id} - {self.status}"
    
    @classmethod
    def create_transaction(cls, order, order_id, amount, payment_method='phonepe'):
        """
        Create a transaction log
        
        Args:
            order: Order instance
            order_id: Our internal order/transaction ID
            amount: Transaction amount
            payment_method: Payment gateway (phonepe, cashfree, stripe)
            
        Returns:
            TransactionLog instance
        """
        return cls.objects.create(
            user=order.user,
            order=order,
            payment_method=payment_method,
            amount=amount,
            transaction_order_id=order_id,
            status='pending'
        )
    
    @classmethod
    def create_cashfree_transaction(cls, order, order_id, amount, cashfree_order_id, 
                                   payment_session_id, order_token):
        """
        Create a Cashfree transaction log
        
        Args:
            order: Order instance
            order_id: Our internal order ID (e.g., NAV_ORDER_16_xxx)
            amount: Transaction amount
            cashfree_order_id: Cashfree's internal order ID (cf_order_id)
            payment_session_id: Payment session ID
            order_token: Order token for SDK
            
        Returns:
            TransactionLog instance
        """
        return cls.objects.create(
            user=order.user,
            order=order,
            payment_method='cashfree',
            amount=amount,
            transaction_order_id=order_id,
            cashfree_order_id=cashfree_order_id,
            payment_session_id=payment_session_id,
            order_token=order_token,
            status='pending'
        )
    
    def mark_as_success(self, phonepe_response):
        """
        Mark transaction as successful (PhonePe)
        
        Args:
            phonepe_response: Response dict from PhonePe
        """
        self.status = 'success'
        self.gateway_payment_id = phonepe_response.get('transactionId')
        
        # Extract payment instrument details
        payment_instrument = phonepe_response.get('paymentInstrument', {})
        self.payment_instrument_type = payment_instrument.get('type')
        
        if self.payment_instrument_type == 'UPI':
            self.upi_id = payment_instrument.get('utr')
        elif self.payment_instrument_type == 'CARD':
            self.card_type = payment_instrument.get('cardType')
            self.card_network = payment_instrument.get('cardNetwork')
        elif self.payment_instrument_type == 'NETBANKING':
            self.bank_name = payment_instrument.get('bankId')
        
        self.payment_details = phonepe_response
        self.save()
        
        # Update order
        self.order.mark_as_paid(self.transaction_order_id)
        
        # Record coupon usage
        if self.order.coupon:
            coupon = self.order.coupon
            coupon.used += 1
            coupon.save()
            coupon.record_usage(self.order.user)
        
        # Clear user's cart after successful payment
        if self.user:
            from cart.models import Cart
            Cart.objects.filter(user=self.user).delete()
    
    def mark_cashfree_success(self, cashfree_response):
        """
        Mark Cashfree transaction as successful
        
        Args:
            cashfree_response: Response dict from Cashfree webhook/API
        """
        self.status = 'success'

        # Cashfree webhook structure expected:
        # {
        #   'order': {...},
        #   'payment': {
        #       'cf_payment_id': '...',
        #       'payment_group': 'upi'|'debit_card'|'credit_card'|'net_banking'|'wallet',
        #       'bank_reference': '...',
        #       'auth_id': '...',
        #       'payment_method': { 'card'| 'upi' | 'netbanking' | 'wallet': {...} },
        #       ...
        #   }
        # }
        payment_info = cashfree_response.get('payment', {}) or {}

        self.gateway_payment_id = payment_info.get('cf_payment_id')
        self.payment_group = payment_info.get('payment_group')
        self.bank_reference = payment_info.get('bank_reference')
        self.auth_id = payment_info.get('auth_id')

        method_detail = payment_info.get('payment_method') or {}

        # Reset instrument-specific fields
        self.payment_instrument_type = None
        self.upi_id = None
        self.card_type = None
        self.card_network = None
        self.bank_name = None

        # Derive method and instrument type from payment_group/method_detail
        pg = (self.payment_group or '').lower() if self.payment_group else ''
        derived_payment_method = 'cashfree'
        derived_instrument_type = None

        if 'upi' in pg or 'upi' in method_detail:
            derived_payment_method = 'upi'
            derived_instrument_type = 'UPI'
            upi_obj = method_detail.get('upi') if isinstance(method_detail, dict) else None
            if isinstance(upi_obj, dict):
                self.upi_id = (
                    upi_obj.get('upi_vpa')
                    or upi_obj.get('vpa')
                    or upi_obj.get('upi_id')
                )
        elif 'card' in pg or 'card' in method_detail:
            derived_payment_method = 'card'
            derived_instrument_type = 'CARD'
            card_obj = method_detail.get('card') if isinstance(method_detail, dict) else None
            if isinstance(card_obj, dict):
                # Cashfree sends card_type like 'debit_card' / 'credit_card'
                self.card_type = (
                    card_obj.get('card_type')
                    or ('debit' if 'debit' in pg else 'credit' if 'credit' in pg else None)
                )
                self.card_network = card_obj.get('card_network')
                self.bank_name = card_obj.get('card_bank_name')
        elif 'net' in pg and 'bank' in pg or 'netbanking' in method_detail:
            derived_payment_method = 'netbanking'
            derived_instrument_type = 'NETBANKING'
            nb_obj = method_detail.get('netbanking') if isinstance(method_detail, dict) else None
            if isinstance(nb_obj, dict):
                self.bank_name = nb_obj.get('bank_name') or nb_obj.get('bank_code')
        elif 'wallet' in pg or 'wallet' in method_detail:
            derived_payment_method = 'cashfree'
            derived_instrument_type = 'WALLET'

        self.payment_method = derived_payment_method
        self.payment_instrument_type = derived_instrument_type

        # Store complete response for audit
        self.payment_details = cashfree_response
        self.save()

        # Update order
        self.order.mark_as_paid(self.transaction_order_id)

        # Record coupon usage
        if self.order.coupon:
            coupon = self.order.coupon
            coupon.used += 1
            coupon.save()
            coupon.record_usage(self.order.user)
        
        # Clear user's cart after successful payment
        if self.user:
            from cart.models import Cart
            Cart.objects.filter(user=self.user).delete()
    
    def mark_as_failed(self, error_message=None):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
        
        # Update order
        self.order.mark_as_failed()
    
    def mark_as_refunded(self, refund_transaction_id):
        """Mark transaction as refunded"""
        self.status = 'refunded'
        self.payment_details['refund_transaction_id'] = refund_transaction_id
        self.save()
        
        # Update order
        self.order.payment_status = 'refunded'
        self.order.save()