# Order API Documentation

## Overview
This document describes the Order APIs for managing user orders, including listing orders, viewing order details, and downloading invoices.

---

## Endpoints

### 1. My Orders (List)
Get a paginated list of all orders for the authenticated user with optional filtering and search.

**Endpoint:** `GET /api/orders/my-orders/`

**Authentication:** Required (JWT Token)

**Query Parameters:**
- `search` (optional): Search by order ID, product name, or transaction ID
- `status` (optional): Filter by order status
  - Values: `pending`, `processing`, `completed`, `cancelled`
- `payment_status` (optional): Filter by payment status
  - Values: `pending`, `paid`, `failed`, `refunded`
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 10)

**Response Structure:**
```json
{
  "success": true,
  "count": 25,
  "next": "http://api.example.com/api/orders/my-orders/?page=2",
  "previous": null,
  "orders": [
    {
      "id": 123,
      "status": "completed",
      "status_display": "Completed",
      "payment_status": "paid",
      "payment_status_display": "Paid",
      "total_amount": "1000.00",
      "discount_amount": "100.00",
      "tax_amount": "162.00",
      "final_amount": "1062.00",
      "items_count": 3,
      "first_product_image": "http://api.example.com/media/products/2024/01/product.jpg",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

**Example Requests:**

1. Get all orders (paginated):
```bash
GET /api/orders/my-orders/
Authorization: Bearer <token>
```

2. Filter by status:
```bash
GET /api/orders/my-orders/?status=completed
Authorization: Bearer <token>
```

3. Filter by payment status:
```bash
GET /api/orders/my-orders/?payment_status=paid
Authorization: Bearer <token>
```

4. Search orders:
```bash
GET /api/orders/my-orders/?search=NAV_ORDER_123
Authorization: Bearer <token>
```

5. Combined filters:
```bash
GET /api/orders/my-orders/?status=completed&payment_status=paid&page=2&page_size=20
Authorization: Bearer <token>
```

---

### 2. Order Detail
Get detailed information about a specific order including all items, address, and transaction details.

**Endpoint:** `GET /api/orders/<order_id>/`

**Authentication:** Required (JWT Token)

**Path Parameters:**
- `order_id` (required): The ID of the order to retrieve

**Response Structure:**
```json
{
  "success": true,
  "order": {
    "id": 123,
    "status": "completed",
    "status_display": "Completed",
    "payment_status": "paid",
    "payment_status_display": "Paid",
    "address": {
      "id": 5,
      "address_line1": "123 Main Street",
      "address_line2": "Apt 4B",
      "city": "Mumbai",
      "state": "Maharashtra",
      "postal_code": "400001",
      "country": "India",
      "is_default": true
    },
    "total_amount": "1000.00",
    "discount_amount": "100.00",
    "coupon_code": "SAVE10",
    "tax_percentage": "18.00",
    "tax_amount": "162.00",
    "final_amount": "1062.00",
    "transaction_id": "NAV_ORDER_16_1234567890",
    "invoice_url": "http://api.example.com/api/orders/123/invoice/",
    "notes": "Please deliver before 5 PM",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:00:00Z",
    "items": [
      {
        "id": 456,
        "product": {
          "id": 10,
          "name": "Premium Honey",
          "size": "500g",
          "category_name": "Natural Products",
          "details": "100% Pure Honey",
          "price": "350.00",
          "max_price": "500.00",
          "discount_precent": "30.00",
          "image": "http://api.example.com/media/products/2024/01/honey.jpg"
        },
        "quantity": 2,
        "price": "350.00",
        "item_total": "700.00",
        "created_at": "2024-01-15T10:30:00Z"
      },
      {
        "id": 457,
        "product": {
          "id": 15,
          "name": "Organic Ghee",
          "size": "1kg",
          "category_name": "Dairy Products",
          "details": "Pure Cow Ghee",
          "price": "300.00",
          "max_price": "400.00",
          "discount_precent": "25.00",
          "image": "http://api.example.com/media/products/2024/01/ghee.jpg"
        },
        "quantity": 1,
        "price": "300.00",
        "item_total": "300.00",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "latest_transaction": {
      "id": 789,
      "transaction_order_id": "NAV_ORDER_16_1234567890",
      "gateway_payment_id": "CF123456789",
      "payment_method": "Cashfree",
      "payment_instrument_type": "UPI",
      "status": "success",
      "amount": "1062.00",
      "created_at": "2024-01-15T10:32:00Z",
      "updated_at": "2024-01-15T10:35:00Z"
    }
  }
}
```

**Example Request:**
```bash
GET /api/orders/123/
Authorization: Bearer <token>
```

**Error Responses:**

1. Order not found:
```json
{
  "success": false,
  "error": "Order not found"
}
```
Status Code: `404 NOT FOUND`

2. Unauthorized access:
```json
{
  "detail": "Authentication credentials were not provided."
}
```
Status Code: `401 UNAUTHORIZED`

---

### 3. Download Invoice
Download the invoice PDF for a paid order.

**Endpoint:** `GET /api/orders/<order_id>/invoice/`

**Authentication:** Required (JWT Token)

**Path Parameters:**
- `order_id` (required): The ID of the order

**Response:**
- Success: PDF file download
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="invoice_123.pdf"`

**Example Request:**
```bash
GET /api/orders/123/invoice/
Authorization: Bearer <token>
```

**Error Responses:**

1. Invoice not available (unpaid order):
```json
{
  "success": false,
  "error": "Invoice is only available for paid orders"
}
```
Status Code: `400 BAD REQUEST`

2. Order not found:
```json
{
  "success": false,
  "error": "Order not found"
}
```
Status Code: `404 NOT FOUND`

3. Invoice generation failed:
```json
{
  "success": false,
  "error": "Failed to generate invoice: <error_details>"
}
```
Status Code: `500 INTERNAL SERVER ERROR`

---

## Data Models

### Order Status Values
- `pending`: Order created but payment pending
- `processing`: Payment successful, order being processed
- `completed`: Order fulfilled and delivered
- `cancelled`: Order cancelled

### Payment Status Values
- `pending`: Payment not yet completed
- `paid`: Payment successful
- `failed`: Payment failed
- `refunded`: Payment refunded

---

## Best Practices

1. **Pagination**: Always implement pagination for order lists to improve performance
2. **Caching**: Cache order list responses where appropriate
3. **Error Handling**: Always check the `success` field in responses
4. **Images**: Product images are returned as absolute URLs including the base domain
5. **Transactions**: The `latest_transaction` field provides payment gateway details
6. **Invoice**: Invoice URL is only available when `payment_status` is `paid`

---

## Rate Limiting
These endpoints are subject to standard API rate limiting. Please refer to the main API documentation for rate limit details.

---

## Support
For API support, please contact the development team or refer to the main API documentation.
