from django.db import models
from orders.models import Order
from django.utils.translation import gettext_lazy as _
from users.models import User


class TransactionLog(models.Model):
    PAYMENT_METHODS = (
        ('phonepe', 'PhonePe'),
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
    
    transaction_id = models.CharField(
        _('Transaction ID'),
        max_length=255,
        unique=True,
        help_text=_('PhonePe transaction reference')
    )
    
    merchant_transaction_id = models.CharField(
        _('Merchant Transaction ID'),
        max_length=255,
        unique=True,
        help_text=_('Our internal transaction reference')
    )
    
    phonepe_transaction_id = models.CharField(
        _('PhonePe Transaction ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('PhonePe internal transaction ID')
    )
    
    payment_details = models.JSONField(
        _('Payment Details'),
        default=dict,
        help_text=_('Additional PhonePe response details')
    )
    
    response_code = models.CharField(
        _('Response Code'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('PhonePe response code')
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
            models.Index(fields=['transaction_id']),
            models.Index(fields=['merchant_transaction_id']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.get_payment_method_display()} - {self.merchant_transaction_id} - {self.status}"
    
    @classmethod
    def create_transaction(cls, order, transaction_id, amount):
        """
        Class method to create a transaction log
        
        Args:
            order: Order instance
            transaction_id: Merchant transaction ID
            amount: Transaction amount
            
        Returns:
            TransactionLog instance
        """
        return cls.objects.create(
            user=order.user,
            order=order,
            payment_method='phonepe',
            amount=amount,
            transaction_id=transaction_id,
            merchant_transaction_id=transaction_id,
            status='pending'
        )
    
    def mark_as_success(self, phonepe_response):
        """
        Mark transaction as successful
        
        Args:
            phonepe_response: Response dict from PhonePe
        """
        self.status = 'success'
        self.phonepe_transaction_id = phonepe_response.get('transactionId')
        self.response_code = phonepe_response.get('responseCode')
        
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
        self.order.mark_as_paid(self.merchant_transaction_id)
    
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