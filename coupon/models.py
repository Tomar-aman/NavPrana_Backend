from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime ,date
from django.core.exceptions import ValidationError
from users.models import User

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('amount', 'Fixed Amount'),
        ('percent', 'Percentage'),
        ('shipping', 'Free Shipping'),
    )

    coupon_id = models.CharField(
        verbose_name=_('Coupon ID'),
        max_length=255,
        unique=True,
        db_index=True
    )
    coupon_code = models.CharField(
        verbose_name=_('Coupon Code'),
        max_length=255,
        unique=True,
        db_index=True
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default='amount',
        verbose_name=_('Discount Type'),
        help_text=_('Type of discount')
    )
    amount = models.DecimalField(
        verbose_name=_('Fixed Amount'),
        default=0.00,
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.00)],
        help_text=_('Fixed discount amount')
    )
    percent = models.DecimalField(
        verbose_name=_('Percentage'),
        default=0.00,
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        help_text=_('Percentage discount (0-100)')
    )
    start_date = models.DateField(
        verbose_name=_('Start Date'),
        default=timezone.now,
        help_text=_('Coupon valid from this date')
    )
    minimum_cart_amount = models.DecimalField(
        verbose_name=_('Minimum Cart Amount'),
        default=0.00,
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0.00)],
        help_text=_('Minimum order amount for this coupon to be valid')
    )
    end_date = models.DateField(
        verbose_name=_('End Date'),
        null=True,
        blank=True,
        help_text=_('Coupon valid until this date (optional)')
    )
    max_use = models.PositiveIntegerField(
        verbose_name=_('Maximum Uses'),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_('Maximum number of times this coupon can be used')
    )
    used = models.PositiveIntegerField(
        verbose_name=_('Times Used'),
        default=0,
        help_text=_('Number of times this coupon has been used')
    )
    uses_per_user = models.PositiveIntegerField(
        verbose_name=_('Uses Per User'),
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_('Maximum number of times a user can use this coupon')
    )
    free_shipping = models.BooleanField(
        default=False,
        verbose_name=_('Free Shipping'),
        help_text=_('If true, delivery charges are waived')
    )
    status = models.BooleanField(
        verbose_name=_('Status'),
        default=True,
        help_text=_('Whether this coupon is currently active')
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
        verbose_name = _("Coupon")
        verbose_name_plural = _("Coupons")
        db_table = "coupon"
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.coupon_code} ({self.coupon_id})"

    def clean(self):
        if not self.free_shipping and self.amount == 0 and self.percent == 0:
            raise ValidationError(_("Either amount or percent must be greater than 0 for non-free shipping coupons."))
        
        if self.amount > 0 and self.percent > 0:
            raise ValidationError(_("Cannot have both fixed amount and percentage discount"))
            
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError(_("End date must be after start date"))
            
        if self.used > self.max_use:
            raise ValidationError(_("Used count cannot exceed maximum uses"))
    

    def save(self, *args, **kwargs):
        self.clean()
        if not self.coupon_id:
            year_suffix = str(datetime.now().year % 100)
            prefix = f"CC{year_suffix}"
            count = Coupon.objects.filter(coupon_id__startswith=prefix).count()
            self.coupon_id = unique_coupon_id(count, prefix)
            self.coupon_code = self.coupon_code.upper().strip()
        super().save(*args, **kwargs)

    def record_usage(self, user):
        """Record that a user has used this coupon"""
        usage, created = CouponUsage.objects.get_or_create(
            coupon=self,
            user=user
        )
        usage.used_count += 1
        usage.save()


def unique_coupon_id(count, prefix):
    new_count = count + 1
    new_coupon_id = f"{prefix}{new_count:06d}"
    if Coupon.objects.filter(coupon_id=new_coupon_id).exists():
        return unique_coupon_id(new_count, prefix)
    return new_coupon_id


class CouponUsage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coupon_usage'
    )
    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Times Used by User')
    )
    first_used_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('First Used At')
    )
    last_used_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Used At')
    )

    class Meta:
        verbose_name = _("Coupon Usage")
        verbose_name_plural = _("Coupon Usages")
        db_table = "coupon_usage"
        unique_together = ['coupon', 'user']
        indexes = [
            models.Index(fields=['coupon', 'user']),
        ]

    def __str__(self):
        return f"{self.coupon.coupon_code} - {self.user.username}"