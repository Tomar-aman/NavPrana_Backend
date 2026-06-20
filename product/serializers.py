from rest_framework import serializers
from .models import Product, ProductImage, ProductReview, Category, ProductFeature, ProductSpecification ,ProductReview, ProductReviewMedia
from django.db import transaction

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_feature']

# class ProductReviewSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProductReview
#         fields = ['rating', 'review']

class ProductReviewMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReviewMedia
        fields = (
            'id',
            'media_type',
            'file',
            'alt_text',
        )
        read_only_fields = ('id',)


class ProductReviewSerializer(serializers.ModelSerializer):
    media = ProductReviewMediaSerializer(many=True, read_only=True)
    user_email = serializers.SerializerMethodField()
    
    # For creating review with media files
    # Accepts a list of files in the request
    # Multiple file upload
    media_files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = ProductReview
        fields = (
            'id',
            'product',
            'rating',
            'review',
            'media',
            'media_files',
            'created_at',
            'user_email',
        )
        read_only_fields = ('id', 'created_at', 'user_email')

    def get_user_email(self, obj):
        return obj.user.email


    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs.get('product')

        # One review per product per user
        if ProductReview.objects.filter(
            user=user,
            product=product
        ).exists():
            raise serializers.ValidationError(
                "You have already reviewed this product."
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        user = request.user

        media_files = validated_data.pop('media_files', [])

        review = ProductReview.objects.create(
            user=user,
            **validated_data
        )

        media_objects = []
        for file in media_files:
            ext = file.name.lower()
            media_type = (
                'video' if ext.endswith(('.mp4', '.mov', '.webm'))
                else 'image'
            )

            media_objects.append(
                ProductReviewMedia(
                    review=review,
                    media_type=media_type,
                    file=file,
                    alt_text=ext
                )
            )

        if media_objects:
            ProductReviewMedia.objects.bulk_create(media_objects)

        return review
    
    def update(self, instance, validated_data):
        media_files = validated_data.pop('media_files', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if media_files:
            # Delete old media
            # instance.media.all().delete()

            media_objects = []
            for file in media_files:
                ext = file.name.lower()
                media_type = (
                    'video' if ext.endswith(('.mp4', '.mov', '.webm'))
                    else 'image'
                )

                media_objects.append(
                    ProductReviewMedia(
                        review=instance,
                        media_type=media_type,
                        file=file,
                        alt_text=ext
                    )
                )

            ProductReviewMedia.objects.bulk_create(media_objects)

        return instance

class ProductFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductFeature
        fields = ['feature']


class ProductSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ['specification']

class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    features = ProductFeatureSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'size', 'details',
            'description','max_price' ,'price', 'discount_precent' ,'available_quantity', 'max_quantity', 'images' ,'average_rating', 'reviews', 'features', 'specifications'
        ]
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews.exists():
            return None
        total_rating = sum(review.rating for review in reviews)
        return total_rating / reviews.count()


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_feature']