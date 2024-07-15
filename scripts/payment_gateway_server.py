import os
import json
import stripe
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from flask_mail import Mail, Message
from flask_oauthlib.provider import OAuth2Provider
import logging

#pip install flask stripe requests apscheduler flask-cors flask-mail flask-oauthlib

# Initialize Flask app
app = Flask(__name__)
CORS(app)
oauth = OAuth2Provider(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Keycloak configuration
KEYCLOAK_URL = os.getenv('KEYCLOAK_URL')
REALM = os.getenv('KEYCLOAK_REALM')

# Pricing IDs
PRICE_IDS = {
    'basic': 'price_1ExampleBasic',  # Replace with actual price IDs
    'advanced': 'price_1ExampleAdvanced',
    'pro': 'price_1ExamplePro'
}

# Subscription options
SUBSCRIPTION_OPTIONS = [
    {
        'name': 'Basic',
        'price_monthly': 1,
        'price_yearly': 12,
        'ai_tokens': 10,
        'storage': 50
    },
    {
        'name': 'Advanced',
        'price_monthly': 2,
        'price_yearly': 24,
        'ai_tokens': 20,
        'storage': 100
    },
    {
        'name': 'Pro',
        'price_monthly': 3,
        'price_yearly': 36,
        'ai_tokens': 30,
        'storage': 150
    }
]

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'your-email@example.com'
app.config['MAIL_PASSWORD'] = 'your-email-password'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

def get_user_profile(access_token):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def update_user_claims(user_id, claims):
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{user_id}"
    headers = {
        "Authorization": f"Bearer {os.getenv('KEYCLOAK_ADMIN_TOKEN')}",
        "Content-Type": "application/json"
    }
    response = requests.put(url, headers=headers, data=json.dumps(claims))
    return response.status_code == 204

def remove_expired_groups():
    url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users"
    headers = {
        "Authorization": f"Bearer {os.getenv('KEYCLOAK_ADMIN_TOKEN')}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json()
        for user in users:
            user_id = user['id']
            user_detail_url = f"{KEYCLOAK_URL}/admin/realms/{REALM}/users/{user_id}"
            user_response = requests.get(user_detail_url, headers=headers)
            if user_response.status_code == 200:
                user_data = user_response.json()
                expiration_date = user_data.get('attributes', {}).get('expiration_date')
                if expiration_date:
                    expiration_date = datetime.fromisoformat(expiration_date[0])
                    if datetime.now() > expiration_date:
                        claims = {
                            'tier': '',
                            'ai_tokens': 0,
                            'storage': 0,
                            'expiration_date': ''
                        }
                        update_user_claims(user_id, claims)
                        logger.info(f"Removed expired subscription for user {user_id}.")
    else:
        logger.error(f"Error fetching users: {response.status_code}")

def send_email(subject, recipient, body):
    msg = Message(subject, sender='your-email@example.com', recipients=[recipient])
    msg.body = body
    mail.send(msg)
    logger.info(f"Email sent to {recipient} with subject: {subject}")

# Schedule the removal of expired groups
scheduler = BackgroundScheduler()
scheduler.add_job(remove_expired_groups, 'interval', hours=24)
scheduler.start()

@app.route('/subscription-options', methods=['GET'])
def subscription_options():
    return jsonify(SUBSCRIPTION_OPTIONS)

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    data = request.json
    if not data:
        logger.error("Invalid data received for creating checkout session.")
        return jsonify({"error": "Invalid data"}), 400

    access_token = data.get('access_token')
    tier = data.get('tier')
    ai_tokens = data.get('ai_tokens')
    storage = data.get('storage')

    if not access_token or not tier or ai_tokens is None or storage is None:
        logger.error("Missing required fields for creating checkout session.")
        return jsonify({"error": "All fields are required"}), 400

    user_profile = get_user_profile(access_token)
    if not user_profile:
        logger.error("Invalid access token provided.")
        return jsonify({"error": "Invalid access token"}), 401

    user_id = user_profile['sub']

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': PRICE_IDS[tier],
                'quantity': 1,
            }],
            mode='subscription',
            metadata={
                'user_id': user_id,
                'ai_tokens': ai_tokens,
                'storage': storage
            },
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
        )
        logger.info(f"Checkout session created successfully for user {user_id}.")
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

    return jsonify({'id': session.id})

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session['metadata']

        user_id = metadata['user_id']
        ai_tokens = int(metadata['ai_tokens'])
        storage = int(metadata['storage'])

        expiration_date = (datetime.now() + timedelta(days=365)).isoformat()

        claims = {
            'tier': session['subscription'],
            'ai_tokens': ai_tokens,
            'storage': storage,
            'expiration_date': expiration_date
        }

        if update_user_claims(user_id, claims):
            send_email("Subscription Successful", user_profile['email'], "Thank you for subscribing!")
            logger.info(f"User claims updated successfully for user {user_id}.")
        else:
            logger.error("Failed to update user claims.")
            return 'Failed to update user claims', 500

    return 'Success', 200

if __name__ == '__main__':
    app.run(port=4242, ssl_context=('cert.pem', 'key.pem'))
