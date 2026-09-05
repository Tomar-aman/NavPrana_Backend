# NavPrana Admin Panel

A custom staff dashboard at **`/panel/`**, built with Django templates plus
hand-written CSS and vanilla JavaScript. It runs alongside the stock Django
admin at `/admin/` — both remain fully usable and share one permission model
and one audit trail.

---

## Running it

```bash
# development
python manage.py runserver            # then open http://127.0.0.1:1921/panel/

# production
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

The panel adds **no models and no migrations**, and **no new dependencies**.
Nothing beyond `collectstatic` is needed to deploy it.

## Getting an account

Access requires `is_active` **and** `is_staff`. A regular customer's
credentials are rejected at the login form.

```bash
# a full-access administrator
python manage.py createsuperuser

# reset a forgotten password
python manage.py changepassword someone@navprana.com
```

To grant limited access without handing out superuser: create the user, tick
**Staff**, then assign a role under **System → Roles**. Roles are Django's own
`auth.Group` objects, so they apply to `/admin/` identically.

## What is in it

| Area | Contents |
|---|---|
| Dashboard | Revenue, orders, awaiting fulfilment, customers, AOV, failed payments; revenue/orders trend, order-status donut, payment-method split, best sellers, new-customer trend, latest orders, low stock, recent activity |
| Commerce | Orders (bespoke detail page), Transactions, Active Carts |
| Catalog | Products, Categories, Product Reviews, Lab Reports |
| Customers | Users, Addresses, OTPs, Newsletter Subscribers |
| Marketing | Coupons, Coupon Redemptions, Spin-Wheel Coupons, Spin Limits |
| Content | Blog Posts, Blog Categories, FAQs, FAQ Categories, Instagram Reels, Social Links |
| Support | Contact Queries, Contact Numbers, Contact Emails, Office Addresses |
| System | Roles, Pricing Settings, Email Settings, Activity Log |

Every list supports search, filters, column sorting, page sizing, CSV export
and (where useful) bulk actions. `/` focuses the global search box.

## Architecture

```
admin_panel/
  registry.py     PanelResource — the declarative description of a model
  resources.py    one registration per model: columns, filters, form rules
  columns.py      column specs and cell rendering
  filters.py      choice / boolean / relation / date-range filters
  forms.py        generic form factory + model-specific forms
  actions.py      bulk action handlers
  metrics.py      all dashboard queries
  navigation.py   permission-filtered sidebar
  mixins.py       access control
  audit.py        writes to django.contrib.admin.LogEntry
  views/          generic CRUD, dashboard, auth, orders, activity, search
templates/panel/  base layout, partials, CRUD pages
static/panel/     panel.css, panel.js (includes the SVG charts)
```

### Adding a model to the panel

Append one `registry.register(...)` call in `resources.py`. The sidebar entry,
list page, filters, detail page, forms, CSV export and permission checks all
follow from it. No new view, URL or template is required.

```python
registry.register(
    PanelResource(
        key='widgets',
        model=Widget,
        group='Catalog',
        icon='box',
        columns=(
            Column('name', 'Widget', is_link=True),
            Column('price', 'Price', kind='currency'),
            Column('is_active', 'Active', kind='bool'),
        ),
        search_fields=('name',),
        filters=(BooleanFilter('is_active', 'Active'),),
        form_fields=('name', 'price', 'is_active'),
    )
)
```

Permissions come from Django: `app_label.view_widget`, `add_`, `change_`,
`delete_`. A user without `view` never sees the link, and the URL 403s.

Give a resource a bespoke page by subclassing `PanelResource` and pointing
`detail_template` at your own file (see `OrderResource`), and register a custom
view class in `views/__init__.py: DETAIL_VIEW_OVERRIDES`. `LIST_VIEW_OVERRIDES`
does the same for the list page — **Pricing Settings** uses it to open its one
row instead of listing it.

## Design notes

* **Money is read-only where the model computes it.** An order prices itself
  once, as it is created, from the coupon, the subtotal and **System → Pricing
  Settings**; `Product.save()` derives `price` from MRP and discount. Neither
  set of figures is offered for editing.
* **Pricing changes never reach a placed order.** Every order stores the
  shipping, handling and prepaid-discount figures it was quoted, so editing
  Pricing Settings re-prices new orders only. `Order.reprice()` is the
  deliberate way to re-run the sums on an existing one.
* **OTPs are readable, not writable.** Support needs to see the code a customer
  was sent, so the list shows it and says whether it is still live. Nothing can
  be added or edited there, the list has no CSV export, and the section is
  behind `users.view_otp` — a working code is a working credential.
* **Orders cannot be created by hand.** They come from checkout, together with
  a cart, coupon and payment session.
* **Filters are built from data, not just choices.** Most orders carry
  `payment_method='cashfree'`, a value absent from `PAYMENT_METHOD_CHOICES`;
  the filter reads the distinct values in the table.
* **The audit trail is `django.contrib.admin.LogEntry`**, so panel and
  `/admin/` actions appear in one history under **System → Activity Log**.
* **Charts are hand-drawn SVG.** No CDN, no vendored bundle, and they read the
  same CSS custom properties as the rest of the UI, so dark mode is free.

## Tests

```bash
python manage.py test admin_panel
```

Covers access control, permission-scoped navigation, secret non-exposure,
the model-specific form rules, filter validation, CSV export, the audit trail,
the pricing singleton (including that a placed order keeps the fees it was
quoted), the OTP section's read-only rules, and a query-count budget that fails
if `select_related` regresses.

> The shared dev Postgres role has no `CREATEDB` grant, so `manage.py test`
> cannot create its test database there. Run the suite against SQLite with a
> settings module that overrides `DATABASES` — nothing here depends on
> Postgres-specific SQL.
