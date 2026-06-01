"""Authentication — JWT tokens + password hashing + role-based access."""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import Employee, EmployeeRole

# ── Config ──────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "aetherium-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()


# ── Password helpers ────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ─────────────────────────────

def create_access_token(employee_id: int, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(employee_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


# ── Dependency — current employee ───────────

def get_current_employee(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> Employee:
    """Extract and validate the employee from the Bearer token."""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    employee_id = int(payload.get("sub", 0))
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Employee not found or inactive")
    return employee


# ── Role guards ─────────────────────────────

def require_admin(emp: Employee = Depends(get_current_employee)) -> Employee:
    if emp.role != EmployeeRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return emp


def require_admin_or_lead(emp: Employee = Depends(get_current_employee)) -> Employee:
    if emp.role not in (EmployeeRole.admin, EmployeeRole.lead):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or lead only")
    return emp


# ── Visibility helpers ───────────────────────

def get_visible_employee_ids(emp: Employee, db: Session) -> list[int]:
    """Return list of employee IDs this employee can view.
    admin → all employees
    lead → self + team (employees whose manager_id = lead.id)
    creative → self only
    """
    if emp.role == EmployeeRole.admin:
        return [e.id for e in db.query(Employee.id).all()]
    if emp.role == EmployeeRole.lead:
        team_ids = [emp.id] + [
            e.id for e in db.query(Employee.id).filter(Employee.manager_id == emp.id).all()
        ]
        return team_ids
    return [emp.id]


def can_edit_client(emp: Employee, client) -> bool:
    """Admin can edit any. Lead can edit their own clients. Creative cannot edit."""
    if emp.role == EmployeeRole.admin:
        return True
    if emp.role == EmployeeRole.lead and client.assigned_to == emp.id:
        return True
    return False


def can_edit_project(emp: Employee, project) -> bool:
    """Admin can edit any. Lead can edit projects of their own clients. Creative cannot edit."""
    if emp.role == EmployeeRole.admin:
        return True
    if emp.role == EmployeeRole.lead and project.client.assigned_to == emp.id:
        return True
    return False
