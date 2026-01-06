from django.urls import path
from .views import SendUsQueryView, PhoneEmailAddressView, PhoneNumberListView, FAQsListView, SocialMediaLinkListView

urlpatterns = [
    path('send-query/', SendUsQueryView.as_view(), name='send_us_query'),
    path('contact-info/', PhoneEmailAddressView.as_view(), name='contact_info'),
    path('phone-numbers/', PhoneNumberListView.as_view(), name='phone_number_list'),
    path('faqs/', FAQsListView.as_view(), name='faqs_list'),
    path('social-media-links/', SocialMediaLinkListView.as_view(), name='social_media_links_list'),
    
]
