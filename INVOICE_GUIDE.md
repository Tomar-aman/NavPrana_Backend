# Invoice Generation Test & Usage Guide

## Installation

ReportLab is already in requirements.txt:
```bash
pip install reportlab==4.4.2
```

## Features

### 1. **Automatic Invoice Generation**
Invoices are automatically generated when an order is marked as paid via webhook.

### 2. **Manual Generation Commands**

#### Generate for specific order:
```bash
python manage.py generate_invoices --order-id 16
```

#### Generate for all paid orders without invoices:
```bash
python manage.py generate_invoices --all-paid
```

#### Regenerate all invoices (overwrite existing):
```bash
python manage.py generate_invoices --all-paid --regenerate
```

### 3. **Download Invoice API**

**Endpoint:** `GET /api/orders/<order_id>/invoice/`

**Authentication:** Required

**Response:** PDF file download

**Example:**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/orders/16/invoice/ \
  -o invoice_16.pdf
```

### 4. **Invoice in Order List**

Orders now include `invoice_url` in API responses:

```json
{
  "id": 16,
  "status": "processing",
  "payment_status": "paid",
  "final_amount": 2184.00,
  "invoice_url": "http://localhost:8000/api/orders/16/invoice/",
  ...
}
```

## Invoice Content

The PDF invoice includes:

- ✅ Company logo (if logo.png exists in static/)
- ✅ Company details & GSTIN
- ✅ Invoice number & date
- ✅ Customer billing/shipping address
- ✅ Itemized product list with quantities & prices
- ✅ Subtotal, discount, tax breakdown
- ✅ Grand total
- ✅ Payment details (method, transaction ID, bank reference)
- ✅ Terms & conditions
- ✅ Professional formatting with colors & borders

## Customization

Edit `orders/invoice_utils.py` to customize:

- Company name, address, GSTIN
- Logo path
- Colors and styling
- Terms & conditions
- Page layout

## File Storage

Invoices are stored in: `MEDIA_ROOT/invoices/YYYY/MM/`

Example: `media/invoices/2026/01/invoice_16_20260116.pdf`

## Error Handling

- Invoice generation errors are logged but don't fail payment processing
- Missing invoices are auto-generated on download request
- Only paid orders can generate invoices

## Testing

1. **Make a test payment** (order gets marked as paid via webhook)
2. **Check order details:** `GET /api/orders/my-orders/`
3. **Download invoice:** Click the `invoice_url` or call the endpoint
4. **Manual regeneration:** `python manage.py generate_invoices --order-id <ID> --regenerate`

## Production Checklist

- [ ] Update company details in `invoice_utils.py`
- [ ] Add company logo as `static/logo.png`
- [ ] Configure MEDIA_ROOT and MEDIA_URL in settings
- [ ] Set up file storage (S3/Azure for production)
- [ ] Test invoice generation with real data
- [ ] Verify PDF rendering on different devices
