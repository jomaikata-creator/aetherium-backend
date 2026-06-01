"""Auth endpoints — login, me, set-password, forgot-password."""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Employee
from auth import verify_password, create_access_token, get_current_employee, hash_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class SetPasswordRequest(BaseModel):
    token: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class EmployeeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee: EmployeeResponse


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.email == data.email).first()
    if not employee or not employee.password_hash or not verify_password(data.password, employee.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not employee.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    token = create_access_token(employee.id, employee.role.value)
    return LoginResponse(
        access_token=token,
        employee=EmployeeResponse.model_validate(employee),
    )


@router.get("/me", response_model=EmployeeResponse)
def me(emp: Employee = Depends(get_current_employee)):
    return EmployeeResponse.model_validate(emp)


@router.post("/set-password")
def set_password(data: SetPasswordRequest, db: Session = Depends(get_db)):
    """Set password using invite/reset token."""
    employee = (
        db.query(Employee)
        .filter(Employee.password_reset_token == data.token)
        .first()
    )
    if not employee:
        raise HTTPException(400, "Invalid or expired token")
    if employee.password_reset_expires and employee.password_reset_expires < datetime.utcnow():
        raise HTTPException(400, "Token has expired")

    if len(data.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    employee.password_hash = hash_password(data.password)
    employee.password_reset_token = None
    employee.password_reset_expires = None
    db.commit()

    return {"message": "Password set successfully. You can now log in."}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send a password reset email (requires RESEND_API_KEY for actual delivery)."""
    employee = db.query(Employee).filter(Employee.email == data.email).first()
    if not employee:
        # Don't reveal whether email exists
        return {"message": "If that email exists, a reset link has been sent."}

    token = secrets.token_urlsafe(32)
    employee.password_reset_token = token
    employee.password_reset_expires = datetime.utcnow() + timedelta(hours=48)
    db.commit()

    from email_service import send_invite_email
    send_invite_email(employee.email, employee.full_name, token, employee.role.value)

    return {"message": "If that email exists, a reset link has been sent."}
