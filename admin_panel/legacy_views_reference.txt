# from django.views.generic import View, TemplateView
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth import authenticate, login, logout, update_session_auth_hash, get_user_model
# from django.contrib import messages
# from django.utils.decorators import method_decorator
# from django.contrib.auth.decorators import user_passes_test
# from django.contrib.auth.tokens import default_token_generator
# from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
# from django.utils.encoding import force_bytes
# from django.http import HttpResponse
# import csv
# from django.core.paginator import Paginator         
# from django.urls import reverse
# from django.utils import timezone
# from django.db.models import Q
# from datetime import timedelta
# from config.utils import send_mail
# from api_settings.models import SMTPSettings
# from django.contrib.auth.hashers import make_password
# from django.core.mail import get_connection, EmailMessage
# from web_content.models import WebContent , SocialLinks
# from coupon.models import Coupon
# from decimal import Decimal
# from orders.models import Order
# from datetime import datetime
# from transactions.models import TransactionLog
# from django.db.models import Count, Sum
# from django.utils.timezone import now
# from django.db.models.functions import TruncDay , TruncMonth
# from django.http import JsonResponse
# from calendar import monthrange


# # @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# # class CustomAdminDashboardView(TemplateView):
# #     template_name = 'custom-admin/pages/dashboard.html'

# #     def get_context_data(self, **kwargs):
# #         context = super().get_context_data(**kwargs)
# #         User = get_user_model()
        
# #         # Get total users count
# #         context['total_users'] = User.objects.count()
# #         context['active_users'] = User.objects.filter(is_active=True).count()
# #         context['staff_users'] = User.objects.filter(is_staff=True).count()
        
# #         # Calculate percentage changes
# #         last_month = timezone.now() - timedelta(days=30)
# #         new_users_last_month = User.objects.filter(date_joined__gte=last_month).count()
# #         total_users_last_month = context['total_users'] - new_users_last_month
        
# #         if total_users_last_month > 0:
# #             growth_percentage = (new_users_last_month / total_users_last_month) * 100
# #             context['total_user_sign'] = '+' if growth_percentage > 0 else '-'
# #             context['total_user_percent'] = abs(round(growth_percentage, 1))
# #         else:
# #             context['total_user_sign'] = '+'
# #             context['total_user_percent'] = 100
            
# #         # Active users percentage change
# #         active_users_last_month = User.objects.filter(
# #             is_active=True,
# #             date_joined__lt=last_month
# #         ).count()
# #         if active_users_last_month > 0:
# #             active_growth = ((context['active_users'] - active_users_last_month) / active_users_last_month) * 100
# #             context['active_user_sign'] = '+' if active_growth > 0 else '-'
# #             context['active_user_percent'] = abs(round(active_growth, 1))
# #         else:
# #             context['active_user_sign'] = '+'
# #             context['active_user_percent'] = 100
            
# #         # Get recent users
# #         context['recent_users'] = User.objects.all().order_by('-date_joined')[:10]
        
# #         # Recent activity (last 10 user registrations)
# #         recent_activity = []
# #         for user in context['recent_users']:
# #             recent_activity.append({
# #                 'user': user,
# #                 'message': 'New user registered',
# #                 'created': user.date_joined
# #             })
# #         context['recent_activity'] = recent_activity
        
# #         context['title'] = 'Dashboard'
# #         return context


# #             return redirect('admin_panel:login')




# # @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# # class UserEditView(View):
# #     def post(self, request):
# #         User = get_user_model()
# #         user_id = request.POST.get('user_id')
# #         try:
# #             user = User.objects.get(id=user_id)
# #             user.full_name = request.POST.get('full_name')
# #             user.email = request.POST.get('email').lower()
            
# #             # Handle city selection
# #             # city_id = request.POST.get('city')
# #             # if city_id:
# #             #     try:
# #             #         city = City.objects.get(id=city_id)
# #             #         user.city = city
# #             #     except City.DoesNotExist:
# #             #         messages.error(request, 'Selected city not found')
# #             #         return redirect('admin_panel:manage_users')
# #             # else:
# #             #     user.city = None
            
# #             user.is_active = request.POST.get('is_active') == 'true'
# #             user.save()
# #             messages.success(request, f'User {user.email} has been updated successfully')
# #         except User.DoesNotExist:
# #             messages.error(request, 'User not found')
# #         except Exception as e:
# #             messages.error(request, f'Error updating user: {str(e)}')
# #         return redirect('admin_panel:manage_users')

# # class ResetUserPasswordView(View):
# #     def post(self, request):
# #         user_id = request.POST.get('user_id')
# #         password = request.POST.get('password')
# #         confirm_password = request.POST.get('confirm_password')
# #         if password != confirm_password:
# #             messages.error(request, 'Passwords do not match.')
# #             return redirect('admin_panel:manage_users')
# #         if len(password) < 8:
# #             messages.error(request, 'Password must be at least 8 characters long.')
# #             return redirect('admin_panel:manage_users')
# #         User = get_user_model()
# #         try:
# #             user = User.objects.get(id=user_id)
# #             user.set_password(password)
# #             user.save()
# #             messages.success(request, 'Password has been reset successfully.')
# #         except User.DoesNotExist:
# #             messages.error(request, 'User not found.')
# #         return redirect('admin_panel:manage_users')


# def is_admin(user):
#     return user.is_staff or user.is_superuser

# class CustomAdminLoginView(View):

#     def get(self, request):
#         if request.user.is_authenticated and is_admin(request.user):
#             return redirect('admin_panel:dashboard')
#         next_url = request.GET.get('next','')
#         return render(request, 'custom-admin/services/login.html',{'next_url':next_url})

#     def post(self, request):
#         email = request.POST.get('email').lower()
#         password = request.POST.get('password')
#         user = authenticate(request, username=email, password=password)
        
#         if user is not None and is_admin(user):
#             login(request, user)
#             next_url = request.POST.get('next','')
#             if next_url:
#                 return redirect(next_url)
#             return redirect('admin_panel:dashboard')
#         messages.error(request, 'Invalid credentials')
#         return render(request, 'custom-admin/services/login.html')

# class ResetPasswordView(View):
#     def get(self, request, uidb64, token):
#         try:
#             uid = urlsafe_base64_decode(uidb64).decode()
#             user = get_user_model().objects.get(pk=uid)
            
#             if default_token_generator.check_token(user, token):
#                 return render(request, 'custom-admin/services/reset-password.html', {
#                     'uidb64': uidb64,
#                     'token': token
#                 })
#             else:
#                 messages.error(request, 'Password reset link is invalid or has expired.')
#                 return redirect('admin_panel:login')
#         except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
#             messages.error(request, 'Password reset link is invalid.')
#             return redirect('admin_panel:login')

#     def post(self, request, uidb64, token):
#         try:
#             uid = urlsafe_base64_decode(uidb64).decode()
#             user = get_user_model().objects.get(pk=uid)
            
#             if default_token_generator.check_token(user, token):
#                 password = request.POST.get('password')
#                 confirm_password = request.POST.get('confirm_password')
                
#                 if password != confirm_password:
#                     messages.error(request, 'Passwords do not match.')
#                     return render(request, 'custom-admin/services/reset-password.html', {
#                         'uidb64': uidb64,
#                         'token': token
#                     })
                
#                 if len(password) < 8:
#                     messages.error(request, 'Password must be at least 8 characters long.')
#                     return render(request, 'custom-admin/services/reset-password.html', {
#                         'uidb64': uidb64,
#                         'token': token
#                     })
                
#                 user.set_password(password)
#                 user.save()
#                 messages.success(request, 'Password has been reset successfully.')
#                 return redirect('admin_panel:login')
#             else:
#                 messages.error(request, 'Password reset link is invalid or has expired.')
#                 return redirect('admin_panel:login')
#         except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
#             messages.error(request, 'Password reset link is invalid.')
#             return redirect('admin_panel:login')

# class ForgotPasswordView(View):
#     def post(self, request):
#         email = request.POST.get('email')
#         User = get_user_model()
#         try:
#             user = User.objects.get(email=email)
#             if not is_admin(user):
#                 messages.error(request, "This email is not registered as an admin user.", extra_tags='forgot_password_message')
#                 return redirect('admin_panel:login')

#             # Generate password reset token
#             token = default_token_generator.make_token(user)
#             uid = urlsafe_base64_encode(force_bytes(user.pk))
            
#             # Build reset URL
#             reset_url = request.build_absolute_uri(
#                 reverse('admin_panel:reset_password', kwargs={'uidb64': uid, 'token': token})
#             )
#             # Send email
#             subject = 'Password Reset Request'
#             template_name = 'email/password_reset_email.html'
#             context = {
#                 'reset_url': reset_url,
#             }
#             send_mail(subject, template_name, context, email)
            
#             messages.success(request, "Password reset link has been sent to your email.", extra_tags='forgot_password_message')
#             return redirect('admin_panel:login')
            
#         except User.DoesNotExist:
#             messages.error(request, "Email not found.", extra_tags='forgot_password_message')
#             return redirect('admin_panel:login')
#         except Exception as e:
#             messages.error(request, "An error occurred while sending the reset link.", extra_tags='forgot_password_message')
#             return redirect('admin_panel:login')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CustomAdminDashboardView(TemplateView):
#     template_name = 'custom-admin/services/dashboard.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         User = get_user_model()
        
#         # Get total users count
#         context['total_users'] = User.objects.count()
#         context['active_users'] = User.objects.filter(is_active=True).count()
#         context['staff_users'] = User.objects.filter(is_staff=True).count()
#         context['recent_users'] = User.objects.all().order_by('-date_joined')[:10]
#         context['free_users'] = User.objects.filter(is_active=True, transaction_logs__isnull=True).count()
#         context['paid_users'] = User.objects.filter(transaction_logs__status='success').distinct().count()
#         context['total_subscriptions'] = (
#             TransactionLog.objects.filter(
#                 status='success',
#                 subscription_id__isnull=False
#             ).values('subscription_id').distinct().count()
#         )
#         total_revenue = TransactionLog.objects.filter(status="success").aggregate(total=Sum("amount"))["total"] or 0
#         context["total_revenue"] = float(total_revenue)

        

#         # # Calculate percentage changes
#         # last_month = timezone.now() - timedelta(days=30)
#         # new_users_last_month = User.objects.filter(date_joined__gte=last_month).count()
#         # total_users_last_month = context['total_users'] - new_users_last_month
        
#         # if total_users_last_month > 0:
#         #     growth_percentage = (new_users_last_month / total_users_last_month) * 100
#         #     context['total_user_sign'] = '+' if growth_percentage > 0 else '-'
#         #     context['total_user_percent'] = abs(round(growth_percentage, 1))
#         # else:
#         #     context['total_user_sign'] = '+'
#         #     context['total_user_percent'] = 100
            
#         # # Active users percentage change
#         # active_users_last_month = User.objects.filter(
#         #     is_active=True,
#         #     date_joined__lt=last_month
#         # ).count()
#         # if active_users_last_month > 0:
#         #     active_growth = ((context['active_users'] - active_users_last_month) / active_users_last_month) * 100
#         #     context['active_user_sign'] = '+' if active_growth > 0 else '-'
#         #     context['active_user_percent'] = abs(round(active_growth, 1))
#         # else:
#         #     context['active_user_sign'] = '+'
#         #     context['active_user_percent'] = 100
            
#         # Get recent users
        
#         # Recent activity (last 10 user registrations)
#         recent_activity = []
#         for user in context['recent_users']:
#             recent_activity.append({
#                 'user': user,
#                 'message': 'New user registered',
#                 'created': user.date_joined
#             })
#         context['recent_activity'] = recent_activity

#         # ========== SUBSCRIPTION STATS ==========
#         # === Revenue Data (default current month) ===
#         # ========== SUBSCRIPTION STATS ==========
#         today = now().date()
#         current_year = today.year
#         current_month = today.month

#         # Current month start and end
#         start_date = today.replace(day=1)
#         days_in_month = monthrange(current_year, current_month)[1]
#         end_date = today.replace(day=days_in_month)

#         # Query revenue for current month
#         qs = (
#             TransactionLog.objects.filter(
#                 status="success",
#                 created_at__date__range=[start_date, end_date]
#             )
#             .annotate(day=TruncDay("created_at"))
#             .values("day")
#             .annotate(total=Sum("amount"))
#             .order_by("day")
#         )

#         # Dict for easy lookup {day: total}
#         revenue_by_day = {x["day"].day: float(x["total"]) for x in qs}

#         # Generate full month labels (1 → last day)
#         labels = [f"{day} {today.strftime('%b')}" for day in range(1, days_in_month + 1)]
#         data = [revenue_by_day.get(day, 0) for day in range(1, days_in_month + 1)]

#         # Add to context
#         context["labels"] = labels
#         context["data"] = data

#         # Monthly revenue total (for heading)
#         context["monthly_total"] = round(sum(data), 2)
        
#         context['title'] = 'Dashboard'
#         return context    

# class CustomAdminLogoutView(View):
#     def get(self, request):
#         logout(request)
#         return redirect('admin_panel:login')


# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UserListView(TemplateView):
#     template_name = 'custom-admin/services/manage-user.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         User = get_user_model()
        
#         # Get search query from request
#         search_query = self.request.GET.get('search', '')
#         page = self.request.GET.get('page', 1)
#         users = User.objects.all()
#         if search_query:
#             users = users.filter(
#                 Q(email__icontains=search_query) |
#                 Q(first_name__icontains=search_query) |
#                 Q(phone_number__icontains=search_query) |
#                 Q(last_name__icontains=search_query)
#             )
#         users = users.order_by('-date_joined')
#         paginator = Paginator(users, 10)  
#         users_page = paginator.get_page(page)
#         context['users'] = users_page
#         context['search_query'] = search_query
#         context['title'] = 'User Management'
#         return context

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UserToggleStatusView(View):
#     def post(self, request, user_id):
#         User = get_user_model()
#         try:
#             user = User.objects.get(id=user_id)
#             user.is_active = not user.is_active
#             user.save()
#             status = 'activated' if user.is_active else 'deactivated'
#             messages.success(request, f'User {user.email} has been {status}')
#         except User.DoesNotExist:
#             messages.error(request, 'User not found')
#         return redirect('admin_panel:manage_users')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UserDeleteView(View):
#     def post(self, request, user_id):
#         User = get_user_model()
#         try:
#             user = User.objects.get(id=user_id)
#             user.delete()
#             messages.success(request, f'User {user.email} has been deleted')
#         except User.DoesNotExist:
#             messages.error(request, 'User not found')
#         return redirect('admin_panel:manage_users')


# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UserEditView(View):
#     def post(self, request):
#         User = get_user_model()
#         user_id = request.POST.get('user_id')
#         try:
#             user = User.objects.get(id=user_id)
#             user.full_name = request.POST.get('full_name')
#             user.email = request.POST.get('email').lower()
#             user.country_code = request.POST.get("country_code")
#             user.phone_number = request.POST.get("phone_number")
            
#             user.is_active = request.POST.get('is_active') == 'true'
#             user.save()
#             messages.success(request, f'User {user.email} has been updated successfully')
#         except User.DoesNotExist:
#             messages.error(request, 'User not found')
#         except Exception as e:
#             messages.error(request, f'Error updating user: {str(e)}')
#         return redirect('admin_panel:manage_users')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UserResetPasswordView(View):
#     def post(self, request, user_id):
#         User = get_user_model()
#         password = request.POST.get('password')
#         confirm_password = request.POST.get('confirm_password')

#         if not user_id or not password or not confirm_password:
#             messages.error(request, 'All fields are required.')
#             return redirect('admin_panel:manage_users')

#         if password != confirm_password:
#             messages.error(request, 'Passwords do not match.')
#             return redirect('admin_panel:manage_users')

#         if len(password) < 8:
#             messages.error(request, 'Password must be at least 8 characters.')
#             return redirect('admin_panel:manage_users')

#         try:
#             user = User.objects.get(id=user_id)
#             user.password = make_password(password)
#             user.save()
#             messages.success(request, f'Password for {user.email} has been reset.')
#         except User.DoesNotExist:
#             messages.error(request, 'User not found.')
#         return redirect('admin_panel:manage_users')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class AdminProfileView(View):
#     def get(self, request):
#         smtp_settings = SMTPSettings.objects.first()
#         context = {
#             'title': 'Update Profile',
#             'user': request.user,
#             # 'cities': City.objects.all(),
#             'smtp_settings': smtp_settings
#         }
#         return render(request, 'custom-admin/services/profile.html', context)

#     def post(self, request):
#         user = request.user
        
#         # Handle profile picture upload
#         if 'profile_picture' in request.FILES:
#             try:
#                 user.profile_picture = request.FILES['profile_picture']
#                 user.save()
#                 messages.success(request, 'Profile picture updated successfully')
#             except Exception as e:
#                 messages.error(request, f'Error updating profile picture: {str(e)}')
#             return redirect('admin_panel:profile')
        
#         # Handle other profile updates
#         first_name = request.POST.get('first_name')
#         last_name  =  request.POST.get('last_name')
#         phone_number = request.POST.get('phone_number')
#         # city_id = request.POST.get('city')
    
#         try:
#             user.first_name = first_name
#             user.last_name = last_name
#             user.phone_number = phone_number
#             # if city_id:
#             #     user.city_id = city_id
#             user.save()
#             messages.success(request, 'Profile updated successfully')
#         except Exception as e:
#             messages.error(request, f'Error updating profile: {str(e)}')
    
#         return redirect('admin_panel:profile')


# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class ChangePasswordView(View):
#     def get(self, request):
#         return render(request, 'custom-admin/services/change-password.html', {'title': 'Change Password'})

#     def post(self, request):
#         current_password = request.POST.get('current_password')
#         new_password = request.POST.get('new_password')
#         confirm_password = request.POST.get('confirm_password')

#         if not request.user.check_password(current_password):
#             messages.error(request, 'Current password is incorrect')
#             return redirect('admin_panel:change_password')

#         if new_password != confirm_password:
#             messages.error(request, 'New passwords do not match')
#             return redirect('admin_panel:change_password')

#         if len(new_password) < 8:
#             messages.error(request, 'Password must be at least 8 characters long')
#             return redirect('admin_panel:change_password')

#         try:
#             request.user.set_password(new_password)
#             request.user.save()
#             update_session_auth_hash(request, request.user)  # Keep user logged in
#             messages.success(request, 'Password changed successfully')
#             return redirect('admin_panel:profile')
#         except Exception as e:
#             messages.error(request, 'Error changing password')
#             return redirect('admin_panel:change_password')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class UpdateSMTPSettingsView(View):
#     def post(self, request):
#         try:
#             smtp_settings = SMTPSettings.objects.first()
#             if not smtp_settings:
#                 smtp_settings = SMTPSettings()

#             smtp_settings.host = request.POST.get('smtp_host')
#             smtp_settings.port = int(request.POST.get('smtp_port'))
#             smtp_settings.username = request.POST.get('smtp_username')
#             smtp_settings.password = request.POST.get('smtp_password')
#             smtp_settings.from_email = request.POST.get('from_email')
#             smtp_settings.use_tls = request.POST.get('use_tls') == 'on'

#             # Test SMTP connection
#             connection = get_connection(
#                 host=smtp_settings.host,
#                 port=smtp_settings.port,
#                 username=smtp_settings.username,
#                 password=smtp_settings.password,
#                 use_tls=smtp_settings.use_tls
#             )

#             # Send test email
#             email = EmailMessage(
#                 'SMTP Test',
#                 'This is a test email to verify SMTP settings.',
#                 smtp_settings.host,
#                 [request.user.email],
#                 connection=connection,
#             )
#             email.send()

#             smtp_settings.save()
#             messages.success(request, 'SMTP settings updated successfully')

#         except ValueError as e:
#             messages.error(request, 'Invalid port number')
#         except Exception as e:
#             messages.error(request, f'Failed to update SMTP settings: {str(e)}')

#         return redirect('admin_panel:profile')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class WebContentView(TemplateView):
#     template_name = 'custom-admin/services/manage-content.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         contents = WebContent.objects.all().order_by('-created_at')
#         context['contents'] = contents
#         context['title'] = 'Web Content Management'
#         return context

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class WebContentEditView(View):
#     def post(self, request,content_id):
#         try:
#             content = WebContent.objects.get(id=content_id)
#             content_type = request.POST.get('content_type')
#               # Check if another content with this type exists (excluding current content)
#             if WebContent.objects.exclude(id=content_id).filter(content_type=content_type).exists():
#                 messages.error(request, f'Another content with type "{content_type}" already exists')
#                 return redirect('admin_panel:manage_content')
#             content.title = request.POST.get('title')
#             content.content = request.POST.get('content')
#             content.content_type = content_type
#             if 'image' in request.FILES:
#                 content.image = request.FILES['image']
#             content.is_active = request.POST.get('is_active') == 'true'
#             content.save()
#             messages.success(request, f'Content "{content.title}" has been updated successfully')
#         except WebContent.DoesNotExist:
#             messages.error(request, 'Content not found')
#         except Exception as e:
#             messages.error(request, f'Error updating content: {str(e)}')
#         return redirect('admin_panel:manage_content')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class WebContentCreateView(View):
#     def post(self, request):
#         try:
#             content_type = request.POST.get('content_type')
#             # Check if content with this type already exists
#             if WebContent.objects.filter(content_type=content_type).exists():
#                 messages.error(request, f'Content with type "{content_type}" already exists')
#                 return redirect('admin_panel:manage_content')
#             # Create new content
#             WebContent.objects.create(
#                 title=request.POST.get('title'),
#                 content=request.POST.get('content'),
#                 content_type=content_type,
#                 image=request.FILES.get('image'),
#             )
#             messages.success(request, 'Content created successfully')
#         except Exception as e:
#             messages.error(request, f'Error creating content: {str(e)}')
#         return redirect('admin_panel:manage_content')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class WebContentDeleteView(View):
#     def post(self, request, content_id):
#         try:
#             content = WebContent.objects.get(id=content_id)
#             content.delete()
#             messages.success(request, 'Content deleted successfully')
#         except WebContent.DoesNotExist:
#             messages.error(request, 'Content not found')
#         except Exception as e:
#             messages.error(request, f'Error deleting content: {str(e)}')
#         return redirect('admin_panel:manage_content')

# # @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# # class APISettingsListView(TemplateView):
# #     template_name = 'custom-admin/services/manage-api.html'

# #     def get_context_data(self, **kwargs):
# #         context = super().get_context_data(**kwargs)
# #         context['chatgpt_settings'] = ChatGptAPISettings.objects.latest('created_at')
# #         # context['api_settings'] = APISettings.objects.all().order_by('provider')
# #         # context['notification_settings'] = NotificationSettings.objects.latest('created_at')
# #         context['stripe_settings'] = StripeSettings.objects.latest('created_at')
# #         context['title'] = 'API Settings Management'
# #         return context

# # class StripeSettingsEditView(View):
# #     def post(self, request, settings_id):
# #         try:
# #             stripe_settings = StripeSettings.objects.get(id=settings_id)
# #             stripe_settings.secret_key = request.POST.get('secret_key')
# #             stripe_settings.publishable_key = request.POST.get('publishable_key')
# #             stripe_settings.api_version = request.POST.get('api_version')
# #             stripe_settings.currency = request.POST.get('currency', 'AED')
# #             stripe_settings.save()
            
# #             messages.success(request, 'Stripe settings updated successfully')
# #         except StripeSettings.DoesNotExist:
# #             messages.error(request, 'Stripe settings not found')
# #         except Exception as e:
# #             messages.error(request, f'Error updating Stripe settings: {str(e)}')
# #         return redirect('admin_panel:manage_api_settings')
    
# # class ChatGptAPISettingsEditView(View):
# #     def post(self, request, chatgpt_id):
# #         try:
# #             chatgpt_settings = ChatGptAPISettings.objects.get(id= chatgpt_id)

# #             chatgpt_settings.api_key = request.POST.get('api_key')
# #             chatgpt_settings.model = request.POST.get('model')
# #             chatgpt_settings.temperature = float(request.POST.get('temperature', 0.7))
# #             chatgpt_settings.is_active = request.POST.get('is_active') == 'true'
# #             chatgpt_settings.save()

# #             messages.success(request, 'ChatGPT API settings updated successfully')
# #         except ChatGptAPISettings.DoesNotExist:
# #             messages.error(request, 'ChatGPT API settings not found')
# #         except Exception as e:
# #             messages.error(request, f'Error updating ChatGPT API settings: {str(e)}')

# #         return redirect('admin_panel:manage_api_settings')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CouponListView(TemplateView):
#     template_name = 'custom-admin/services/manage-coupons.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         search_query = self.request.GET.get('search', '')
#         page = self.request.GET.get('page', 1)
#         coupons = Coupon.objects.all().order_by('-created_at')
#         if search_query:
#             coupons = coupons.filter(
#                 Q(coupon_code__icontains=search_query) |
#                 Q(coupon_id__icontains=search_query) 
#             )
#         paginator = Paginator(coupons, 10)
#         coupons = paginator.get_page(page)
#         context['coupons'] = coupons
#         context['search_query'] = search_query
#         context['title'] = 'Coupon Management'
#         return context

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CouponCreateView(View):
#     def post(self, request):
#         try:
#             coupon = Coupon.objects.create(
#                 coupon_code=request.POST.get('coupon_code').upper().strip(),
#                 amount=Decimal(request.POST.get('amount') or 0),
#                 minimum_plan_amount=Decimal(request.POST.get('minimum_plan_amount') or 0),
#                 percent=Decimal(request.POST.get('percent') or 0),
#                 start_date=request.POST.get('start_date'),
#                 end_date=request.POST.get('end_date') or None,
#                 max_use=int(request.POST.get('max_use', 1)),
#                 status=True
#             )
#             messages.success(request, 'Coupon created successfully')
#         except Exception as e:
#             messages.error(request, f'Error creating coupon: {str(e)}')
#         return redirect('admin_panel:manage_coupons')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CouponEditView(View):
#     def post(self, request, coupon_id):
#         try:
#             coupon = Coupon.objects.get(id=coupon_id)
#             coupon.coupon_code = request.POST.get('coupon_code').upper().strip()
#             coupon.amount = Decimal(request.POST.get('amount') or 0)
#             coupon.percent = Decimal(request.POST.get('percent') or 0)
#             coupon.minimum_plan_amount = Decimal(request.POST.get('minimum_plan_amount') or 0)
#             coupon.start_date = request.POST.get('start_date')
#             coupon.end_date = request.POST.get('end_date') or None
#             coupon.max_use = int(request.POST.get('max_use', 1))
#             coupon.status = request.POST.get('status') == 'true'
#             coupon.save()
#             messages.success(request, 'Coupon updated successfully')
#         except Coupon.DoesNotExist:
#             messages.error(request, 'Coupon not found')
#         except Exception as e:
#             messages.error(request, f'Error updating coupon: {str(e)}')
#         return redirect('admin_panel:manage_coupons')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CouponToggleStatusView(View):
#     def post(self, request, coupon_id):
#         try:
#             coupon = Coupon.objects.get(id=coupon_id)
#             coupon.status = not coupon.status
#             coupon.save()
#             status = 'active' if coupon.status else 'inactive'
#             messages.success(request, f'Coupon {coupon.coupon_code} has been {status}')
#         except Coupon.DoesNotExist:
#             messages.error(request, 'Coupon not found')
#         return redirect('admin_panel:manage_coupons')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class CouponDeleteView(View):
#     def post(self, request, coupon_id):
#         try:
#             coupon = Coupon.objects.get(id=coupon_id)
#             if coupon.used > 0:
#                 messages.error(request, 'Cannot delete coupon that has been used')
#                 return redirect('admin_panel:manage_coupons')
#             coupon.delete()
#             messages.success(request, 'Coupon deleted successfully')
#         except Coupon.DoesNotExist:
#             messages.error(request, 'Coupon not found')
#         return redirect('admin_panel:manage_coupons')



# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class OrderListView(TemplateView):
#     template_name = 'custom-admin/services/manage-orders.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         orders = Order.objects.all().order_by('-created_at')

#         search = self.request.GET.get('search', '')
#         if search:
#             orders = orders.filter(
#                 Q(user__first_name__icontains=search) |
#                 Q(plan__name__icontains=search) |
#                 Q(id__icontains=search)
#             )

#         daterange = self.request.GET.get('daterange', '')
#         if daterange:
#             try:
#                 start, end = daterange.split(' - ')
#                 orders = orders.filter(created_at__date__range=[start, end])
#             except ValueError:
#                 pass

#         status = self.request.GET.get('status', '')
#         if status:
#             orders = orders.filter(status=status)

#         payment_status = self.request.GET.get('payment_status', '')
#         if payment_status:
#             orders = orders.filter(payment_status=payment_status)

#         paginator = Paginator(orders, 10)
#         page = self.request.GET.get('page', 1)
#         paginated_orders = paginator.get_page(page)

#         context.update({
#             'orders': paginated_orders,
#             'search': search,
#             'status': status,
#             'payment_status': payment_status,
#             'date_range': daterange,
#         })
#         return context

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class OrderEditView(View):
#     def post(self, request, order_id):
#         order = get_object_or_404(Order, id=order_id)
#         status = request.POST.get('status')
#         payment_status = request.POST.get('payment_status')

#         order.status = status
#         order.payment_status = payment_status
#         order.save()

#         messages.success(request, 'Order updated successfully')
#         return redirect('admin_panel:manage_orders')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class OrderExportView(View):
#     def get(self, request):
#         orders = Order.objects.select_related('user', 'plan').all()

#         search = request.GET.get('search', '')
#         if search:
#             orders = orders.filter(
#                 Q(user__first_name__icontains=search) |
#                 Q(plan__name__icontains=search)
#             )

#         daterange = request.GET.get('daterange', '')
#         if daterange:
#             try:
#                 start, end = daterange.split(' - ')
#                 orders = orders.filter(created_at__date__range=[start, end])
#             except ValueError:
#                 pass

#         response = HttpResponse(content_type='text/csv')
#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         response['Content-Disposition'] = f'attachment; filename="orders_{timestamp}.csv"'

#         writer = csv.writer(response)
#         writer.writerow([
#             'Order ID', 'User', 'Plan', 'Status', 'Payment Status',
#             'Total Amount', 'Discount', 'Tax %', 'Created At'
#         ])

#         for order in orders:
#             writer.writerow([
#                 order.id,
#                 order.user.first_name,
#                 order.plan.name,
#                 order.status,
#                 order.payment_status,
#                 f"${order.total_amount:.2f}",
#                 f"${order.discount_amount:.2f}",
#                 f"{order.tax_percentage:.2f}%",
#                 order.created_at.strftime('%Y-%m-%d %H:%M')
#             ])

#         return response


# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class SocialLinksView(TemplateView):
#     template_name = 'custom-admin/services/manage-social-link.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         contents = SocialLinks.objects.all().order_by('-created_at')
#         context['contents'] = contents
#         context['title'] = 'Social Links Management'
#         return context

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class SocialLinksEditView(View):
#     def post(self, request, link_id):
#         try:
#             twitter = request.POST.get('twitter')
#             instagram = request.POST.get('instagram')
#             linkedin = request.POST.get('linkedin')
#             facebook = request.POST.get('facebook')
#             is_active = request.POST.get('is_active') == 'true'

#             # Check if another SocialLinks entry with the same URLs exists (excluding current one)
#             if SocialLinks.objects.exclude(id=link_id).filter(
#                 Q(twitter__icontains=twitter, twitter__isnull=False) |
#                 Q(instagram__icontains=instagram, instagram__isnull=False) |
#                 Q(linkedin__icontains=linkedin, linkedin__isnull=False) |
#                 Q(facebook__icontains=facebook, facebook__isnull=False)
#             ).exists():
#                 messages.error(request, 'Social links with one or more of these URLs already exist')
#                 return redirect('admin_panel:manage_social_links')

#             social_link = SocialLinks.objects.get(id=link_id)
#             social_link.twitter = twitter
#             social_link.instagram = instagram
#             social_link.linkedin = linkedin
#             social_link.facebook = facebook
#             social_link.is_active = is_active
#             social_link.save()
#             messages.success(request, 'Social links updated successfully')
#         except SocialLinks.DoesNotExist:
#             messages.error(request, 'Social link not found')
#         except Exception as e:
#             messages.error(request, f'Error updating social links: {str(e)}')
#         return redirect('admin_panel:manage_social_links')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class SocialLinksCreateView(View):
#     def post(self, request):
#         try:
#             twitter = request.POST.get('twitter')
#             instagram = request.POST.get('instagram')
#             linkedin = request.POST.get('linkedin')
#             facebook = request.POST.get('facebook')
#             is_active = request.POST.get('is_active') == 'true'

#             # Check if a SocialLinks entry with the same URLs already exists
#             if SocialLinks.objects.filter(
#                 Q(twitter__iexact=twitter, twitter__isnull=False) |
#                 Q(instagram__iexact=instagram, instagram__isnull=False) |
#                 Q(linkedin__iexact=linkedin, linkedin__isnull=False) |
#                 Q(facebook__iexact=facebook, facebook__isnull=False)
#             ).exists():
#                 messages.error(request, 'Social links with one or more of these URLs already exist')
#                 return redirect('admin_panel:manage_social_links')

#             SocialLinks.objects.create(
#                 twitter=twitter,
#                 instagram=instagram,
#                 linkedin=linkedin,
#                 facebook=facebook,
#                 is_active=is_active
#             )
#             messages.success(request, 'Social links added successfully')
#         except Exception as e:
#             messages.error(request, f'Error adding social links: {str(e)}')
#         return redirect('admin_panel:manage_social_links')

# @method_decorator(user_passes_test(is_admin, login_url='admin_panel:login'), name='dispatch')
# class SocialLinksDeleteView(View):
#     def post(self, request, link_id):
#         try:
#             content = SocialLinks.objects.get(id=link_id)
#             content.delete()
#             messages.success(request, 'Social Links deleted successfully')
#         except SocialLinks.DoesNotExist:
#             messages.error(request, 'Content not found')
#         except Exception as e:
#             messages.error(request, f'Error deleting content: {str(e)}')
#         return redirect('admin_panel:manage_social_links')