from django.db import models
from django.utils.translation import gettext_lazy as _

class WebContent(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('privacy_policy', 'Privacy Policy'),
        ('terms_and_condition', 'Terms and condition'),
        ('about_us', 'About Us'),
    ]
    content_type = models.CharField(
        max_length=50,
        verbose_name=_("Content Type"),
        choices=CONTENT_TYPE_CHOICES,
        db_index=True,
        help_text=_("Type of content, e.g., 'Privacy Policy', 'Terms and condition', 'About Us'."),
    )
    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
        help_text=_("Title of the content."),
    )
    content = models.TextField(
        verbose_name=_("Content"),
        help_text=_("The actual content text."),
    )
    image = models.ImageField(
        upload_to='web_content_images/',
        null=True,
        blank=True,
        verbose_name=_("Image"),
        help_text=_("Optional image associated with the content."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when the content was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when the content was last updated."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the content is currently active."),
    )

    class Meta:
        verbose_name = _("Web Content")
        verbose_name_plural = _("Web Contents")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.content_type} - {self.title}"
    


class SocialLinks(models.Model):
    twitter = models.URLField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name=_("Twitter URL"),
        help_text=_("URL to the Twitter profile."),
    )
    instagram = models.URLField(
        max_length=500,
        null=True,
        blank=True, 
        verbose_name=_("Instagram URL"),
        help_text=_("URL to the Instagram profile."),
    )
    linkedin = models.URLField(
        max_length=500, 
        null=True,
        blank=True,
        verbose_name=_("LinkedIn URL"),
        help_text=_("URL to the LinkedIn profile or page."),    
    )
    facebook = models.URLField(
        max_length=500,     
        null=True,
        blank=True,
        verbose_name=_("Facebook URL"),
        help_text=_("URL to the Facebook profile or page."),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Indicates whether the social link is currently active."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At"),
        help_text=_("The date and time when the social link was created."),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At"),
        help_text=_("The date and time when the social link was last updated."),
    )

    def __str__(self):
        return "Social Links"

    class Meta:
        verbose_name = _("Social Link")
        verbose_name_plural = _("Social Links")
    
