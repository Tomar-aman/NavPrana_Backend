"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions

from config.views import custom_404_view

schema_view = get_schema_view(
   openapi.Info(
      title="Properly API",
      default_version='v1',
      description="API for Properly Web Application",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="admin@properly.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('', include('admin_panel.urls')),
    path('admin/', admin.site.urls),
    path('reports/', include('lab_report.url')),
    path("api/", include("config.apis", namespace="api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        re_path(r'^(?!media/|static/).+$', custom_404_view),
    ]
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler404 = "config.views.custom_404_view"
 