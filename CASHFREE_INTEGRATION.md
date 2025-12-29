# Cashfree Payment Gateway Integration

This document explains how to integrate and use the Cashfree payment gateway in your Django application.

## Table of Contents
- [Setup](#setup)
- [Configuration](#configuration)
- [Payment Flow](#payment-flow)
- [API Endpoints](#api-endpoints)
- [Webhook Setup](#webhook-setup)
- [Testing](#testing)
- [Production Checklist](#production-checklist)

---

## Setup

### 1. Environment Variables

Add these variables to your `.env` file:

```env
# Cashfree Configuration
CASHFREE_APP_ID=your_cashfree_app_id
CASHFREE_SECRET_KEY=your_cashfree_secret_key
CASHFREE_API_VERSION=2023-08-01
CASHFREE_ENVIRONMENT=TEST  # Change to PROD for production

# Optional: Base URLs (automatically set based on environment)
# TEST: https://sandbox.cashfree.com/pg
# PROD: https://api.cashfree.com/pg
```

### 2. Get Cashfree Credentials

1. Sign up at [Cashfree Dashboard](https://merchant.cashfree.com/)
2. Go to **Developers** > **API Keys**
3. Copy your **App ID** and **Secret Key**
4. For testing, use the Sandbox credentials
5. For production, get Production credentials after KYC verification

### 3. Django Settings

Add to your `config/settings.py`:

```python
# Cashfree Settings
CASHFREE_APP_ID = config('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = config('CASHFREE_SECRET_KEY')
CASHFREE_API_VERSION = config('CASHFREE_API_VERSION', default='2023-08-01')
CASHFREE_ENVIRONMENT = config('CASHFREE_ENVIRONMENT', default='TEST')
```

### 4. Run Migrations

Run migrations to add Cashfree-specific fields to the database:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Configuration

### Database Model Updates

The `TransactionLog` model now includes these Cashfree-specific fields:

- `cashfree_order_id` - Cashfree's internal order ID
- `payment_session_id` - Session ID for payment
- `order_token` - Token for SDK integration
- `payment_group` - Payment method group (upi, credit_card, etc.)
- `bank_reference` - Bank reference number
- `auth_id` - Gateway authorization ID

---

## Payment Flow

### Standard Payment Flow

```
1. User adds products to cart
2. User clicks "Pay Now"
   ↓
3. Backend creates Order in database
   POST /api/payments/cashfree/create-order/
   ↓
4. Backend calls Cashfree API to create payment session
   Returns: payment_session_id, payment_url
   ↓
5. Frontend redirects user to Cashfree payment page
   URL: payment_url or use payment_session_id with Cashfree SDK
   ↓
6. User completes payment on Cashfree
   ↓
7. Cashfree sends webhook to your server
   POST /api/payments/cashfree/webhook/
   ↓
8. Backend verifies payment and updates order status
   ↓
9. User redirected back to return_url
   GET /api/payments/cashfree/return/?order_id=ORDER_123
   ↓
10. Frontend shows success/failure message
```

---

## API Endpoints

### 1. Create Order and Payment Session

**Endpoint:** `POST /api/payments/cashfree/create-order/`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "products": [
        {
            "product_id": 1,
            "quantity": 2
        },
        {
            "product_id": 3,
            "quantity": 1
        }
    ],
    "coupon_code": "SAVE20",  // Optional
    "tax_percentage": 18.0,   // Optional
    "notes": "Gift wrap required",  // Optional
    "return_url": "https://yourapp.com/payment-success",  // Optional
    "notify_url": "https://yourbackend.com/api/payments/cashfree/webhook/"  // Optional
}
```

**Response (Success):**
```json
{
    "success": true,
    "order_id": 123,
    "transaction_id": "ORDER_123_1672531200",
    "payment_session_id": "session_abc123xyz",
    "payment_url": "https://sandbox.cashfree.com/order/#session_abc123xyz",
    "order_token": "token_for_sdk_integration",
    "order_summary": {
        "order_number": 123,
        "total_amount": 1000.0,
        "discount_amount": 200.0,
        "tax_amount": 180.0,
        "final_amount": 980.0,
        "currency": "INR",
        "items_count": 2
    }
}
```

**Frontend Integration:**

```javascript
// Option 1: Redirect to payment URL
window.location.href = response.payment_url;

// Option 2: Use Cashfree Checkout SDK (Recommended)
const cashfree = new Cashfree({
    mode: "sandbox" // or "production"
});

cashfree.checkout({
    paymentSessionId: response.payment_session_id,
    returnUrl: "https://yourapp.com/payment-success"
});
```

### 2. Check Payment Status

**Endpoint:** `GET /api/payments/cashfree/status/<order_id>/`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
    "success": true,
    "order_id": "ORDER_123_1672531200",
    "payment_status": true,
    "order_status": "PAID",
    "payment_method": "UPI",
    "payment_time": "2023-01-01T12:00:00+05:30",
    "amount": 980.0,
    "transaction_status": "success"
}
```

### 3. Handle Return URL

**Endpoint:** `GET /api/payments/cashfree/return/?order_id=ORDER_123`

This endpoint is called by Cashfree after payment completion. It:
- Verifies payment status
- Updates transaction in database
- Redirects user to success/failure page

**No manual calling required** - Cashfree handles this automatically.

### 4. Initiate Refund

**Endpoint:** `POST /api/payments/cashfree/refund/`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
    "order_id": "ORDER_123_1672531200",
    "refund_amount": 100.0,  // Optional - defaults to full amount
    "refund_note": "Customer requested refund"
}
```

**Response:**
```json
{
    "success": true,
    "refund_id": "REFUND_123_1672531200",
    "cf_refund_id": "123456",
    "refund_status": "PENDING",
    "refund_amount": 100.0
}
```

---

## Webhook Setup

### 1. Configure Webhook URL in Cashfree Dashboard

1. Go to **Cashfree Dashboard** > **Developers** > **Webhooks**
2. Add webhook URL: `https://yourdomain.com/api/payments/cashfree/webhook/`
3. Select events to receive:
   - PAYMENT_SUCCESS_WEBHOOK
   - PAYMENT_FAILED_WEBHOOK
   - PAYMENT_USER_DROPPED_WEBHOOK
   - REFUND_STATUS_WEBHOOK

### 2. Webhook Security

Cashfree sends these headers with webhooks:
- `x-webhook-signature` - HMAC SHA256 signature
- `x-webhook-timestamp` - Request timestamp

Our implementation automatically:
- Verifies signature using your secret key
- Rejects invalid signatures
- Processes only valid webhooks

### 3. Webhook Events Handled

| Event | Description | Action |
|-------|-------------|--------|
| PAYMENT_SUCCESS_WEBHOOK | Payment completed | Mark order as paid, update inventory |
| PAYMENT_FAILED_WEBHOOK | Payment failed | Mark order as failed |
| PAYMENT_USER_DROPPED_WEBHOOK | User abandoned payment | Cancel order |
| REFUND_STATUS_WEBHOOK | Refund status update | Update refund status |

---

## Testing

### 1. Test Cards (Sandbox)

Cashfree provides test cards for sandbox testing:

**Successful Payment:**
- Card Number: `4111 1111 1111 1111`
- CVV: Any 3 digits
- Expiry: Any future date
- Name: Any name

**Failed Payment:**
- Card Number: `4242 4242 4242 4242`
- CVV: Any 3 digits
- Expiry: Any future date

**Test UPI:**
- UPI ID: `success@ybl`
- Use test mode in Cashfree SDK

### 2. Test Flow

1. Create an order using the API
2. Use test credentials
3. Complete payment with test card
4. Check webhook logs
5. Verify order status in database

### 3. Webhook Testing

For local development, use ngrok to expose your local server:

```bash
ngrok http 8000
```

Then use the ngrok URL in Cashfree dashboard:
```
https://abc123.ngrok.io/api/payments/cashfree/webhook/
```

---

## Production Checklist

### Before Going Live:

- [ ] Complete KYC verification in Cashfree
- [ ] Get Production API credentials
- [ ] Update `.env` with production credentials:
  ```env
  CASHFREE_ENVIRONMENT=PROD
  CASHFREE_APP_ID=prod_app_id
  CASHFREE_SECRET_KEY=prod_secret_key
  ```
- [ ] Configure production webhook URL in Cashfree dashboard
- [ ] Test with small amounts first
- [ ] Set up proper error logging and monitoring
- [ ] Configure return URLs correctly
- [ ] Test refund flow
- [ ] Review transaction limits with Cashfree
- [ ] Enable relevant payment methods (UPI, Cards, Net Banking)
- [ ] Set up settlement account
- [ ] Test webhook signature verification
- [ ] Configure proper CORS settings
- [ ] Set up SSL certificate (required for production)

### Security Best Practices:

1. **Never expose credentials** - Use environment variables
2. **Always verify webhook signatures** - Already implemented
3. **Use HTTPS** - Required for production
4. **Validate amounts** - Check order amount matches payment
5. **Idempotency** - Handle duplicate webhooks gracefully
6. **Logging** - Log all payment events for audit

### Monitoring:

- Set up alerts for failed payments
- Monitor webhook delivery success rate
- Track payment success/failure rates
- Review settlement reports regularly

---

## Example Integration Code

### React/Next.js Frontend

```javascript
import { useState } from 'react';

const CheckoutPage = () => {
    const [loading, setLoading] = useState(false);
    
    const initiatePayment = async () => {
        setLoading(true);
        
        try {
            // Create order
            const response = await fetch('/api/payments/cashfree/create-order/', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    products: cartItems,
                    coupon_code: appliedCoupon,
                    return_url: window.location.origin + '/payment-success'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Redirect to Cashfree payment page
                window.location.href = data.payment_url;
                
                // OR use Cashfree SDK (recommended)
                const cashfree = new Cashfree({
                    mode: process.env.NODE_ENV === 'production' ? 'production' : 'sandbox'
                });
                
                cashfree.checkout({
                    paymentSessionId: data.payment_session_id,
                    returnUrl: window.location.origin + '/payment-success'
                });
            }
        } catch (error) {
            console.error('Payment initiation failed:', error);
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <button onClick={initiatePayment} disabled={loading}>
            {loading ? 'Processing...' : 'Pay Now'}
        </button>
    );
};
```

### Payment Success Page

```javascript
const PaymentSuccessPage = () => {
    const [verifying, setVerifying] = useState(true);
    const [paymentStatus, setPaymentStatus] = useState(null);
    
    useEffect(() => {
        const orderId = new URLSearchParams(window.location.search).get('order_id');
        
        // Verify payment status
        fetch(`/api/payments/cashfree/status/${orderId}/`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        })
        .then(res => res.json())
        .then(data => {
            setPaymentStatus(data);
            setVerifying(false);
        });
    }, []);
    
    if (verifying) return <div>Verifying payment...</div>;
    
    return (
        <div>
            {paymentStatus?.payment_status ? (
                <div>
                    <h1>Payment Successful! 🎉</h1>
                    <p>Order ID: {paymentStatus.order_id}</p>
                    <p>Amount: ₹{paymentStatus.amount}</p>
                </div>
            ) : (
                <div>
                    <h1>Payment Failed</h1>
                    <p>Please try again</p>
                </div>
            )}
        </div>
    );
};
```

---

## Troubleshooting

### Common Issues:

1. **Webhook signature verification fails**
   - Ensure secret key is correct
   - Check that webhook body is not modified

2. **Payment URL not working**
   - Verify API credentials
   - Check CASHFREE_ENVIRONMENT setting
   - Ensure order amount is valid

3. **Webhooks not received**
   - Check webhook URL in dashboard
   - Verify URL is publicly accessible
   - Check server logs for incoming requests

4. **Database errors**
   - Run migrations: `python manage.py migrate`
   - Check for duplicate transaction IDs

---

## Support

- **Cashfree Documentation:** https://docs.cashfree.com/
- **Cashfree Support:** support@cashfree.com
- **Sandbox Dashboard:** https://sandbox.cashfree.com/merchant
- **Production Dashboard:** https://merchant.cashfree.com/

---

## License

This integration is part of the NavPrana Backend project.
