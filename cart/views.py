from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import CartSerializer
from .models import Cart

class CartView(GenericAPIView):
    serializer_class = CartSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        cart_items = user.carts.all()
        serializer = self.get_serializer(cart_items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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