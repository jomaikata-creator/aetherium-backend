"""Project management + Stripe payment flows — scoped by role + team."""
import os
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Employee, EmployeeRole, Client, Project, ProjectStatus,
    Payment, PaymentMethod, PaymentStatus as PayStatus,
)
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse, CheckoutRequest
from auth import (
    get_current_employee, require_admin_or_lead,
    get_visible_employee_ids, can_edit_project,
)
from stripe_service import create_checkout_session
from email_service import send_payment_email

MONTHLY_FEE = float(os.getenv("DEFAULT_MONTHLY_FEE", "300.0"))

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")

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
        creative_percent=data.creative_percent,
        lead_percent=data.lead_percent,
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
    visible_ids = get_visible_employee_ids(emp, db)
    return (
        db.query(Project)
        .join(Client)
        .filter(Client.assigned_to.in_(visible_ids))
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

    if emp.role != EmployeeRole.admin:
        visible_ids = get_visible_employee_ids(emp, db)
        if project.client.assigned_to not in visible_ids:
            raise HTTPException(403, "Not in your team")
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
    if not can_edit_project(emp, project):
        raise HTTPException(403, "Admin can edit any, lead can only edit own projects")

    if data.full_price is not None or data.deposit_amount is not None:
        fp = data.full_price if data.full_price is not None else project.full_price
        dp = data.deposit_amount if data.deposit_amount is not None else project.deposit_amount
        if dp > fp:
            raise HTTPException(400, "deposit_amount cannot exceed full_price")
        project.full_price = fp
        project.deposit_amount = dp
        project.remaining_amount = round(fp - dp, 2)

    for field in ("project_name", "website_type", "features", "pages_count"):
        if getattr(data, field, None) is not None:
            setattr(project, field, getattr(data, field))

    if data.creative_percent is not None:
        project.creative_percent = data.creative_percent
    if data.lead_percent is not None:
        project.lead_percent = data.lead_percent

    if data.status is not None:
        try:
            project.status = ProjectStatus(data.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {data.status}")

    db.commit()
    db.refresh(project)
    return project


def _create_one_time_payment(
    project: Project,
    amount: float,
    payment_type: str,
    payment_method: str,
    success_url: str,
    cancel_url: str,
    db: Session,
) -> Payment:
    """Shared helper: create Stripe checkout + Payment record for deposit/final."""
    method = PaymentMethod.stripe_card if payment_method == "card" else PaymentMethod.bank_transfer

    session = create_checkout_session(
        amount=amount,
        currency="eur",
        project_id=project.id,
        client_email=project.client.email,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"payment_type": payment_type},
        payment_method=payment_method,
    )

    payment = Payment(
        project_id=project.id,
        stripe_payment_intent_id=session.payment_intent,
        stripe_checkout_session_id=session.id,
        amount=amount,
        method=method,
        status=PayStatus.pending,
        checkout_url=session.url,
    )
    db.add(payment)

    # Send the client an email with the checkout link
    client = project.client
    payment_label = "deposit" if payment_type == "deposit" else "final"
    send_payment_email(
        to_email=client.email,
        client_name=client.name,
        project_name=project.project_name,
        amount=amount,
        payment_type=payment_label,
        checkout_url=session.url,
    )
    print(f"[payment] Email sent to {client.email} for {payment_label} payment on project #{project.id}")

    return payment


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
    if not can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")
    if project.deposit_amount <= 0:
        raise HTTPException(400, "No deposit required")

    _create_one_time_payment(
        project=project,
        amount=project.deposit_amount,
        payment_type="deposit",
        payment_method=req.payment_method,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        db=db,
    )
    project.status = ProjectStatus.deposit_pending
    db.commit()
    return {"checkout_url": project.payments[-1].checkout_url}


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
    if not can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")
    if project.remaining_amount <= 0:
        raise HTTPException(400, "No remaining amount to pay")

    _create_one_time_payment(
        project=project,
        amount=project.remaining_amount,
        payment_type="final",
        payment_method=req.payment_method,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        db=db,
    )
    project.status = ProjectStatus.awaiting_final
    db.commit()
    return {"checkout_url": project.payments[-1].checkout_url}


@router.get("/{project_id}/checkout-url")
def get_checkout_url(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    """Get the latest pending Stripe checkout URL for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    payment = (
        db.query(Payment)
        .filter(Payment.project_id == project_id, Payment.status == PayStatus.pending, Payment.checkout_url.isnot(None))
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        raise HTTPException(404, "No pending checkout URL found")

    return {"checkout_url": payment.checkout_url}


@router.post("/{project_id}/regenerate-checkout")
def regenerate_payment_checkout(
    project_id: int,
    req: CheckoutRequest,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    """Regenerate a fresh Stripe Checkout for a pending payment (expired link)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    if not can_edit_project(emp, project):
        raise HTTPException(403, "Not authorized")

    # Find the most recent pending payment for this project
    payment = (
        db.query(Payment)
        .filter(
            Payment.project_id == project_id,
            Payment.status == PayStatus.pending,
            Payment.checkout_url.isnot(None),
        )
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment:
        raise HTTPException(404, "No pending payment to regenerate")

    # Determine amount from payment record
    session = create_checkout_session(
        amount=payment.amount,
        currency="eur",
        project_id=project.id,
        client_email=project.client.email,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"payment_type": "deposit" if payment.amount == project.deposit_amount else "final"},
        payment_method=req.payment_method,
    )

    payment.stripe_checkout_session_id = session.id
    payment.checkout_url = session.url
    payment.stripe_payment_intent_id = session.payment_intent
    db.commit()

    # Resend the payment email with the fresh checkout link
    client = project.client
    is_deposit = payment.amount == project.deposit_amount
    payment_label = "deposit" if is_deposit else "final"
    send_payment_email(
        to_email=client.email,
        client_name=client.name,
        project_name=project.project_name,
        amount=payment.amount,
        payment_type=payment_label,
        checkout_url=session.url,
    )
    print(f"[payment] Regenerated checkout + resent email to {client.email} for project #{project.id}")

    return {"checkout_url": session.url}


def _next_invoice_number(db: Session) -> str:
    """Generate next sequential invoice number: YYYY-NNNN."""
    from models import Invoice as Inv
    year = datetime.datetime.utcnow().year
    last = (
        db.query(Inv)
        .filter(Inv.invoice_number.like(f"{year}-%"))
        .order_by(Inv.invoice_number.desc())
        .first()
    )
    seq = int(last.invoice_number.split("-")[1]) + 1 if last else 1
    return f"{year}-{seq:04d}"


@router.post("/{project_id}/check-payment")
def check_payment_status(
    project_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    """Check Stripe for the latest payment status and update the DB."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found")

    payment = (
        db.query(Payment)
        .filter(
            Payment.project_id == project_id,
            Payment.stripe_checkout_session_id.isnot(None),
            Payment.status == PayStatus.pending,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )
    if not payment or not payment.stripe_checkout_session_id:
        return {"status": "no_pending_payment"}

    # Query Stripe for the checkout session status
    try:
        import stripe as stripe_lib
        session = stripe_lib.checkout.Session.retrieve(payment.stripe_checkout_session_id)

        if session.payment_status == "paid" and payment.status != PayStatus.paid:
            payment.status = PayStatus.paid
            # Update project status based on payment type
            if project.status == ProjectStatus.deposit_pending:
                project.status = ProjectStatus.building
            elif project.status == ProjectStatus.awaiting_final:
                project.status = ProjectStatus.ready_to_deploy
            # Generate invoice
            from invoice_service import generate_invoice_pdf
            from models import Invoice, InvoiceType, InvoiceStatus
            inv_num = _next_invoice_number(db)
            client = project.client
            pdf_path = generate_invoice_pdf(
                invoice_number=inv_num,
                invoice_date=datetime.datetime.utcnow(),
                client_name=client.name, client_company=client.company_name,
                client_eik=client.eik, client_mol=client.mol,
                client_vat=client.vat_number, client_address=client.address,
                project_name=project.project_name,
                service_description="Web Design & Development",
                amount=payment.amount, currency="EUR",
                invoice_type="deposit" if project.status == ProjectStatus.deposit_pending else "final",
            )
            invoice = Invoice(
                invoice_number=inv_num, invoice_date=datetime.datetime.utcnow(),
                client_id=client.id, project_id=project.id,
                eik=client.eik, mol=client.mol, vat_number=client.vat_number,
                amount=payment.amount, currency="EUR",
                type=InvoiceType("deposit" if payment.amount == project.deposit_amount else "final"),
                stripe_reference_id=session.id, pdf_path=pdf_path,
                status=InvoiceStatus.issued,
            )
            db.add(invoice)
            db.commit()
            db.refresh(project)
            return {"status": "paid", "project_status": project.status.value}

        return {"status": session.payment_status}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


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
    if not can_edit_project(emp, project):
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
        project.status = ProjectStatus.ready_to_deploy

    db.commit()
    return {"status": "paid", "project_status": project.status.value}
