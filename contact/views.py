from django.db.models import Prefetch
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from contact.serializers import FAQCategorySerializer, SendUsQuerySerializer, PhoneNumberSerializer, EmailSerializer, AddressSerializer, FAQsSerializer, SocialMediaLinkSerializer, PhoneEmailAddressSerializer, SubscriberSerializer
from contact.models import FAQCategory, SendUsQuery, PhoneNumber, Email, Address, FAQs, SocialMediaLink, Subscriber


class SendUsQueryView(GenericAPIView):
    serializer_class = SendUsQuerySerializer
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Query sent successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PhoneNumberListView(GenericAPIView):
    serializer_class = PhoneNumberSerializer
    permission_classes = [AllowAny]
    def get(self, request):
        phone_numbers = PhoneNumber.objects.all()
        serializer = self.serializer_class(phone_numbers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PhoneEmailAddressView(GenericAPIView):
    serializer_class = PhoneEmailAddressSerializer
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        phone_numbers = PhoneNumber.objects.all()
        emails = Email.objects.all()
        addresses = Address.objects.all()

        serializer = self.get_serializer({
            'phone_numbers': phone_numbers,
            'emails': emails,
            'addresses': addresses
        })
        return Response(serializer.data, status=status.HTTP_200_OK)

class FAQsListView(GenericAPIView):
    serializer_class = FAQsSerializer
    permission_classes = [AllowAny]
    def get(self, request):
        categories = FAQCategory.objects.filter(
            is_active=True
        ).prefetch_related(
            Prefetch(
                'faqs',
                queryset=FAQs.objects.filter(is_active=True).order_by('order')
            )
        ).order_by('order')
        serializer = FAQCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SocialMediaLinkListView(GenericAPIView):
    serializer_class = SocialMediaLinkSerializer
    permission_classes = [AllowAny]
    def get(self, request):
        social_media_links = SocialMediaLink.objects.all()
        serializer = self.serializer_class(social_media_links, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class SubscriberView(GenericAPIView):
    serializer_class = SubscriberSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Thank you for subscribing!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)