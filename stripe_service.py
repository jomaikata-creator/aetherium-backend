"""Stripe integration — payment rail only. Business logic stays in routes."""
import os
import time
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
    payment_method: str = "card",
) -> stripe.checkout.Session:
    """Create a Stripe Checkout Session for one-time payments (deposit or final).

    Expects payment_method="card" or "bank_transfer". Link expires in 24 hours.
    """
    meta = {"project_id": str(project_id)}
    if metadata:
        meta.update(metadata)

    if payment_method == "bank_transfer":
        # Need a Stripe Customer for bank transfers (virtual IBAN generation)
        customers = stripe.Customer.list(email=client_email, limit=1)
        if customers.data:
            customer_id = customers.data[0].id
        else:
            customer = stripe.Customer.create(email=client_email)
            customer_id = customer.id

        return stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["customer_balance"],
            payment_method_options={
                "customer_balance": {
                    "funding_type": "bank_transfer",
                    "bank_transfer": {
                        "type": "eu_bank_transfer",
                        "eu_bank_transfer": {
                            "country": "DE",  # EU bank transfer supported countries: DE, FR, IE, NL
                        },
                    },
                },
            },
            line_items=[{
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": f"Project #{project_id} Payment"},
                    "unit_amount": int(amount * 100),
                },
                "quantity": 1,
            }],
            mode="payment",
            expires_at=int(time.time() + 86400),  # 24 hours
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=meta,
        )

    # Default: card
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
        expires_at=int(time.time() + 86400),  # 24 hours
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=client_email,
        metadata=meta,
    )


def create_subscription_checkout_session(
    monthly_fee: float,
    currency: str,
    project_id: int,
    project_name: str,
    client_email: str,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """Create a Stripe Checkout Session for a recurring monthly subscription.

    Checkout link expires after 24 hours. Pending subscriptions can be
    regenerated with a fresh session via the repopulate endpoint.
    """
    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": currency.lower(),
                "product_data": {
                    "name": f"{project_name} — Monthly Maintenance",
                    "description": f"Project #{project_id} ongoing maintenance & hosting",
                },
                "unit_amount": int(monthly_fee * 100),
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        expires_at=int(time.time() + 86400),  # 24 hours (Stripe max)
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=client_email,
        metadata={"project_id": str(project_id), "type": "subscription"},
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    whsec = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return stripe.Webhook.construct_event(payload, sig_header, whsec)
