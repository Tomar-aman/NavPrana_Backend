from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.response import Response
from product.models import Product
from .serializers import CartSerializer
from .models import Cart

class CartView(GenericAPIView):
    serializer_class = CartSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        cart_items = user.carts.select_related('product').prefetch_related('product__images')
        serializer = self.get_serializer(cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CartSyncView(GenericAPIView):
    """
    Push a locally-held (guest) cart onto the account in one request.

    POST /api/v1/cart/sync/
    Body: {"items": [{"product": 1, "quantity": 2}, ...]}

    Quantities are upserted rather than added, so re-syncing the same local
    cart is idempotent. Returns the full server cart.
    """
    serializer_class = CartSerializer

    def post(self, request, *args, **kwargs):
        items = request.data.get('items') or []
        if not isinstance(items, list):
            return Response(
                {'error': '"items" must be a list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        for entry in items:
            try:
                product_id = int(entry.get('product'))
                quantity = int(entry.get('quantity', 1))
            except (TypeError, ValueError, AttributeError):
                continue
            if quantity < 1 or not Product.objects.filter(id=product_id).exists():
                continue

            Cart.objects.update_or_create(
                user=user,
                product_id=product_id,
                defaults={'quantity': quantity},
            )

        cart_items = user.carts.select_related('product').prefetch_related('product__images')
        serializer = self.get_serializer(cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartUpdateDeleteView(GenericAPIView):
    serializer_class = CartSerializer

    def patch(self, request, pk, *args, **kwargs):
        user = request.user
        try:
            cart_item = user.carts.get(pk=pk)
            serializer = self.get_serializer(cart_item, data=request.data, context={'request': request}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
    
        except Cart.DoesNotExist:
                return Response({'error': 'Cart item not found.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, *args, **kwargs):
        user = request.user
        try:
            cart_item = user.carts.get(pk=pk)
            cart_item.delete()
            return Response({"message": "Cart item deleted successfully."},status=status.HTTP_204_NO_CONTENT)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart item not found.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)