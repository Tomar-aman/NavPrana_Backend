"""
Sign-in, sign-out and account self-service.

Everything here delegates to ``django.contrib.auth`` — its views, its session
handling, its password validators. The panel only supplies templates, a staff
check, and redirect-target validation.
"""

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.generic import TemplateView

from ..audit import log_change
from ..forms import PanelLoginForm, PanelProfileForm
from ..mixins import PanelContextMixin
from ..registry import registry
from ..utils import safe_redirect_target


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class PanelLoginView(LoginView):
    """Staff sign-in.

    ``redirect_authenticated_user`` stays off deliberately: with it on, Django
    documents that the login page becomes an oracle for probing session state.
    """

    template_name = 'panel/auth/login.html'
    authentication_form = PanelLoginForm
    redirect_authenticated_user = False

    def get_success_url(self):
        return safe_redirect_target(self.request, reverse('admin_panel:dashboard'))

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Welcome back, {self.request.user.first_name or "there"}.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Sign in'
        return context


class PanelLogoutView(LogoutView):
    """POST-only sign-out, matching Django 5's own behaviour."""

    next_page = reverse_lazy('admin_panel:login')


@method_decorator(sensitive_post_parameters(), name='dispatch')
class PanelPasswordChangeView(PanelContextMixin, PasswordChangeView):
    """Change your own password. Django's validators apply unchanged."""

    template_name = 'panel/auth/password_change.html'
    success_url = reverse_lazy('admin_panel:profile')
    nav_key = 'profile'
    page_title = 'Change password'
    page_subtitle = 'Update the password for your own account'

    def get_breadcrumbs(self):
        return [('My account', reverse('admin_panel:profile')), ('Change password', '')]

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'field-input')
            field.widget.attrs.setdefault('autocomplete', 'new-password')
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Your password has been changed.')
        return response


class PanelProfileView(PanelContextMixin, TemplateView):
    """The signed-in admin's own details."""

    template_name = 'panel/auth/profile.html'
    nav_key = 'profile'
    page_title = 'My account'
    page_subtitle = 'Your profile and sign-in details'

    def get_breadcrumbs(self):
        return [('My account', '')]

    def get(self, request, *args, **kwargs):
        return self.render_to_response(
            self.get_context_data(form=PanelProfileForm(instance=request.user))
        )

    def post(self, request, *args, **kwargs):
        form = PanelProfileForm(
            data=request.POST, files=request.FILES, instance=request.user
        )
        if not form.is_valid():
            messages.error(request, 'Please correct the highlighted fields.')
            return self.render_to_response(self.get_context_data(form=form))

        user = form.save()
        log_change(request.user, user, form.changed_data)
        messages.success(request, 'Your profile has been updated.')
        return redirect('admin_panel:profile')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = self.request.user.groups.all()
        return context


@method_decorator(sensitive_post_parameters(), name='dispatch')
class UserSetPasswordView(PanelContextMixin, TemplateView):
    """Set another user's password.

    Gated on ``users.change_user`` and, for staff targets, on being a superuser
    — otherwise any account with user-edit rights could take over an admin.
    """

    template_name = 'panel/auth/set_password.html'
    nav_key = 'users'
    page_subtitle = 'The new password takes effect immediately.'

    @cached_property
    def users_resource(self):
        return registry.get('users')

    @cached_property
    def target(self):
        target = get_object_or_404(self.users_resource.model, pk=self.kwargs['pk'])
        if (target.is_staff or target.is_superuser) and not self.request.user.is_superuser:
            raise PermissionDenied('Only a superuser can reset a staff password.')
        return target

    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm('users.change_user'):
            raise PermissionDenied('You do not have permission to change user passwords.')
        self.target  # resolve now so the superuser rule applies before the body

    def get_page_title(self):
        return f'Set password for {self.target.email or self.target.pk}'

    def get_breadcrumbs(self):
        return [
            ('Customers', ''),
            ('Users', self.users_resource.url('list')),
            (self.target.email or f'User #{self.target.pk}', self.users_resource.url('detail', self.target.pk)),
            ('Set password', ''),
        ]

    def build_form(self, data=None):
        form = SetPasswordForm(self.target, data=data)
        for field in form.fields.values():
            field.widget.attrs.setdefault('class', 'field-input')
            field.widget.attrs.setdefault('autocomplete', 'new-password')
        return form

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data(form=self.build_form()))

    def post(self, request, *args, **kwargs):
        form = self.build_form(data=request.POST)
        if not form.is_valid():
            messages.error(request, 'Please correct the highlighted fields.')
            return self.render_to_response(self.get_context_data(form=form))

        form.save()
        log_change(request.user, self.target, ['password'])
        if self.target.pk == request.user.pk:
            # Rotating your own password invalidates the current session hash.
            update_session_auth_hash(request, self.target)
        messages.success(request, f'Password updated for {self.target.email}.')
        return redirect(self.users_resource.url('detail', self.target.pk))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'target': self.target,
                'cancel_url': self.users_resource.url('detail', self.target.pk),
            }
        )
        return context
