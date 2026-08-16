"""
Tests for the admin panel.

Focused on the parts that would be expensive to get wrong: access control,
the model-specific form rules, and the query budget of the list pages.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from product.models import Category, Product
from users.models import UserAddress

from .filters import BooleanFilter, ChoiceFilter, DateRangeFilter
from .registry import registry


User = get_user_model()


def make_product(**overrides):
    defaults = {
        'name': 'Test Ghee',
        'size': '500ml',
        'max_price': Decimal('1000.00'),
        'discount_precent': Decimal('10.00'),
        'max_quantity': 100,
        'available_quantity': 50,
        'price': Decimal('900.00'),
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


class PanelAccessTests(TestCase):
    """Only active staff may reach the panel, and only their own sections."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        cls.shopper = User.objects.create_user('shopper@example.com', 'pw-Str0ng!123')
        cls.shopper.is_active = True
        cls.shopper.save()

        cls.editor = User.objects.create_user('editor@example.com', 'pw-Str0ng!123')
        cls.editor.is_active = True
        cls.editor.is_staff = True
        cls.editor.save()
        role = Group.objects.create(name='Catalog editor')
        role.permissions.add(
            *Permission.objects.filter(
                content_type__app_label='product',
                codename__in=['view_product', 'change_product'],
            )
        )
        cls.editor.groups.add(role)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin_panel:login'), response['Location'])

    def test_active_non_staff_is_forbidden(self):
        self.client.force_login(self.shopper)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 403)

    def test_non_staff_cannot_sign_in(self):
        response = self.client.post(
            reverse('admin_panel:login'),
            {'username': 'shopper@example.com', 'password': 'pw-Str0ng!123'},
        )
        self.assertContains(response, 'does not have access to the admin panel')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_staff_reaches_only_permitted_sections(self):
        self.client.force_login(self.editor)
        list_url = registry.get('products').url('list')

        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(list_url).status_code, 200)
        # Permission missing -> 403 even though the URL is guessable.
        self.assertEqual(self.client.get(registry.get('orders').url('list')).status_code, 403)
        self.assertEqual(self.client.get(registry.get('users').url('list')).status_code, 403)
        # Holds "change" but not "add" or "delete".
        self.assertEqual(self.client.get(registry.get('products').url('add')).status_code, 403)

    def test_sidebar_omits_forbidden_sections(self):
        self.client.force_login(self.editor)
        body = self.client.get(reverse('admin_panel:dashboard')).content.decode()
        self.assertIn(registry.get('products').url('list'), body)
        self.assertNotIn(registry.get('orders').url('list'), body)

    def test_every_resource_renders_for_a_superuser(self):
        self.client.force_login(self.superuser)
        for resource in registry:
            with self.subTest(resource=resource.key):
                self.assertEqual(self.client.get(resource.url('list')).status_code, 200)


class SecretExposureTests(TestCase):
    """Credentials must never be rendered, even to a superuser."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_user_detail_hides_the_password_hash(self):
        url = registry.get('users').url('detail', self.superuser.pk)
        self.assertNotContains(self.client.get(url), self.superuser.password)

    def test_user_form_has_no_password_field(self):
        url = registry.get('users').url('edit', self.superuser.pk)
        self.assertNotContains(self.client.get(url), 'name="password"')

    def test_smtp_password_is_write_only(self):
        from api_settings.models import SMTPSettings

        settings_row = SMTPSettings.objects.create(
            host='smtp.example.com', port=587, username='mailer',
            password='super-secret-value', from_email='no-reply@example.com',
        )
        detail = registry.get('email-settings').url('detail', settings_row.pk)
        edit = registry.get('email-settings').url('edit', settings_row.pk)
        self.assertNotContains(self.client.get(detail), 'super-secret-value')
        self.assertNotContains(self.client.get(edit), 'super-secret-value')

        # An empty password box keeps the stored credential.
        self.client.post(edit, {
            'host': 'smtp.example.com', 'port': 587, 'username': 'mailer',
            'password': '', 'from_email': 'no-reply@example.com', 'use_tls': 'on',
        })
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.password, 'super-secret-value')


class ProductFormRuleTests(TestCase):
    """``Product.save()`` raises bare ValueError; the form must catch it first."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        cls.category = Category.objects.create(name='Ghee')
        cls.product = make_product(category=cls.category)

    def setUp(self):
        self.client.force_login(self.superuser)

    def payload(self, **overrides):
        data = {
            'name': 'Test Ghee', 'size': '500ml', 'category': self.category.pk,
            'description': '', 'details': '',
            'max_price': '1000', 'discount_precent': '10',
            'max_quantity': '100', 'available_quantity': '50', 'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_price_is_not_editable(self):
        response = self.client.get(registry.get('products').url('edit', self.product.pk))
        self.assertNotContains(response, 'name="price"')

    def test_discount_above_100_is_rejected(self):
        url = registry.get('products').url('edit', self.product.pk)
        response = self.client.post(url, self.payload(discount_precent='150'))
        self.assertContains(response, 'Discount must be between 0 and 100')
        self.product.refresh_from_db()
        self.assertEqual(self.product.discount_precent, Decimal('10.00'))

    def test_available_above_maximum_is_rejected(self):
        url = registry.get('products').url('edit', self.product.pk)
        response = self.client.post(url, self.payload(max_quantity='10', available_quantity='99'))
        self.assertContains(response, 'cannot exceed the maximum quantity')

    def test_blank_mrp_is_rejected_rather_than_crashing_save(self):
        url = registry.get('products').url('edit', self.product.pk)
        response = self.client.post(url, self.payload(max_price=''))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_valid_save_recomputes_the_selling_price(self):
        url = registry.get('products').url('edit', self.product.pk)
        response = self.client.post(url, self.payload(max_price='2000', discount_precent='25'))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('1500'))


class OrderFulfilmentTests(TestCase):
    """Order money is derived, and shipping needs real tracking details."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        cls.customer = User.objects.create_user('buyer@example.com', 'pw-Str0ng!123')
        cls.address = UserAddress.objects.create(
            user=cls.customer, address_line1='1 Test Road', city='Morena',
            state='Madhya Pradesh', postal_code='476001', country='India',
        )
        cls.product = make_product()
        cls.order = Order.objects.create(
            user=cls.customer, address=cls.address,
            total_amount=Decimal('900.00'), payment_status='paid', status='pending',
        )
        OrderItem.objects.create(
            order=cls.order, product=cls.product, quantity=1, price=Decimal('900.00')
        )

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_orders_cannot_be_created_by_hand(self):
        self.assertFalse(registry.get('orders').can_add)
        self.assertEqual(self.client.get(registry.get('orders').url('add')).status_code, 403)

    def test_money_fields_are_not_editable(self):
        response = self.client.get(registry.get('orders').url('edit', self.order.pk))
        for name in ('final_amount', 'total_amount', 'discount_amount', 'shipping_fee'):
            self.assertNotContains(response, f'name="{name}"')

    def test_shipping_requires_a_tracking_number(self):
        url = registry.get('orders').url('edit', self.order.pk)
        response = self.client.post(url, {
            'status': 'shipped', 'payment_status': 'paid',
            'courier': '', 'awb_number': '', 'notes': '',
        })
        self.assertContains(response, 'Add courier and tracking details')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_tracking_number_requires_a_courier(self):
        url = registry.get('orders').url('edit', self.order.pk)
        response = self.client.post(url, {
            'status': 'processing', 'payment_status': 'paid',
            'courier': '', 'awb_number': 'ABC123', 'notes': '',
        })
        self.assertContains(response, 'Choose the shipping partner')

    def test_shipping_succeeds_with_full_details(self):
        url = registry.get('orders').url('edit', self.order.pk)
        response = self.client.post(url, {
            'status': 'shipped', 'payment_status': 'paid',
            'courier': 'delhivery', 'awb_number': 'abc123', 'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'shipped')
        self.assertEqual(self.order.awb_number, 'ABC123')  # normalised by save()
        self.assertIn('delhivery', self.order.tracking_url)

    def test_quick_status_rejects_shipped_and_unknown_values(self):
        url = reverse('admin_panel:order_status', args=[self.order.pk])
        for value in ('shipped', 'not-a-status'):
            with self.subTest(value=value):
                self.client.post(url, {'status': value})
                self.order.refresh_from_db()
                self.assertEqual(self.order.status, 'pending')

    def test_quick_status_applies_a_valid_move(self):
        self.client.post(reverse('admin_panel:order_status', args=[self.order.pk]),
                         {'status': 'processing'})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')

    def test_external_next_is_not_honoured(self):
        response = self.client.post(
            reverse('admin_panel:order_status', args=[self.order.pk]),
            {'status': 'processing', 'next': 'https://evil.example.com/'},
        )
        self.assertFalse(response['Location'].startswith('http'))


class ListQueryBudgetTests(TestCase):
    """Row count must not drive query count."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        product = make_product()
        for index in range(12):
            customer = User.objects.create_user(f'buyer{index}@example.com', 'pw-Str0ng!123')
            address = UserAddress.objects.create(
                user=customer, address_line1=f'{index} Test Road', city='Morena',
                state='Madhya Pradesh', postal_code='476001', country='India',
            )
            order = Order.objects.create(
                user=customer, address=address,
                total_amount=Decimal('900.00'), payment_status='paid',
            )
            OrderItem.objects.create(
                order=order, product=product, quantity=1, price=Decimal('900.00')
            )

    def setUp(self):
        self.client.force_login(self.superuser)

    def _count_queries(self, url):
        from django.db import connection, reset_queries
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        reset_queries()
        return len(captured)

    def test_order_list_query_count_is_flat(self):
        """Adding rows must not add queries — proves select_related is working."""
        url = registry.get('orders').url('list')
        with_twelve = self._count_queries(url)

        product = Product.objects.first()
        for index in range(12, 30):
            customer = User.objects.create_user(f'extra{index}@example.com', 'pw-Str0ng!123')
            order = Order.objects.create(
                user=customer, total_amount=Decimal('900.00'), payment_status='paid'
            )
            OrderItem.objects.create(
                order=order, product=product, quantity=1, price=Decimal('900.00')
            )

        self.assertEqual(self._count_queries(url), with_twelve)

    def test_dashboard_query_count_is_bounded(self):
        count = self._count_queries(reverse('admin_panel:dashboard'))
        self.assertLess(count, 40, f'Dashboard issued {count} queries')


class FilterTests(TestCase):
    """Filters must ignore anything they did not offer."""

    @classmethod
    def setUpTestData(cls):
        cls.active = make_product(name='Active', is_active=True)
        cls.hidden = make_product(name='Hidden', is_active=False)

    def test_choice_filter_ignores_unlisted_values(self):
        f = ChoiceFilter('size', 'Size', Product.SIZE_CHOICES)
        base = Product.objects.all()
        self.assertEqual(f.apply(base, {'size': '500ml'}).count(), 2)
        # Not in choices: filter is skipped rather than passed to the ORM.
        self.assertEqual(f.apply(base, {'size': "'; DROP TABLE--"}).count(), 2)

    def test_boolean_filter(self):
        f = BooleanFilter('is_active', 'Active')
        base = Product.objects.all()
        self.assertEqual(f.apply(base, {'is_active': 'yes'}).count(), 1)
        self.assertEqual(f.apply(base, {'is_active': 'no'}).count(), 1)
        self.assertEqual(f.apply(base, {'is_active': 'maybe'}).count(), 2)

    def test_date_range_filter_includes_the_whole_end_day(self):
        f = DateRangeFilter('created', 'Created', field='created_at')
        today = Product.objects.first().created_at.date().isoformat()
        self.assertEqual(
            f.apply(Product.objects.all(), {'created_from': today, 'created_to': today}).count(),
            2,
        )

    def test_unknown_sort_field_falls_back_to_the_default(self):
        resource = registry.get('products')
        ordered = resource.apply_ordering(Product.objects.all(), 'password; DROP TABLE')
        self.assertEqual(ordered.query.order_by, (resource.default_ordering,))


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')
        make_product(name='Exported', is_active=True)
        make_product(name='Excluded', is_active=False)

    def test_export_applies_the_active_filters(self):
        self.client.force_login(self.superuser)
        response = self.client.get(registry.get('products').url('export') + '?is_active=yes')
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        self.assertIn('Exported', body)
        self.assertNotIn('Excluded', body)


class AuditTrailTests(TestCase):
    """Panel writes land in the same LogEntry table the Django admin uses."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser('root@example.com', 'pw-Str0ng!123')

    def test_create_update_delete_are_logged(self):
        from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry

        self.client.force_login(self.superuser)
        resource = registry.get('categories')

        self.client.post(resource.url('add'), {'name': 'Audited', 'description': '', 'is_active': 'on'})
        category = Category.objects.get(name='Audited')
        self.assertTrue(LogEntry.objects.filter(object_id=category.pk, action_flag=ADDITION).exists())

        self.client.post(resource.url('edit', category.pk),
                         {'name': 'Audited v2', 'description': 'x', 'is_active': 'on'})
        self.assertTrue(LogEntry.objects.filter(object_id=category.pk, action_flag=CHANGE).exists())

        self.client.post(resource.url('delete', category.pk))
        self.assertTrue(LogEntry.objects.filter(object_id=category.pk, action_flag=DELETION).exists())
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())


class BrokenStrTests(TestCase):
    """A model with a broken ``__str__`` must not take a page down with it."""

    def test_safe_repr_survives_an_exploding_str(self):
        from .columns import safe_repr

        class Exploding:
            pk = 7

            def __str__(self):
                raise AttributeError('no such field')

        self.assertEqual(safe_repr(Exploding()), 'Exploding #7')

    def test_contact_query_str_uses_real_fields(self):
        from contact.models import SendUsQuery

        query = SendUsQuery.objects.create(
            first_name='Asha', last_name='Rao', email='asha@example.com',
            phone_number='+911234567890', subject='Delivery', message='Where is my order?',
        )
        self.assertIn('Asha Rao', str(query))
