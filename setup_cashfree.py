"""
Quick Setup Script for Cashfree Integration

Run this after completing the integration to ensure everything is set up correctly.
"""

print("🚀 Cashfree Payment Gateway Setup")
print("=" * 50)
print()

# Step 1: Environment Variables
print("✓ Step 1: Add to your .env file:")
print("-" * 50)
print("""
CASHFREE_APP_ID=your_app_id_here
CASHFREE_SECRET_KEY=your_secret_key_here
CASHFREE_API_VERSION=2023-08-01
CASHFREE_ENVIRONMENT=TEST
""")
print()

# Step 2: Django Settings
print("✓ Step 2: Add to config/settings.py:")
print("-" * 50)
print("""
from decouple import config

# Cashfree Settings
CASHFREE_APP_ID = config('CASHFREE_APP_ID')
CASHFREE_SECRET_KEY = config('CASHFREE_SECRET_KEY')
CASHFREE_API_VERSION = config('CASHFREE_API_VERSION', default='2023-08-01')
CASHFREE_ENVIRONMENT = config('CASHFREE_ENVIRONMENT', default='TEST')
""")
print()

# Step 3: Run Migrations
print("✓ Step 3: Run these commands:")
print("-" * 50)
print("""
python manage.py makemigrations transactions
python manage.py migrate transactions
""")
print()

# Step 4: Test the integration
print("✓ Step 4: Test the integration:")
print("-" * 50)
print("""
# Start your development server
python manage.py runserver

# Make a test payment request
POST http://localhost:8000/api/payments/cashfree/create-order/
Authorization: Bearer <your_token>

{
    "products": [
        {"product_id": 1, "quantity": 1}
    ]
}
""")
print()

# Step 5: Webhook setup
print("✓ Step 5: Setup webhooks:")
print("-" * 50)
print("""
1. For local testing, use ngrok:
   ngrok http 8000
   
2. Configure webhook in Cashfree dashboard:
   https://your-domain.com/api/payments/cashfree/webhook/

3. Select these events:
   - PAYMENT_SUCCESS_WEBHOOK
   - PAYMENT_FAILED_WEBHOOK  
   - PAYMENT_USER_DROPPED_WEBHOOK
   - REFUND_STATUS_WEBHOOK
""")
print()

# API Endpoints
print("✓ Available API Endpoints:")
print("-" * 50)
print("""
POST   /api/payments/cashfree/create-order/   - Create payment
GET    /api/payments/cashfree/status/<id>/    - Check status
GET    /api/payments/cashfree/return/         - Return handler
POST   /api/payments/cashfree/refund/         - Initiate refund
POST   /api/payments/cashfree/webhook/        - Webhook handler
""")
print()

print("📚 Documentation: See CASHFREE_INTEGRATION.md for detailed guide")
print("=" * 50)
print("✅ Setup complete! Read CASHFREE_INTEGRATION.md for full details.")
