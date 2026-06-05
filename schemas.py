"""Pydantic v2 schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════
#  Employee
# ═══════════════════════════════════════════

class EmployeeCreate(BaseModel):
    email: str
    password: Optional[str] = None  # optional — invite email handles password setup
    full_name: str
    role: str = "creative"
    manager_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    manager_id: Optional[int] = None


class EmployeeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    manager_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Client
# ═══════════════════════════════════════════

class ClientCreate(BaseModel):
    assigned_to: Optional[int] = None  # employee id
    name: str
    email: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    eik: Optional[str] = None
    mol: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None


class ClientUpdate(BaseModel):
    assigned_to: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    eik: Optional[str] = None
    mol: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None


class ClientResponse(BaseModel):
    id: int
    assigned_to: Optional[int] = None
    name: str
    email: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    eik: Optional[str] = None
    mol: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Project
# ═══════════════════════════════════════════

class ProjectCreate(BaseModel):
    client_id: int
    project_name: str
    full_price: float = Field(gt=0)
    deposit_amount: float = Field(ge=0)
    creative_percent: float = Field(default=0, ge=0, le=100)
    lead_percent: float = Field(default=0, ge=0, le=100)
    website_type: Optional[str] = None
    features: Optional[str] = None
    pages_count: Optional[int] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    full_price: Optional[float] = None
    deposit_amount: Optional[float] = None
    creative_percent: Optional[float] = Field(default=None, ge=0, le=100)
    lead_percent: Optional[float] = Field(default=None, ge=0, le=100)
    website_type: Optional[str] = None
    features: Optional[str] = None
    pages_count: Optional[int] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    client_id: int
    project_name: str
    full_price: float
    deposit_amount: float
    remaining_amount: float
    monthly_fee: float
    creative_percent: float
    lead_percent: float
    website_type: Optional[str] = None
    features: Optional[str] = None
    pages_count: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Consultation
# ═══════════════════════════════════════════

class ConsultationCreate(BaseModel):
    name: str
    email: str
    message: Optional[str] = ""


class ConsultationResponse(BaseModel):
    id: int
    name: str
    email: str
    message: Optional[str] = None
    created_at: datetime
    read: bool

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Payment
# ═══════════════════════════════════════════

class PaymentResponse(BaseModel):
    id: int
    project_id: int
    stripe_payment_intent_id: Optional[str] = None
    amount: float
    method: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Invoice
# ═══════════════════════════════════════════

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    invoice_date: datetime
    client_id: int
    project_id: int
    eik: Optional[str] = None
    mol: Optional[str] = None
    vat_number: Optional[str] = None
    amount: float
    currency: str
    type: str
    stripe_reference_id: Optional[str] = None
    stripe_hosted_url: Optional[str] = None
    pdf_path: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════
#  Stripe Checkout
# ═══════════════════════════════════════════

class CheckoutRequest(BaseModel):
    project_id: int
    success_url: str = "http://localhost:5173/success"
    cancel_url: str = "http://localhost:5173/cancel"
    payment_method: str = "card"  # "card" or "bank_transfer"
