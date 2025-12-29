# Cashfree Payment Flow Diagram

## Complete Payment Flow

```
┌─────────────┐
│   Customer  │
└──────┬──────┘
       │
       │ 1. Adds products to cart
       │    and clicks "Pay Now"
       ▼
┌─────────────────────┐
│   Your Frontend     │
│   (React/Next.js)   │
└──────┬──────────────┘
       │
       │ 2. POST /api/payments/cashfree/create-order/
       │    {products, coupon_code, etc}
       ▼
┌─────────────────────────────────────────┐
│   Django Backend                        │
│                                         │
│   3. Create Order in Database          │
│      - Calculate total amount           │
│      - Apply coupon discount            │
│      - Calculate tax                    │
│                                         │
│   4. Call Cashfree API                 │
│      - Create payment session           │
│      - Get payment_session_id           │
│                                         │
│   5. Create TransactionLog             │
│      - Store order details              │
│      - Status: pending                  │
└──────┬──────────────────────────────────┘
       │
       │ 6. Return response with:
       │    - payment_url
       │    - payment_session_id
       │    - order_token
       ▼
┌─────────────────────┐
│   Your Frontend     │
└──────┬──────────────┘
       │
       │ 7. Redirect to Cashfree
       │    payment page or use SDK
       ▼
┌─────────────────────┐
│   Cashfree          │
│   Payment Gateway   │
│                     │
│   - User selects    │
│     payment method  │
│   - UPI / Card /    │
│     Net Banking     │
│   - Enters details  │
│   - Completes       │
│     payment         │
└──────┬──────────────┘
       │
       ├───────────────────────────────────────┐
       │                                       │
       │ 8. Webhook (Async)                    │ 9. Return URL (Sync)
       │    Server-to-Server                   │    User Redirect
       ▼                                       ▼
┌──────────────────────┐              ┌──────────────────────┐
│ Webhook Handler      │              │ Return URL Handler   │
│                      │              │                      │
│ POST /webhook/       │              │ GET /return/?order_id│
│                      │              │                      │
│ 10. Verify signature │              │ 14. Verify payment   │
│                      │              │     status from API  │
│ 11. Decode payload   │              │                      │
│                      │              │ 15. Redirect to      │
│ 12. Update order:    │              │     success/fail page│
│     - Mark as paid   │              │                      │
│     - Update status  │              └──────────────────────┘
│                      │
│ 13. Send email/notif │
│     to customer      │
└──────────────────────┘

```

## Sequence Diagram (Detailed)

```
Customer    Frontend        Backend         Cashfree        Webhook         Return
   │           │              │                │               │              │
   │──────────>│              │                │               │              │
   │  Browse   │              │                │               │              │
   │  & Add to │              │                │               │              │
   │  Cart     │              │                │               │              │
   │           │              │                │               │              │
   │───────────>              │                │               │              │
   │  Checkout │              │                │               │              │
   │           │              │                │               │              │
   │           │──────────────>               │               │              │
   │           │ Create Order │                │               │              │
   │           │              │                │               │              │
   │           │              │────────────────>              │              │
   │           │              │ Create Payment │               │              │
   │           │              │   Session      │               │              │
   │           │              │                │               │              │
   │           │              │<────────────────               │              │
   │           │              │ payment_url    │               │              │
   │           │              │ session_id     │               │              │
   │           │              │                │               │              │
   │           │<─────────────                 │               │              │
   │           │ Payment URL  │                │               │              │
   │           │              │                │               │              │
   │───────────────────────────────────────────>              │              │
   │           Redirect to Cashfree            │               │              │
   │           │              │                │               │              │
   │<──────────────────────────────────────────               │              │
   │           Payment Page   │                │               │              │
   │           │              │                │               │              │
   │──────────>│              │                │               │              │
   │ Complete  │              │                │               │              │
   │ Payment   │              │                │               │              │
   │           │              │                │               │              │
   │           │              │                │──────────────>              │
   │           │              │                │ Payment       │              │
   │           │              │                │ Notification  │              │
   │           │              │                │               │              │
   │           │              │                │<─────────────               │
   │           │              │                │ Webhook Call  │              │
   │           │              │                │               │              │
   │           │              │<───────────────────────────────              │
   │           │              │ Update Order Status            │              │
   │           │              │ Mark as Paid                   │              │
   │           │              │                │               │              │
   │           │              │────────────────────────────────>             │
   │           │              │             200 OK             │              │
   │           │              │                │               │              │
   │<──────────────────────────────────────────────────────────────────────>
   │           Redirect to Return URL           │               │              │
   │           │              │                │               │              │
   │           │              │<───────────────────────────────────────────>
   │           │              │ Verify Payment & Redirect     │              │
   │           │              │                │               │              │
   │<──────────              │                │               │              │
   │ Success   │              │                │               │              │
   │ Page      │              │                │               │              │
```

## Error Handling Flow

```
┌─────────────────────┐
│  Payment Initiated  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  User on Cashfree   │
│  Payment Page       │
└──────┬──────────────┘
       │
       ├──────────────────────┬────────────────────┐
       │                      │                    │
       │ Success              │ Failed             │ Abandoned
       ▼                      ▼                    ▼
┌────────────────┐    ┌────────────────┐   ┌─────────────────┐
│ PAYMENT_       │    │ PAYMENT_       │   │ PAYMENT_USER_   │
│ SUCCESS_       │    │ FAILED_        │   │ DROPPED_        │
│ WEBHOOK        │    │ WEBHOOK        │   │ WEBHOOK         │
└───────┬────────┘    └───────┬────────┘   └────────┬────────┘
        │                     │                      │
        │ Update Order        │ Update Order         │ Cancel Order
        │ Status: Paid        │ Status: Failed       │ Status: Cancelled
        │                     │                      │
        ▼                     ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│           Redirect to Appropriate Page                  │
│                                                          │
│  Success: /payment-success?order_id=123&status=success  │
│  Failed:  /payment-failed?order_id=123&status=failed    │
│  Dropped: /payment-failed?order_id=123&status=cancelled │
└─────────────────────────────────────────────────────────┘
```

## Database State Changes

```
Order Creation
│
├─ Order.status = 'pending'
├─ Order.payment_status = 'pending'
└─ TransactionLog.status = 'pending'

Payment Success (Webhook)
│
├─ Order.status = 'processing'
├─ Order.payment_status = 'paid'
├─ TransactionLog.status = 'success'
└─ Inventory updated

Payment Failed (Webhook)
│
├─ Order.status = 'cancelled'
├─ Order.payment_status = 'failed'
└─ TransactionLog.status = 'failed'

Payment Abandoned (Webhook)
│
├─ Order.status = 'cancelled'
├─ Order.payment_status = 'pending'
└─ TransactionLog.status = 'cancelled'

Refund Initiated
│
├─ Order.payment_status = 'refunded'
├─ TransactionLog.status = 'refunded'
└─ Inventory restored
```

## Security Flow

```
┌─────────────────────┐
│ Cashfree Webhook    │
│ Payload Received    │
└──────┬──────────────┘
       │
       │ 1. Extract signature & timestamp
       ▼
┌──────────────────────────────────┐
│ Verify Webhook Signature         │
│                                  │
│ signature_string =               │
│   timestamp + raw_body           │
│                                  │
│ expected_signature =             │
│   HMAC_SHA256(                   │
│     secret_key,                  │
│     signature_string             │
│   )                              │
│                                  │
│ Compare signatures               │
└──────┬───────────────────────────┘
       │
       ├──────────────┬─────────────┐
       │              │             │
   ✓ Valid        ✗ Invalid    ✗ Expired
       │              │             │
       ▼              ▼             ▼
┌─────────────┐  ┌──────────┐  ┌──────────┐
│ Process     │  │ Reject   │  │ Reject   │
│ Webhook     │  │ 401      │  │ 401      │
└─────────────┘  └──────────┘  └──────────┘
```

## Payment Methods Supported

```
Cashfree Payment Gateway
│
├─ UPI
│  ├─ QR Code
│  ├─ UPI ID
│  └─ Intent (PhonePe, GPay, etc.)
│
├─ Cards
│  ├─ Credit Cards
│  │  ├─ Visa
│  │  ├─ Mastercard
│  │  ├─ RuPay
│  │  └─ American Express
│  │
│  └─ Debit Cards
│     ├─ Visa
│     ├─ Mastercard
│     └─ RuPay
│
├─ Net Banking
│  ├─ All Major Banks
│  └─ 50+ Banks Supported
│
├─ Wallets
│  ├─ Paytm
│  ├─ PhonePe
│  ├─ Amazon Pay
│  └─ More...
│
└─ Pay Later
   ├─ Simpl
   └─ LazyPay
```
