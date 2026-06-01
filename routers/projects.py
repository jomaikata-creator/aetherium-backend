"""Project management + Stripe payment flows."""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Employee, EmployeeRole, Client, Project, ProjectStatus,
    Payment, PaymentMethod, PaymentStatus as PayStatus,
)
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse, CheckoutRequest
from auth import get_current_employee, require_admin_or_lead
from stripe_service import create_checkout_session

MONTHLY_FEE = float(os.getenv("DEFAULT_MONTHLY_FEE", "300.0"))

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _can_access_project(emp: Employee, project: Project, db: Session) -> bool:
    if emp.role == EmployeeRole.admin:
        return True
    if project.client.assigned_to == emp.id:
        return True
    return False


def _can_edit_project(emp: Employee, project: Project) -> bool:
    if emp.role == EmployeeRole.admin:
        return True
    if emp.role == EmployeeRole.lead and project.client.assigned_to == emp.id:
        return True
    return False


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")

    # Lead can only create for own clients
    if emp.role == EmployeeRole.lead and client.assigned_to != emp.id:
        raise HTTPException(403, "Not your client")

    if data.deposit_amount > data.full_price:
        raise HTTPException(400, "deposit_amount cannot exceed full_price")

    remaining = round(data.full_price - data.deposit_amount, 2)

    project = Project(
        client_id=data.client_id,
        project_name=data.project_name,
        full_price=data.full_price,
        deposit_amount=data.deposit_amount,
        remaining_amount=remaining,
        monthly_fee=MONTHLY_FEE,
        website_type=data.website_type,
        features=data.features,
        pages_count=data.pages_count,
        status=ProjectStatus.quoted,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    if emp.role == EmployeeRole.admin:
        return db.query(Project).order_by(Project.created_at.desc()).all()
    # Lead + creative: only projects of their clients
    return (
        db.query(Project)
        .join(Client)
        .filter(Client.assigned_to == emp.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not _can_access_project(emp, project, db):
        raise HTTPException(403, "Not your project")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not _can_edit_project(emp, project):
        raise HTTPException(403, "Only admin or assigned lead can edit")

    if data.full_price is not None or data.deposit_amount is not None:
        fp = data.full_price if data.full_price is not None else project.full_price
        dp = data.deposit_amount if data.deposit_amount is not None else project.deposit_amount
        if dp > fp:
            raise HTTPException(400, "deposit_amount cannot exceed full_price")
        project.full_price = fp
        project.deposit_amount = dp
        project.remaining_amount = round(fp - dp, 2)

    if data.project_name is not None:
        project.project_name = data.project_name
    if data.website_type is not None:
        project.website_type = data.website_type
    if data.features is not None:
        project.features = data.features
    if data.pages_count is not None:
        project.pages_count = data.pages_count
    if data.status is not None:
        try:
            project.status = ProjectStatus(data.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {data.status}")

    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/pay-deposit")
def pay_deposit(
    project_id: int,
    req: CheckoutRequest,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not _can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")
    if project.deposit_amount <= 0:
        raise HTTPException(400, "No deposit required")

    session = create_checkout_session(
        amount=project.deposit_amount,
        currency="eur",
        project_id=project.id,
        client_email=project.client.email,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"payment_type": "deposit"},
    )

    payment = Payment(
        project_id=project.id,
        stripe_payment_intent_id=session.payment_intent,
        amount=project.deposit_amount,
        method=PaymentMethod.stripe_card,
        status=PayStatus.pending,
    )
    db.add(payment)
    project.status = ProjectStatus.deposit_pending
    db.commit()

    return {"checkout_url": session.url}


@router.post("/{project_id}/pay-final")
def pay_final(
    project_id: int,
    req: CheckoutRequest,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not _can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")
    if project.remaining_amount <= 0:
        raise HTTPException(400, "No remaining amount to pay")

    session = create_checkout_session(
        amount=project.remaining_amount,
        currency="eur",
        project_id=project.id,
        client_email=project.client.email,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"payment_type": "final"},
    )

    payment = Payment(
        project_id=project.id,
        stripe_payment_intent_id=session.payment_intent,
        amount=project.remaining_amount,
        method=PaymentMethod.stripe_card,
        status=PayStatus.pending,
    )
    db.add(payment)
    project.status = ProjectStatus.awaiting_final
    db.commit()

    return {"checkout_url": session.url}


@router.post("/{project_id}/mark-bank-paid")
def mark_bank_paid(
    project_id: int,
    amount: float = 0,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not _can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")

    payment = Payment(
        project_id=project.id,
        amount=amount or project.deposit_amount,
        method=PaymentMethod.bank_transfer,
        status=PayStatus.paid,
    )
    db.add(payment)

    if project.status == ProjectStatus.deposit_pending:
        project.status = ProjectStatus.building
    elif project.status == ProjectStatus.awaiting_final:
        project.status = ProjectStatus.launched

    db.commit()
    return {"status": "paid", "project_status": project.status.value}
