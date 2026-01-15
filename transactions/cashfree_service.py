"""
Cashfree Payment Gateway Integration Service

This module handles:
- Payment order creation
- Payment verification
- Webhook signature verification
- Transaction status checks
"""

import hashlib
import hmac
import base64
import json
import logging
from typing import Dict, Optional
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
import requests

logger = logging.getLogger(__name__)


class CashfreePaymentService:
    """
    Service class for Cashfree payment integration
    
    Environment Variables Required in settings.py:
    - CASHFREE_APP_ID: Your Cashfree App ID
    - CASHFREE_SECRET_KEY: Your Cashfree Secret Key
    - CASHFREE_API_VERSION: API version (default: "2023-08-01")
    - CASHFREE_ENVIRONMENT: "TEST" or "PROD"
    """
    
    # API URLs
    PROD_URL = "https://api.cashfree.com/pg"
    TEST_URL = "https://sandbox.cashfree.com/pg"
    
    def __init__(self):
        """Initialize Cashfree service with credentials from settings"""
        self.app_id = getattr(settings, 'CASHFREE_APP_ID', '')
        self.secret_key = getattr(settings, 'CASHFREE_SECRET_KEY', '')
        self.api_version = getattr(settings, 'CASHFREE_API_VERSION', '2023-08-01')
        self.environment = getattr(settings, 'CASHFREE_ENVIRONMENT', 'TEST')
        
        # Set base URL based on environment
        self.base_url = self.PROD_URL if self.environment == 'PROD' else self.TEST_URL
        
        if not self.app_id or not self.secret_key:
            raise ValueError("Cashfree credentials not configured in settings")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            'accept': 'application/json',
            'content-type': 'application/json',
            'x-api-version': self.api_version,
            'x-client-id': self.app_id,
            'x-client-secret': self.secret_key
        }
    
    def create_order(
        self,
        order_id: str,
        amount: Decimal,
        customer_details: Dict[str, str],
        order_meta: Optional[Dict] = None,
        order_note: Optional[str] = None
    ) -> Dict:
        """
        Create a Cashfree order and get payment session
        
        Args:
            order_id: Your internal order ID (unique)
            amount: Order amount in INR
            customer_details: Dict with customer_id, customer_phone, customer_email, customer_name
            order_meta: Optional metadata for the order
            order_note: Optional note for the order
            
        Returns:
            Dict containing payment_session_id and order details
        """
        try:
            # Prepare order payload
            payload = {
                "order_id": str(order_id),
                "order_amount": float(amount),
                "order_currency": "INR",
                "customer_details": {
                    "customer_id": customer_details.get('customer_id'),
                    "customer_phone": customer_details.get('customer_phone'),
                    "customer_email": customer_details.get('customer_email'),
                    "customer_name": customer_details.get('customer_name', '')
                },
                "order_meta": order_meta or {},
                "order_note": order_note or ""
            }
            
            # API endpoint
            url = f"{self.base_url}/orders"
            
            # Make API request
            # logger.info(f"Creating Cashfree order: {order_id}")
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # print(result,"cashfree create order response")
            # logger.info(f"Cashfree order created successfully: {order_id}")
            
            return {
                'success': True,
                'payment_session_id': result.get('payment_session_id'),
                'order_id': result.get('order_id'),
                'order_status': result.get('order_status'),
                # 'order_token': result.get('order_token'),  # For SDK integration
                'cf_order_id': result.get('cf_order_id'),  # Cashfree's internal order ID
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Cashfree order creation failed: {str(e)}"
            logger.error(error_msg)
            
            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Cashfree API error details: {error_detail}")
                except:
                    error_detail = e.response.text
            
            return {
                'success': False,
                'error': error_msg,
                'error_detail': error_detail
            }
    
    def verify_payment(self, order_id: str) -> Dict:
        """
        Verify payment status from Cashfree
        
        Args:
            order_id: Your order ID
            
        Returns:
            Dict with payment verification details
        """
        try:
            url = f"{self.base_url}/orders/{order_id}"
            
            logger.info(f"Verifying payment for order: {order_id}")
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            order_status = result.get('order_status')
            payment_data = result.get('payment_info', {})
            
            return {
                'success': True,
                'order_id': result.get('order_id'),
                'cf_order_id': result.get('cf_order_id'),
                'order_status': order_status,
                'order_amount': result.get('order_amount'),
                'payment_status': order_status in ['PAID', 'ACTIVE'],
                'payment_method': payment_data.get('payment_method'),
                'payment_time': result.get('payment_completion_time'),
                'payment_group': payment_data.get('payment_group'),
                'bank_reference': payment_data.get('bank_reference'),
                'auth_id': payment_data.get('auth_id'),
                'raw_response': result
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Payment verification failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
    
    # def verify_webhook_signature(
    #     self,
    #     webhook_body: str,
    #     signature: str,
    #     timestamp: str
    # ) -> bool:
    #     """
    #     Verify Cashfree webhook signature
        
    #     Args:
    #         webhook_body: Raw webhook body as string
    #         signature: Signature from x-webhook-signature header
    #         timestamp: Timestamp from x-webhook-timestamp header
            
    #     Returns:
    #         bool: True if signature is valid
    #     """
    #     try:
    #         # Create signature string: timestamp + raw_body
    #         signature_string = f"{timestamp}{webhook_body}"
            
    #         # Generate expected signature using HMAC SHA256
    #         expected_signature = hmac.new(
    #             self.secret_key.encode('utf-8'),
    #             signature_string.encode('utf-8'),
    #             hashlib.sha256
    #         ).hexdigest()
            
    #         # Compare signatures
    #         is_valid = hmac.compare_digest(expected_signature, signature)
            
    #         if is_valid:
    #             logger.info("Webhook signature verified successfully")
    #         else:
    #             logger.warning("Webhook signature verification failed")
            
    #         return is_valid
            
    #     except Exception as e:
    #         logger.error(f"Webhook signature verification error: {str(e)}")
    #         return False

    def verify_webhook_signature(self, raw_body: str, signature: str, timestamp: str) -> bool:
        """
        Verify Cashfree PG v3 webhook signature
        """

        try:
            # IMPORTANT: timestamp + raw body (NO spaces, NO json.dumps)
            message = f"{timestamp}{raw_body}".encode("utf-8")

            secret = self.secret_key.encode("utf-8")

            # Generate HMAC SHA256
            digest = hmac.new(
                secret,
                message,
                hashlib.sha256
            ).digest()

            # Cashfree uses BASE64, not HEX
            expected_signature = base64.b64encode(digest).decode()

            # Secure comparison
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def refund_payment(
        self,
        order_id: str,
        refund_amount: Decimal,
        refund_id: str,
        refund_note: Optional[str] = None
    ) -> Dict:
        """
        Initiate refund for a payment
        
        Args:
            order_id: Original order ID
            refund_amount: Amount to refund
            refund_id: Unique refund ID
            refund_note: Optional refund note
            
        Returns:
            Dict with refund details
        """
        try:
            payload = {
                "refund_amount": float(refund_amount),
                "refund_id": refund_id,
                "refund_note": refund_note or ""
            }
            
            url = f"{self.base_url}/orders/{order_id}/refunds"
            
            logger.info(f"Initiating refund for order: {order_id}")
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'cf_refund_id': result.get('cf_refund_id'),
                'refund_status': result.get('refund_status'),
                'refund_arn': result.get('refund_arn'),
                'refund_id': result.get('refund_id')
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Refund initiation failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_payment_url(self, payment_session_id: str) -> str:
        """
        Get Hosted Checkout URL for payment (Cashfree Checkout v3)
        
        Cashfree recommends using the JS Checkout with the
        `paymentSessionId`. For a direct redirect (Hosted Checkout),
        use the web checkout URL pattern below.
        
        Args:
            payment_session_id: Payment session ID from create_order
            
        Returns:
            str: Cashfree hosted checkout URL
        """
        base = "https://payments.cashfree.com" if self.environment == 'PROD' else "https://sandbox.cashfree.com"
        # Hosted Checkout path for PG
        return f"{base}/pg/web/checkout?payment_session_id={payment_session_id}"
    
    def get_settlements(self, start_date: str, end_date: str) -> Dict:
        """
        Get settlement details for a date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dict with settlement details
        """
        try:
            url = f"{self.base_url}/settlements"
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            return {
                'success': True,
                'settlements': response.json()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e)
            }
