import os
from flask import request
import stripe

from bot import app

STRIPE_KEY = os.getenv('STRIPE_KEY')

def get_delivery_types():
    stripe.api_key = os.getenv('STRIPE_KEY')
    return stripe.Price.list()

# Gets checkout session url for user to navigate to
def create_checkout_session(priceId):
    stripe.api_key = os.getenv('STRIPE_KEY')
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': priceId,
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url='https://t.me/ninja_scheduler_bot',
            cancel_url='https://t.me/ninja_scheduler_bot',
        )
    except Exception as e:
        return str(e)

    return checkout_session.url

# Webhook that stripe calls upon success/failed payment by user
@app.route('/webhook', methods=['POST'])
def post_payment():
    stripe.api_key = os.getenv('STRIPE_KEY')
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('ENDPOINT_SECRET')
        )

    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Fulfill the purchase...
        payment_success(session)
    else:
        session = event['data']['object']
        payment_failure(session)

    return 'Success', 200


def payment_success(session):
    # TODO: Add logic for updating delivery type
    print(session)
    print("Payment success!")
    print("Updated delivery type.")

def payment_failure(session):
    # TODO: Add logic for failure
    print(session.failure_message)
    print("Failed to process payment, please try again.")
