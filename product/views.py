from rest_framework.generics import ListAPIView, RetrieveAPIView, GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
# from django_filters import rest_framework as filters
from .models import Product, ProductReview
from .serializers import ProductSerializer, ProductReviewSerializer
# from .filters import ProductFilter
from rest_framework.response import Response
from rest_framework import status


class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    # filter_backends = [filters.DjangoFilterBackend, SearchFilter, OrderingFilter]
    # filterset_class = ProductFilter
    search_fields = ['name', 'description',]
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']


class ProductDetailView(RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'


class ProductReviewCreateView(GenericAPIView):
    serializer_class = ProductReviewSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Thank you for your review! Your feedback is valuable to us.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class ProductReviewListView(GenericAPIView):
    serializer_class = ProductReviewSerializer
    permission_classes = [AllowAny]

    def get(self, request, product_id, *args, **kwargs):
        reviews = (
            ProductReview.objects
            .filter(product_id=product_id)
            .select_related('user', 'product')
            .prefetch_related('media')
        )

        serializer = self.get_serializer(reviews, many=True)
        return Response(serializer.data)


class ProductReviewDetailView(GenericAPIView):
    serializer_class = ProductReviewSerializer
    def get_object(self, pk, user):
        return ProductReview.objects.get(pk=pk, user=user)

    def get(self, request, pk, *args, **kwargs):
        review = self.get_object(pk, request.user)
        serializer = self.get_serializer(review)
        return Response(serializer.data)

    def patch(self, request, pk, *args, **kwargs):
        try:
            review = self.get_object(pk, request.user)
            serializer = self.get_serializer(
                review,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                {
                    "message": "Your review has been updated successfully.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except ProductReview.DoesNotExist:
            return Response(
                {"error": "Review not found or you do not have permission to edit it."},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, pk, *args, **kwargs):
        try:
            review = self.get_object(pk, request.user)    
            review.delete()
            return Response(
                {"message": "Review deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )
        except ProductReview.DoesNotExist:
            return Response(
                {"error": "Review not found or you do not have permission to delete it."},
                status=status.HTTP_404_NOT_FOUND
            )