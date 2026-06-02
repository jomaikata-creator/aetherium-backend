"""Subscription management — pause, resume, cancel."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Employee, EmployeeRole, Client, Project, ProjectStatus,
    Subscription, SubscriptionStatus,
)
from auth import get_current_employee, require_admin_or_lead, get_visible_employee_ids

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


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
        }
        for s in subs
    ]


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


@router.post("/projects/{project_id}/start")
def start_subscription(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    """Create a subscription record for a completed project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    existing = db.query(Subscription).filter(Subscription.project_id == project_id).first()
    if existing:
        raise HTTPException(400, "Subscription already exists for this project")

    sub = Subscription(
        project_id=project.id,
        monthly_fee=project.monthly_fee,
        status=SubscriptionStatus.active,
        start_date=datetime.utcnow(),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return {
        "id": sub.id,
        "project_id": sub.project_id,
        "monthly_fee": sub.monthly_fee,
        "status": sub.status.value,
        "start_date": sub.start_date.isoformat(),
    }
