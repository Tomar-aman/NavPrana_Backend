from django.db import models

class InstagramReel(models.Model):
    instagram_url = models.URLField(
        help_text="Full Instagram reel/post URL, e.g. https://www.instagram.com/reel/ABC123/"
    )
    thumbnail = models.ImageField(
        upload_to="reels/thumbnails/",
        help_text="Thumbnail image for the reel (upload a screenshot or cover image)"
    )
    caption = models.CharField(
        max_length=300,
        help_text="Short caption to display below the reel card"
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower number = shown first"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["sort_order", "-created_at"]
        verbose_name = "Instagram Reel"
        verbose_name_plural = "Instagram Reels"
    def __str__(self):
        return f"Reel: {self.caption[:50]}"
