"""Stripe integration — payment rail only. Business logic stays in routes."""
import os
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def create_checkout_session(
    amount: float,
    currency: str,
    project_id: int,
    client_email: str,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> stripe.checkout.Session:
    meta = {"project_id": str(project_id)}
    if metadata:
        meta.update(metadata)

    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": currency.lower(),
                "product_data": {"name": f"Project #{project_id} Payment"},
                "unit_amount": int(amount * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=client_email,
        metadata=meta,
    )


def create_subscription(
    monthly_fee: float,
    currency: str,
    project_id: int,
    client_email: str,
) -> stripe.Subscription:
    price = stripe.Price.create(
        unit_amount=int(monthly_fee * 100),
        currency=currency.lower(),
        recurring={"interval": "month"},
        product_data={"name": f"Project #{project_id} Monthly Maintenance"},
    )

    customers = stripe.Customer.list(email=client_email, limit=1)
    if customers.data:
        customer_id = customers.data[0].id
    else:
        customer = stripe.Customer.create(email=client_email)
        customer_id = customer.id

    return stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price.id}],
        metadata={"project_id": str(project_id)},
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    whsec = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return stripe.Webhook.construct_event(payload, sig_header, whsec)
