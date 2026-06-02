"""Stripe webhook handler — updates DB state on payment events."""
import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Project, ProjectStatus, Payment, PaymentStatus as PayStatus,
    Subscription, SubscriptionStatus, Invoice, InvoiceType, InvoiceStatus,
)
from stripe_service import construct_webhook_event
from invoice_service import generate_invoice_pdf

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


def _generate_invoice(db: Session, project: Project, amount: float, inv_type: str, stripe_ref: str | None = None) -> Invoice:
    client = project.client
    inv_num = _next_invoice_number(db)

    pdf_path = generate_invoice_pdf(
        invoice_number=inv_num,
        invoice_date=datetime.datetime.utcnow(),
        client_name=client.name,
        client_company=client.company_name,
        client_eik=client.eik,
        client_mol=client.mol,
        client_vat=client.vat_number,
        client_address=client.address,
        project_name=project.project_name,
        service_description="Web Design & Development",
        amount=amount,
        currency="EUR",
        invoice_type=inv_type,
    )

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
        stripe_reference_id=stripe_ref,
        pdf_path=pdf_path,
        status=InvoiceStatus.issued,
    )
    db.add(invoice)
    return invoice


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
                # Move project to maintenance
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
        _generate_invoice(db, project, amount, payment_type, data.get("invoice"))
        db.commit()

    # ── Subscription payment ──
    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        if subscription_id:
            sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
            if sub:
                amount = data.get("amount_paid", 0) / 100
                _generate_invoice(db, sub.project, amount, "monthly", data.get("id"))
                db.commit()

    return {"status": "received"}
