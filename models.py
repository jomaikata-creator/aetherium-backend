"""SQLAlchemy ORM models — single source of truth."""
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum


# ═══════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════

class EmployeeRole(str, enum.Enum):
    admin = "admin"
    lead = "lead"
    creative = "creative"


class ProjectStatus(str, enum.Enum):
    lead = "lead"
    quoted = "quoted"
    deposit_pending = "deposit_pending"
    building = "building"
    feedback = "feedback"
    awaiting_final = "awaiting_final"
    ready_to_deploy = "ready_to_deploy"
    completed = "completed"


class PaymentMethod(str, enum.Enum):
    stripe_card = "stripe_card"
    bank_transfer = "bank_transfer"
    subscription = "subscription"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    canceled = "canceled"


class InvoiceType(str, enum.Enum):
    deposit = "deposit"
    final = "final"
    monthly = "monthly"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    paid = "paid"


# ═══════════════════════════════════════════
#  Models
# ═══════════════════════════════════════════

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(SAEnum(EmployeeRole), default=EmployeeRole.creative, nullable=False)
    is_active = Column(Boolean, default=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    password_reset_token = Column(String, nullable=True, unique=True)
    password_reset_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    manager = relationship("Employee", remote_side=[id], backref="team")
    clients = relationship("Client", back_populates="assigned_employee")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True)

    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)

    company_name = Column(String, nullable=True)
    eik = Column(String, nullable=True)
    mol = Column(String, nullable=True)
    vat_number = Column(String, nullable=True)
    address = Column(String, nullable=True)

    stripe_customer_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    assigned_employee = relationship("Employee", back_populates="clients")
    projects = relationship("Project", back_populates="client")
    invoices = relationship("Invoice", back_populates="client")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    project_name = Column(String, nullable=False)

    full_price = Column(Float, nullable=False, default=0.0)
    deposit_amount = Column(Float, nullable=False, default=0.0)
    remaining_amount = Column(Float, nullable=False, default=0.0)
    monthly_fee = Column(Float, nullable=False, default=300.0)

    creative_percent = Column(Float, nullable=False, default=0.0)  # % for creative
    lead_percent = Column(Float, nullable=False, default=0.0)      # % for team lead

    website_type = Column(String, nullable=True)
    features = Column(Text, nullable=True)
    pages_count = Column(Integer, nullable=True)

    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.lead, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="projects")
    payments = relationship("Payment", back_populates="project")
    subscriptions = relationship("Subscription", back_populates="project")
    invoices = relationship("Invoice", back_populates="project")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    stripe_payment_intent_id = Column(String, nullable=True)
    stripe_invoice_id = Column(String, nullable=True)
    stripe_checkout_session_id = Column(String, nullable=True)
    checkout_url = Column(String, nullable=True)

    amount = Column(Float, nullable=False)
    method = Column(SAEnum(PaymentMethod), nullable=False)
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.pending, nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="payments")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    stripe_subscription_id = Column(String, nullable=True)
    monthly_fee = Column(Float, nullable=False)

    status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False)
    start_date = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="subscriptions")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)

    invoice_number = Column(String, nullable=False, unique=True)
    invoice_date = Column(DateTime, default=datetime.datetime.utcnow)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    eik = Column(String, nullable=True)
    mol = Column(String, nullable=True)
    vat_number = Column(String, nullable=True)

    amount = Column(Float, nullable=False)
    currency = Column(String, default="EUR")

    type = Column(SAEnum(InvoiceType), nullable=False)

    stripe_reference_id = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)

    status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.draft, nullable=False)

    client = relationship("Client", back_populates="invoices")
    project = relationship("Project", back_populates="invoices")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    read = Column(Boolean, default=False)
