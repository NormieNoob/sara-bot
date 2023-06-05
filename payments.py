from dotenv import load_dotenv
import os
import json
from base64 import b64encode
import requests
import hashlib

if os.path.exists('.env'):
    load_dotenv()
    merchant_id = os.environ.get('MERCHANT_ID')
    salt_key = os.environ.get('SALT_KEY')
    salt_index = os.environ.get('SALT_INDEX')
else:
    merchant_id = os.getenv('MERCHANT_ID')
    salt_key = os.getenv('SALT_KEY')
    salt_index = os.getenv('SALT_INDEX')


def create_payment_request(amount, transaction_id, user_id, vpa):
    payload = {
        "merchantId": merchant_id,
        "merchantTransactionId": transaction_id,
        "merchantUserId": user_id,
        "amount": amount,
        "callbackUrl": "https://webhook.site/callback-url",
        "paymentInstrument": {
            "type": "UPI_COLLECT",
            "vpa": vpa
        }
    }
    return b64encode(json.dumps(payload).encode()).decode()


def send_payment_request(encoded_payload):
    url = "https://api-preprod.phonepe.com/apis/merchant-simulator/pg/v1/pay"

    concat_string = f"{encoded_payload}/pg/v1/pay{salt_key}"
    sha256_hash = hashlib.sha256(concat_string.encode()).hexdigest()
    x_verify = f"{sha256_hash}###{salt_index}"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "X-VERIFY": x_verify
    }
    data = {
        "request": encoded_payload
    }
    response = requests.post(url=url, headers=headers, json=data)
    return response.json()


def handle_api_response(response):
    if response['success']:
        return response['data']['merchantTransactionId']
    else:
        return None






