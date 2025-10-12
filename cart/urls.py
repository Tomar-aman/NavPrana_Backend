from django.urls import path
from .views import CartUpdateDeleteView, CartView

app_name = 'cart'

urlpatterns = [
    path('', CartView.as_view(), name='cart_list_create'),
    path('<int:pk>/', CartUpdateDeleteView.as_view(), name='cart_update_delete'),
]