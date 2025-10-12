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
            cart_item = user.cart_items.get(pk=pk)
        except Cart.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(cart_item, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        user = request.user
        try:
            cart_item = user.cart_items.get(pk=pk)
        except Cart.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)