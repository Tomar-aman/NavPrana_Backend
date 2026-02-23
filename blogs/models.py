from django.db import models
from django.utils.translation import gettext_lazy as _
from config.models import BaseModel
from django.utils.text import slugify

class BlogCategory(BaseModel):
    name = models.CharField(
        _('name'),
        max_length=255,
        unique=True,
        help_text=_('Enter the blog category name')
    )
    slug = models.SlugField(
        _('slug'),
        max_length=255,
        unique=True,
        blank=True,
        help_text=_('Auto-generated slug from the category name')
    )

    class Meta:
        verbose_name = _('Blog Category')
        verbose_name_plural = _('Blog Categories')
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Blog(BaseModel):
    title = models.CharField(
        _('title'),
        max_length=255,
        help_text=_('Enter the blog title')
    )
    slug = models.SlugField(
        _('slug'),
        max_length=255,
        unique=True,
        blank=True,
        help_text=_('Auto-generated slug from the blog title')
    )
    excerpt = models.TextField(
        _('excerpt'),
        help_text=_('Enter a short excerpt for the blog')
    )
    content = models.TextField(
        _('content'),
        help_text=_('Enter the blog content')
    )
    thumbnail = models.ImageField(
        _('thumbnail'),
        upload_to='blog_thumbnails/',
        null=True,
        blank=True,
        help_text=_('Upload a thumbnail image for the blog')
    )
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blogs',
        verbose_name=_('category'),
        help_text=_('Select the category for this blog')
    )

    is_featured = models.BooleanField(
        _('is featured'),
        default=False,
        help_text=_('Indicates whether this blog is featured')
    )
    read_time = models.CharField(
        _('read time'),
        max_length=50,
        help_text=_('Enter the estimated read time for the blog (e.g., "5 min read")')
    )
    meta_title = models.CharField(
        _('meta title'),
        max_length=255,
        help_text=_('Enter the meta title for SEO purposes')
    )
    meta_description = models.TextField(
        _('meta description'),
        help_text=_('Enter the meta description for SEO purposes')
    )

    class Meta:
        verbose_name = _('Blog')
        verbose_name_plural = _('Blogs')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    def __str__(self):
        return self.title
