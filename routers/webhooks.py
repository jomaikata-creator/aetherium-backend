"""Stripe webhook handler — updates DB state on payment events."""
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Project, ProjectStatus, Payment, PaymentStatus as PayStatus,
    Subscription, SubscriptionStatus, Invoice, InvoiceType, InvoiceStatus,
)
from services.stripe_service import construct_webhook_event
from services.email_service import send_invoice_email

import stripe as stripe_lib

router = APIRouter(prefix="/api/webhooks/stripe", tags=["webhooks"])


def _next_invoice_number(db: Session) -> str:
    year = datetime.datetime.utcnow().year
    last = (
        db.query(Invoice)
        .filter(Invoice.invoice_number.like(f"{year}-%"))
        .order_by(Invoice.invoice_number.desc())
        .first()
    )
    seq = int(last.invoice_number.split("-")[1]) + 1 if last else 1
    return f"{year}-{seq:04d}"


def _generate_invoice(db: Session, project: Project, amount: float,
                      inv_type: str, stripe_invoice_id: str | None = None,
                      stripe_hosted_url: str | None = None) -> Invoice:
    client = project.client
    inv_num = _next_invoice_number(db)

    invoice = Invoice(
        invoice_number=inv_num,
        invoice_date=datetime.datetime.utcnow(),
        client_id=client.id,
        project_id=project.id,
        eik=client.eik,
        mol=client.mol,
        vat_number=client.vat_number,
        amount=amount,
        currency="EUR",
        type=InvoiceType(inv_type),
        stripe_reference_id=stripe_invoice_id,
        stripe_hosted_url=stripe_hosted_url,
        status=InvoiceStatus.issued,
    )
    db.add(invoice)
    return invoice


def _email_invoice(invoice: Invoice, project: Project, client, invoice_type: str,
                   service_description: str, stripe_hosted_url: str | None = None):
    """Send the invoice email to the client."""
    try:
        send_invoice_email(
            to_email=client.email,
            client_name=client.name,
            project_name=project.project_name,
            amount=invoice.amount,
            currency=invoice.currency,
            invoice_number=invoice.invoice_number,
            invoice_date=invoice.invoice_date.strftime("%d.%m.%Y"),
            invoice_type=invoice_type,
            service_description=service_description,
            stripe_hosted_url=stripe_hosted_url,
        )
        print(f"[webhook] Invoice email sent to {client.email} for {invoice.invoice_number}")
    except Exception as e:
        print(f"[webhook] Failed to send invoice email: {e}")


def _get_stripe_invoice_url(stripe_invoice_id: str) -> str | None:
    """Retrieve the Stripe hosted invoice URL."""
    try:
        inv = stripe_lib.Invoice.retrieve(stripe_invoice_id)
        return inv.hosted_invoice_url
    except Exception as e:
        print(f"[webhook] Failed to retrieve Stripe invoice {stripe_invoice_id}: {e}")
        return None


@router.post("")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload, sig_header)
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    event_type = event["type"]
    data = event["data"]["object"]

    # ── One-time payment completed ──
    if event_type == "checkout.session.completed":
        project_id = int(data.get("metadata", {}).get("project_id", 0))
        payment_type = data.get("metadata", {}).get("payment_type", "deposit")
        checkout_type = data.get("metadata", {}).get("type", "")

        # Handle subscription checkout
        if checkout_type == "subscription":
            sub = db.query(Subscription).filter(
                Subscription.stripe_checkout_session_id == data.get("id")
            ).first()
            if sub:
                sub.stripe_subscription_id = data.get("subscription")
                sub.status = SubscriptionStatus.active
                project = db.query(Project).filter(Project.id == project_id).first()
                if project and project.status == ProjectStatus.completed:
                    project.status = ProjectStatus.maintenance
                db.commit()
                print(f"[webhook] Subscription #{sub.id} paid — status active, project #{project_id} → maintenance")
            return {"status": "received"}

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"status": "ignored", "reason": "project not found"}

        payment = (
            db.query(Payment)
            .filter(Payment.stripe_payment_intent_id == data.get("payment_intent"))
            .first()
        )
        if payment:
            payment.status = PayStatus.paid
            payment.stripe_invoice_id = data.get("invoice")

        if payment_type == "deposit":
            project.status = ProjectStatus.building
        elif payment_type == "final":
            project.status = ProjectStatus.ready_to_deploy

        amount = data.get("amount_total", 0) / 100
        stripe_invoice_id = data.get("invoice")
        stripe_hosted_url = _get_stripe_invoice_url(stripe_invoice_id) if stripe_invoice_id else None

        invoice = _generate_invoice(db, project, amount, payment_type, stripe_invoice_id, stripe_hosted_url)
        db.commit()

        service = "Web Design & Development"
        _email_invoice(invoice, project, project.client, payment_type, service, stripe_hosted_url)

    # ── Subscription payment ──
    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        if subscription_id:
            sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
            if sub:
                amount = data.get("amount_paid", 0) / 100
                stripe_hosted_url = data.get("hosted_invoice_url")
                invoice = _generate_invoice(db, sub.project, amount, "monthly",
                                            data.get("id"), stripe_hosted_url)
                db.commit()

                _email_invoice(invoice, sub.project, sub.project.client, "monthly",
                              "Monthly Maintenance & Hosting", stripe_hosted_url)

    return {"status": "received"}
