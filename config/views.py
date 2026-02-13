from django.shortcuts import render


def custom_404_view(request, exception=None):
    # Reuse the same renderer both for handler404 and manual fallbacks
    return render(request, "404.html", status=404)
