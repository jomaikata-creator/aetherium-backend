"""Subscription management — pause, resume, cancel, start with Stripe Checkout."""
import os
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Employee, EmployeeRole, Client, Project, ProjectStatus,
    Subscription, SubscriptionStatus,
)
from schemas import CheckoutRequest
from auth import get_current_employee, require_admin_or_lead, get_visible_employee_ids
from stripe_service import create_subscription_checkout_session
from email_service import send_subscription_email

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
APP_URL = os.getenv("APP_URL", "http://localhost:5175")


@router.get("")
def list_subscriptions(
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    if emp.role == EmployeeRole.admin:
        subs = db.query(Subscription).order_by(Subscription.start_date.desc()).all()
    else:
        visible_ids = get_visible_employee_ids(emp, db)
        subs = (
            db.query(Subscription)
            .join(Project)
            .join(Client)
            .filter(Client.assigned_to.in_(visible_ids))
            .order_by(Subscription.start_date.desc())
            .all()
        )

    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "project_name": s.project.project_name,
            "client_name": s.project.client.name,
            "monthly_fee": s.monthly_fee,
            "status": s.status.value,
            "start_date": s.start_date.isoformat() if s.start_date else None,
            "stripe_subscription_id": s.stripe_subscription_id,
            "checkout_url": s.checkout_url,
        }
        for s in subs
    ]


@router.post("/projects/{project_id}/start")
def start_subscription(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    """Create a Stripe Checkout Session for a recurring subscription, save it, and email the client."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    existing = db.query(Subscription).filter(Subscription.project_id == project_id).first()
    if existing:
        raise HTTPException(400, "Subscription already exists for this project")

    client = project.client

    # Create Stripe Checkout Session (mode="subscription")
    success_url = f"{APP_URL}/dashboard/projects?subscription_success={project_id}"
    cancel_url = f"{APP_URL}/dashboard/projects?subscription_canceled={project_id}"

    session = create_subscription_checkout_session(
        monthly_fee=project.monthly_fee,
        currency="eur",
        project_id=project.id,
        project_name=project.project_name,
        client_email=client.email,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    # Create local subscription record with checkout URL
    sub = Subscription(
        project_id=project.id,
        monthly_fee=project.monthly_fee,
        status=SubscriptionStatus.pending,
        start_date=datetime.utcnow(),
        stripe_checkout_session_id=session.id,
        checkout_url=session.url,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Inform admin about the pending state
    print(f"[subscription] Created pending subscription #{sub.id} for project #{project.id}")
    print(f"[subscription] Checkout expires: {time.ctime(session.expires_at)}")

    # Send the client a nice email with the checkout link
    send_subscription_email(
        to_email=client.email,
        client_name=client.name,
        project_name=project.project_name,
        monthly_fee=project.monthly_fee,
        checkout_url=session.url,
    )

    return {
        "id": sub.id,
        "project_id": sub.project_id,
        "monthly_fee": sub.monthly_fee,
        "status": sub.status.value,
        "start_date": sub.start_date.isoformat(),
        "checkout_url": session.url,
    }


@router.get("/projects/{project_id}/checkout-url")
def get_subscription_checkout_url(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    """Get the saved Stripe checkout URL for a project's subscription so it can be resent."""
    sub = db.query(Subscription).filter(Subscription.project_id == project_id).first()
    if not sub:
        raise HTTPException(404, "No subscription found for this project")
    if not sub.checkout_url:
        raise HTTPException(404, "No checkout URL saved")
    return {"checkout_url": sub.checkout_url}


@router.post("/projects/{project_id}/resend-email")
def resend_subscription_email(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    """Resend the subscription payment email to the client."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    sub = db.query(Subscription).filter(Subscription.project_id == project_id).first()
    if not sub:
        raise HTTPException(404, "No subscription found for this project")
    if sub.status != SubscriptionStatus.pending:
        raise HTTPException(400, f"Subscription is {sub.status.value}, not pending — no checkout needed")
    if not sub.checkout_url:
        raise HTTPException(404, "No checkout URL saved")

    client = project.client
    send_subscription_email(
        to_email=client.email,
        client_name=client.name,
        project_name=project.project_name,
        monthly_fee=sub.monthly_fee,
        checkout_url=sub.checkout_url,
    )

    return {"status": "resent", "checkout_url": sub.checkout_url}


@router.post("/projects/{project_id}/repopulate-checkout")
def repopulate_subscription_checkout(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    """Generate a fresh Stripe Checkout Session for a pending subscription (e.g. expired link)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    sub = db.query(Subscription).filter(Subscription.project_id == project_id).first()
    if not sub:
        raise HTTPException(404, "No subscription found for this project")
    if sub.status != SubscriptionStatus.pending:
        raise HTTPException(400, f"Subscription is {sub.status.value}, not pending")

    client = project.client

    success_url = f"{APP_URL}/dashboard/projects?subscription_success={project_id}"
    cancel_url = f"{APP_URL}/dashboard/projects?subscription_canceled={project_id}"

    session = create_subscription_checkout_session(
        monthly_fee=project.monthly_fee,
        currency="eur",
        project_id=project.id,
        project_name=project.project_name,
        client_email=client.email,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    sub.stripe_checkout_session_id = session.id
    sub.checkout_url = session.url
    db.commit()
    db.refresh(sub)

    send_subscription_email(
        to_email=client.email,
        client_name=client.name,
        project_name=project.project_name,
        monthly_fee=sub.monthly_fee,
        checkout_url=session.url,
    )

    return {
        "id": sub.id,
        "checkout_url": session.url,
        "expires_at": session.expires_at,
    }


@router.post("/{subscription_id}/pause")
def pause_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(404, "Subscription not found")
    if sub.status != SubscriptionStatus.active:
        raise HTTPException(400, "Only active subscriptions can be paused")

    # Pause Stripe subscription if exists
    if sub.stripe_subscription_id:
        try:
            import stripe
            stripe.Subscription.modify(sub.stripe_subscription_id, pause_collection={"behavior": "void"})
        except Exception as e:
            raise HTTPException(500, f"Stripe error: {e}")

    sub.status = SubscriptionStatus.paused
    db.commit()
    return {"status": "paused"}


@router.post("/{subscription_id}/resume")
def resume_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(404, "Subscription not found")
    if sub.status not in (SubscriptionStatus.paused, SubscriptionStatus.canceled):
        raise HTTPException(400, "Can only resume paused or canceled subscriptions")

    # Resume Stripe subscription
    if sub.stripe_subscription_id:
        try:
            import stripe
            stripe.Subscription.modify(sub.stripe_subscription_id, pause_collection="")
        except Exception as e:
            raise HTTPException(500, f"Stripe error: {e}")

    sub.status = SubscriptionStatus.active
    db.commit()
    return {"status": "active"}


@router.post("/{subscription_id}/cancel")
def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    # Cancel Stripe subscription
    if sub.stripe_subscription_id:
        try:
            import stripe
            stripe.Subscription.delete(sub.stripe_subscription_id)
        except Exception as e:
            raise HTTPException(500, f"Stripe error: {e}")

    sub.status = SubscriptionStatus.canceled
    db.commit()
    return {"status": "canceled"}