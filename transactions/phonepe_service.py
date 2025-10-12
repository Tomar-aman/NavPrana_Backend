import hashlib
import base64
import json
import requests
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings


class PhonePePaymentService:
    """
    PhonePe Payment Gateway Integration Service
    Handles payment initiation, status checking, and refunds
    """
    
    # UAT (Testing) URLs
    BASE_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"
    # Production URLs (uncomment when going live)
    # BASE_URL = "https://api.phonepe.com/apis/hermes"
    
    def __init__(self):
        self.merchant_id = getattr(settings, 'PHONEPE_MERCHANT_ID', 'PHONEPEPGUAT')
        self.salt_key = getattr(settings, 'PHONEPE_SALT_KEY', 'c817ffaf-8471-48b5-a7e2-a27e5b7efbd3')
        self.salt_index = getattr(settings, 'PHONEPE_SALT_INDEX', '1')
        self.redirect_url = getattr(settings, 'PHONEPE_REDIRECT_URL', '')
        self.callback_url = getattr(settings, 'PHONEPE_CALLBACK_URL', '')
    
    def generate_checksum(self, payload: str) -> str:
        """
        Generate X-VERIFY checksum for PhonePe API
        Formula: SHA256(base64_payload + endpoint + salt_key) + ### + salt_index
        """
        checksum_string = payload + "/pg/v1/pay" + self.salt_key
        sha256_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
        return f"{sha256_hash}###1"
    
    def generate_transaction_id(self, order_id: int) -> str:
        """Generate unique transaction ID for PhonePe"""
        import time
        timestamp = int(time.time() * 1000)
        return f"TXN{order_id}_{timestamp}"
    
    def create_payment(self, order, amount: Decimal, user) -> Dict:
        """
        Create PhonePe payment (Standard Checkout - Web Flow)
        
        Args:
            order: Order instance
            amount: Payment amount in INR
            user: User instance
            
        Returns:
            dict: Payment response with redirect URL
        """
        transaction_id = self.generate_transaction_id(order.id)
        
        # Convert amount to paise (PhonePe uses paise)
        amount_in_paise = int(amount * 100)
        
        # Prepare payload
        payload = {
            "merchantId": self.merchant_id,
            "merchantTransactionId": transaction_id,
            "merchantUserId": f"USER_{user.id}",
            "amount": amount_in_paise,
            "redirectUrl": f"{self.redirect_url}?order_id={order.id}",
            "redirectMode": "POST",
            "callbackUrl": self.callback_url,
            "mobileNumber": getattr(user, 'phone', ''),
            "paymentInstrument": {
                "type": "PAY_PAGE"
            }
        }
        
        # Base64 encode the payload
        payload_json = json.dumps(payload)
        base64_payload = base64.b64encode(payload_json.encode()).decode()
        
        # Generate checksum
        checksum = self.generate_checksum(base64_payload)
        
        # Make API request
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum
        }
        
        request_data = {
            "request": base64_payload
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/pg/v1/pay",
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            if response_data.get('success'):
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'payment_url': response_data['data']['instrumentResponse']['redirectInfo']['url'],
                    'merchant_transaction_id': transaction_id,
                    'code': response_data.get('code'),
                    'message': response_data.get('message')
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', 'Payment initiation failed'),
                    'code': response_data.get('code')
                }
                
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'API request failed: {str(e)}'
            }
    
    def check_payment_status(self, transaction_id: str) -> Dict:
        """
        Check payment status from PhonePe
        
        Args:
            transaction_id: Merchant transaction ID
            
        Returns:
            dict: Payment status information
        """
        endpoint = f"/pg/v1/status/{self.merchant_id}/{transaction_id}"
        
        # Generate checksum for status check
        checksum_string = endpoint + self.salt_key
        sha256_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
        checksum = f"{sha256_hash}###{self.salt_index}"
        
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": self.merchant_id
        }
        
        try:
            response = requests.get(
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            if response_data.get('success'):
                payment_data = response_data['data']
                return {
                    'success': True,
                    'status': payment_data.get('state'),  # SUCCESS, FAILED, PENDING
                    'code': payment_data.get('responseCode'),
                    'amount': payment_data.get('amount', 0) / 100,  # Convert from paise
                    'transaction_id': payment_data.get('transactionId'),
                    'merchant_transaction_id': payment_data.get('merchantTransactionId'),
                    'payment_instrument': payment_data.get('paymentInstrument', {}),
                    'message': response_data.get('message')
                }
            else:
                return {
                    'success': False,
                    'status': 'FAILED',
                    'error': response_data.get('message', 'Status check failed')
                }
                
        except requests.RequestException as e:
            return {
                'success': False,
                'status': 'ERROR',
                'error': f'API request failed: {str(e)}'
            }
    
    def initiate_refund(self, transaction_id: str, amount: Decimal) -> Dict:
        """
        Initiate refund for a transaction
        
        Args:
            transaction_id: Original transaction ID
            amount: Refund amount in INR
            
        Returns:
            dict: Refund response
        """
        import time
        refund_transaction_id = f"REFUND_{transaction_id}_{int(time.time())}"
        amount_in_paise = int(amount * 100)
        
        payload = {
            "merchantId": self.merchant_id,
            "merchantTransactionId": refund_transaction_id,
            "originalTransactionId": transaction_id,
            "amount": amount_in_paise,
            "callbackUrl": self.callback_url
        }
        
        payload_json = json.dumps(payload)
        base64_payload = base64.b64encode(payload_json.encode()).decode()
        
        # Generate checksum
        checksum_string = base64_payload + "/pg/v1/refund" + self.salt_key
        sha256_hash = hashlib.sha256(checksum_string.encode()).hexdigest()
        checksum = f"{sha256_hash}###{self.salt_index}"
        
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum
        }
        
        request_data = {
            "request": base64_payload
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/pg/v1/refund",
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            response_data = response.json()
            
            return {
                'success': response_data.get('success', False),
                'refund_transaction_id': refund_transaction_id,
                'message': response_data.get('message'),
                'code': response_data.get('code')
            }
            
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f'Refund request failed: {str(e)}'
            }
    
    def validate_callback(self, base64_response: str, checksum: str) -> Optional[Dict]:
        """
        Validate callback/webhook from PhonePe
        
        Args:
            base64_response: Base64 encoded response from PhonePe
            checksum: X-VERIFY header value
            
        Returns:
            dict: Decoded response if valid, None otherwise
        """
        # Verify checksum
        expected_checksum_string = base64_response + self.salt_key
        expected_hash = hashlib.sha256(expected_checksum_string.encode()).hexdigest()
        expected_checksum = f"{expected_hash}###{self.salt_index}"
        
        if checksum != expected_checksum:
            return None
        
        # Decode response
        try:
            decoded_response = base64.b64decode(base64_response).decode()
            return json.loads(decoded_response)
        except Exception:
            return None