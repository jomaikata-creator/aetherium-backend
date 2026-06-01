"""Invoice listing and PDF download — scoped by team visibility."""
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models import Invoice, Employee, Client, EmployeeRole
from schemas import InvoiceResponse
from auth import get_current_employee, get_visible_employee_ids

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    if emp.role == EmployeeRole.admin:
        return db.query(Invoice).order_by(Invoice.invoice_date.desc()).all()
    visible_ids = get_visible_employee_ids(emp, db)
    return (
        db.query(Invoice)
        .join(Client, Invoice.client_id == Client.id)
        .filter(Client.assigned_to.in_(visible_ids))
        .order_by(Invoice.invoice_date.desc())
        .all()
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv or not inv.pdf_path or not os.path.exists(inv.pdf_path):
        raise HTTPException(404, "PDF not found")
    return FileResponse(
        inv.pdf_path,
        media_type="application/pdf",
        filename=f"invoice-{inv.invoice_number}.pdf",
    )
