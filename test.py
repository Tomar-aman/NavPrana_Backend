"""
Test script to verify PhonePe integration
Run this standalone to check if your credentials are working

Usage:
python test_phonepe_integration.py
"""

import hashlib
import base64
import json
import requests
import time

# ============================================
# CONFIGURATION - Update these if needed
# ============================================
MERCHANT_ID = 'PHONEPEPGUAT'
SALT_KEY = 'c817ffaf-8471-48b5-a7e2-a27e5b7efbd3'
SALT_INDEX = '1'
BASE_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"

# Use webhook.site for testing callbacks
# Go to https://webhook.site/ and get your unique URL
TEST_CALLBACK_URL = "https://webhook.site/your-unique-id"  # Replace with your webhook.site URL


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def test_phonepe_payment():
    """Test PhonePe payment initiation"""
    print_section("PHONEPE PAYMENT INTEGRATION TEST")
    
    # Step 1: Configuration Check
    print_section("Step 1: Configuration Check")
    print(f"✓ Merchant ID: {MERCHANT_ID}")
    print(f"✓ Salt Key: {SALT_KEY[:10]}...{SALT_KEY[-10:]}")
    print(f"✓ Salt Index: {SALT_INDEX}")
    print(f"✓ Base URL: {BASE_URL}")
    print(f"✓ Callback URL: {TEST_CALLBACK_URL}")
    
    # Step 2: Create Payload
    print_section("Step 2: Creating Payment Payload")
    
    transaction_id = f"TEST_TXN_{int(time.time())}"
    
    payload = {
        "merchantId": MERCHANT_ID,
        "merchantTransactionId": transaction_id,
        "merchantUserId": "TEST_USER_123",
        "amount": 10000,  # 100 INR in paise
        "redirectUrl": TEST_CALLBACK_URL,
        "redirectMode": "POST",
        "callbackUrl": TEST_CALLBACK_URL,
        "mobileNumber": "9999999999",  # Test mobile number
        "paymentInstrument": {
            "type": "PAY_PAGE"
        }
    }
    
    print(f"Transaction ID: {transaction_id}")
    print(f"Amount: ₹100.00 (10000 paise)")
    print(f"\nPayload:")
    print(json.dumps(payload, indent=2))
    
    # Step 3: Encode Payload
    print_section("Step 3: Encoding Payload")
    
    payload_json = json.dumps(payload)
    base64_payload = base64.b64encode(payload_json.encode()).decode()
    
    print(f"JSON Payload Length: {len(payload_json)} characters")
    print(f"Base64 Payload: {base64_payload[:50]}...")
    
    # Step 4: Generate Checksum
    print_section("Step 4: Generating Checksum")
    
    endpoint = "/pg/v1/pay"
    checksum_string = base64_payload + endpoint + SALT_KEY
    
    print(f"Checksum String Components:")
    print(f"  - Base64 Payload: {base64_payload[:30]}...")
    print(f"  - Endpoint: {endpoint}")
    print(f"  - Salt Key: {SALT_KEY[:10]}...{SALT_KEY[-10:]}")
    
    sha256_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
    checksum = f"{sha256_hash}###{SALT_INDEX}"
    
    print(f"\nSHA256 Hash: {sha256_hash}")
    print(f"Final Checksum: {checksum[:50]}...")
    
    # Step 5: Prepare Request
    print_section("Step 5: Preparing API Request")
    
    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": checksum,
        "accept": "application/json"
    }
    
    request_data = {
        "request": base64_payload
    }
    print(f"Request Headers:")
    print(json.dumps(headers, indent=2))
    print(f"\nRequest Data:")
    print(json.dumps(request_data, indent=2)[:500] + "...")

    # Step 6: Make API Call
    print_section("Step 6: Making API Call to PhonePe")
    try:
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            headers=headers,
            json=request_data,
            timeout=30
        )
        
        response_data = response.json()
        print("\nResponse:")
        print(json.dumps(response_data, indent=2))
        
        if response_data.get('success'):
            print("\n✅ Payment initiation successful!")
            payment_url = response_data.get('data', {}).get('paymentUrl')
            print(f"Payment URL: {payment_url}")
            print("\nOpen this URL in a browser to complete the payment.")
            return True
        else:
            print("\n❌ Payment initiation failed!")
            error_message = response_data.get('message', 'No error message provided')
            print(f"Error: {error_message}")
            return False
    except Exception as e:
        print(f"\n❌ Exception during API call: {str(e)}")
        return False
    
    



def test_payment_status(transaction_id):
    """Test payment status check"""
    print_section("TESTING PAYMENT STATUS CHECK")
    
    endpoint = f"/pg/v1/status/{MERCHANT_ID}/{transaction_id}"
    
    # Generate checksum for status check
    checksum_string = endpoint + SALT_KEY
    sha256_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
    checksum = f"{sha256_hash}###{SALT_INDEX}"
    
    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": checksum,
        "X-MERCHANT-ID": MERCHANT_ID,
        "accept": "application/json"
    }
    
    print(f"Checking status for: {transaction_id}")
    print(f"URL: {BASE_URL}{endpoint}")
    
    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            headers=headers,
            timeout=30
        )
        
        response_data = response.json()
        print("\nStatus Response:")
        print(json.dumps(response_data, indent=2))
        
        if response_data.get('success'):
            print("\n✅ Status check successful!")
            payment_state = response_data.get('data', {}).get('state')
            print(f"Payment State: {payment_state}")
        else:
            print("\n⚠️ Status check returned error")
            
    except Exception as e:
        print(f"❌ Error checking status: {str(e)}")


def main():
    """Main test function"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "PhonePe Integration Test Script" + " " * 16 + "║")
    print("╚" + "═" * 58 + "╝")
    
    print("\n⚠️  IMPORTANT NOTES:")
    print("  1. This script uses UAT (testing) credentials")
    print("  2. Update TEST_CALLBACK_URL with your webhook.site URL")
    print("  3. For production, change credentials and BASE_URL")
    print("  4. Amount is in paise (10000 = ₹100)")
    
    input("\nPress Enter to start the test...")
    
    # Test payment initiation
    success = test_phonepe_payment()
    
    if success:
        print_section("TEST COMPLETED SUCCESSFULLY")
        print("✅ Your PhonePe integration is working correctly!")
        print("\nNext Steps:")
        print("  1. Integrate the PhonePe service into your Django views")
        print("  2. Test with actual orders from your application")
        print("  3. Set up proper callback handling")
        print("  4. Test payment completion flow")
    else:
        print_section("TEST FAILED")
        print("❌ There are issues with your configuration")
        print("\nPlease review the error messages above and:")
        print("  1. Verify your credentials in settings.py")
        print("  2. Check the troubleshooting guide")
        print("  3. Ensure you're using the correct environment (UAT/Production)")
    
    # Ask if user wants to test status check
    print("\n" + "-" * 60)
    test_status = input("\nDo you want to test payment status check? (y/n): ").lower()
    
    if test_status == 'y':
        txn_id = input("Enter transaction ID to check (or press Enter to skip): ").strip()
        if txn_id:
            test_payment_status(txn_id)
    
    print("\n" + "=" * 60)
    print("Test script completed!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()