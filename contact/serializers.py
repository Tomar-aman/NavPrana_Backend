from rest_framework import serializers
from .models import FAQCategory, SendUsQuery, PhoneNumber, Email, Address, FAQs, SocialMediaLink

class SendUsQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SendUsQuery
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'subject', 'message',]
        read_only_fields = ['created_at', 'updated_at'] 

class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = ['id', 'phone_number',]
        read_only_fields = ['created_at', 'updated_at']

class EmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Email
        fields = ['id', 'email',]
        read_only_fields = ['created_at', 'updated_at']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',]
        read_only_fields = ['created_at', 'updated_at']

class FAQsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQs
        fields = ['id', 'question', 'answer',]
        read_only_fields = ['created_at', 'updated_at']

class FAQCategorySerializer(serializers.ModelSerializer):
    faqs = FAQsSerializer(many=True, read_only=True)
    class Meta:
        model = FAQCategory
        fields = ['id', 'name', 'slug', 'faqs']

class SocialMediaLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMediaLink
        fields = ['id', 'platform_name', 'url']
        read_only_fields = ['created_at', 'updated_at']

class PhoneEmailAddressSerializer(serializers.Serializer):
    phone_numbers = PhoneNumberSerializer(many=True, read_only=True)
    emails = EmailSerializer(many=True, read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    

class SocialMediaLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialMediaLink
        fields = ['id', 'platform_name', 'url']
        read_only_fields = ['created_at', 'updated_at']