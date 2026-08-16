from django.db import models
from django.utils.translation import gettext_lazy as _
from config.models import BaseModel

class SendUsQuery(BaseModel):
    first_name = models.CharField(
        _('first name'),
        max_length=255,
        help_text=_('Enter your first name')
    )
    last_name = models.CharField(
        _('last name'),
        max_length=255,
        help_text=_('Enter your last name')
    )
    email = models.EmailField(
        _('email'),
        max_length=255,
        help_text=_('Enter your email address')
    )
    phone_number = models.CharField(
        _('contact number'),
        max_length=20,
        help_text=_('Enter your contact number')
    )
    subject = models.CharField(
        _('subject'),
        max_length=255,
        help_text=_('Enter the subject of your query')
    )
    message = models.TextField(
        _('message'),
        help_text=_('Enter your message or query')
    )

    class Meta:
        verbose_name = _('Send Us Query')
        verbose_name_plural = _('Send Us Queries')
        ordering = ['-created_at']

    def __str__(self):
        # ``self.name`` was referenced here but no such field exists, so any
        # str() of a query raised AttributeError - including the Django admin
        # change page and every LogEntry written for one.
        return f"Query from {self.first_name} {self.last_name} - Subject: {self.subject}"

class PhoneNumber(BaseModel):
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        unique=True,
        help_text=_('Enter the phone number')
    )

    class Meta:
        verbose_name = _('Phone Number')
        verbose_name_plural = _('Phone Numbers')
        ordering = ['-created_at']

    def __str__(self):
        return self.phone_number

class Email(BaseModel):
    email = models.EmailField(
        _('email'),
        max_length=255,
        unique=True,
        help_text=_('Enter the email address')
    )

    class Meta:
        verbose_name = _('Email')
        verbose_name_plural = _('Emails')
        ordering = ['-created_at']

    def __str__(self):
        return self.email

class Address(BaseModel):
    address_line1 = models.CharField(
        _('address line 1'),
        max_length=255,
        help_text=_('Enter the first line of the address')
    )
    address_line2 = models.CharField(
        _('address line 2'),
        max_length=255,
        blank=True,
        help_text=_('Enter the second line of the address (optional)')
    )
    city = models.CharField(
        _('city'),
        max_length=100,
        help_text=_('Enter the city')
    )
    state = models.CharField(
        _('state'),
        max_length=100,
        help_text=_('Enter the state or province')
    )
    postal_code = models.CharField(
        _('postal code'),
        max_length=20,
        help_text=_('Enter the postal or ZIP code')
    )
    country = models.CharField(
        _('country'),
        max_length=100,
        help_text=_('Enter the country')
    )

    class Meta:
        verbose_name = _('Address')
        verbose_name_plural = _('Addresses')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.address_line1}, {self.city}, {self.country}"
    
class FAQCategory(BaseModel):
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Enter the name of the FAQ category')
    )              
    slug = models.SlugField(
        _('slug'),
        max_length=255,
        unique=True,
        help_text=_('Enter a unique slug for the FAQ category')
    ) 
    order = models.PositiveIntegerField(
        _('order'),
        default=0,
        help_text=_('Enter the display order for the FAQ category')
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Indicates whether the FAQ category is active')
    )
    class Meta:
        ordering = ['order']
        verbose_name_plural = 'FAQ Categories'
    def __str__(self):
        return self.name
    

class FAQs(BaseModel):
    category = models.ForeignKey(
        FAQCategory,
        on_delete=models.CASCADE,
        related_name='faqs',
        verbose_name=_('category'),
        help_text=_('Select the category for this FAQ'),
        null=True,
    )
    question = models.TextField(
        _('question'),
        help_text=_('Enter the frequently asked question')
    )
    answer = models.TextField(
        _('answer'),
        help_text=_('Enter the answer to the frequently asked question')
    )
    order = models.PositiveIntegerField(
        _('order'),
        default=0,
        help_text=_('Enter the display order for this FAQ')
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Indicates whether this FAQ is active')
    )
    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['order']
    
    def __str__(self):
        return self.question

class SocialMediaLink(BaseModel):
    PLATEFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('instagram', 'Instagram'),
        ('linkedin', 'LinkedIn'),
        ('youtube', 'YouTube'),
    ]
    platform_name = models.CharField(
        _('platform name'),
        max_length=100,
        choices=PLATEFORM_CHOICES,
        help_text=_('Enter the name of the social media platform')
    )
    url = models.URLField(
        _('URL'),
        max_length=255,
        help_text=_('Enter the URL of the social media profile')
    )

    class Meta:
        verbose_name = _('Social Media Link')
        verbose_name_plural = _('Social Media Links')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.platform_name}: {self.url}"


class Subscriber(BaseModel):
    email = models.EmailField(
        _('email'),
        max_length=255,
        unique=True,
        help_text=_('Enter the email address to subscribe')
    )

    class Meta:
        verbose_name = _('Subscriber')
        verbose_name_plural = _('Subscribers')
        ordering = ['-created_at']

    def __str__(self):
        return self.email