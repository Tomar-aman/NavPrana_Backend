from django.urls import path
from .views import CartSyncView, CartUpdateDeleteView, CartView

app_name = 'cart'

urlpatterns = [
    path('', CartView.as_view(), name='cart_list_create'),
    path('sync/', CartSyncView.as_view(), name='cart_sync'),
    path('<int:pk>/', CartUpdateDeleteView.as_view(), name='cart_update_delete'),
]
