"""Employee management — admin only."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Employee, EmployeeRole
from schemas import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from auth import hash_password, get_current_employee, require_admin

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
):
    if db.query(Employee).filter(Employee.email == data.email).first():
        raise HTTPException(400, "Email already exists")

    if data.role not in ("admin", "lead", "creative"):
        raise HTTPException(400, "Role must be admin, lead, or creative")

    emp = Employee(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=EmployeeRole(data.role),
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
):
    return db.query(Employee).order_by(Employee.created_at.desc()).all()


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    return emp


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")

    if data.email is not None:
        existing = db.query(Employee).filter(Employee.email == data.email, Employee.id != employee_id).first()
        if existing:
            raise HTTPException(400, "Email already taken")
        emp.email = data.email
    if data.password is not None:
        emp.password_hash = hash_password(data.password)
    if data.full_name is not None:
        emp.full_name = data.full_name
    if data.role is not None:
        if data.role not in ("admin", "lead", "creative"):
            raise HTTPException(400, "Role must be admin, lead, or creative")
        emp.role = EmployeeRole(data.role)
    if data.is_active is not None:
        emp.is_active = data.is_active

    db.commit()
    db.refresh(emp)
    return emp


@router.delete("/{employee_id}", status_code=204)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_admin),
):
    if employee_id == current.id:
        raise HTTPException(400, "Cannot delete yourself")
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    db.delete(emp)
    db.commit()
