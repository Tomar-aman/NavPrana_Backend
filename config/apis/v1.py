from django.urls import include, path

app_name = "v1"

urlpatterns = [
    path("user/", include("users.urls")),
    path('product/', include('product.urls')),
    path('cart/', include('cart.urls')),
    path('coupon/', include('coupon.urls')),
    path('order/', include('orders.urls')),
    path('transaction/', include('transactions.urls')),
    path('contact/', include('contact.urls')),
    path('blogs/', include('blogs.urls')),
    path('public/', include('public_data.urls')),
        
    # path('web-content/', include('web_content.urls')),
]