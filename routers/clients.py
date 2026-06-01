"""Client management — scoped by role."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Client, Employee, EmployeeRole
from schemas import ClientCreate, ClientUpdate, ClientResponse
from auth import get_current_employee, require_admin_or_lead

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _can_access_client(emp: Employee, client: Client) -> bool:
    if emp.role == EmployeeRole.admin:
        return True
    return client.assigned_to == emp.id


@router.post("", response_model=ClientResponse, status_code=201)
def create_client(
    data: ClientCreate,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    # If lead creates and doesn't specify assigned_to, assign to self
    assigned = data.assigned_to
    if emp.role == EmployeeRole.lead and assigned is None:
        assigned = emp.id

    # Validate assigned employee exists
    if assigned is not None:
        target = db.query(Employee).filter(Employee.id == assigned).first()
        if not target:
            raise HTTPException(400, "Assigned employee not found")

    client = Client(**{**data.model_dump(), "assigned_to": assigned})
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("", response_model=list[ClientResponse])
def list_clients(
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    if emp.role == EmployeeRole.admin:
        return db.query(Client).order_by(Client.created_at.desc()).all()
    return (
        db.query(Client)
        .filter(Client.assigned_to == emp.id)
        .order_by(Client.created_at.desc())
        .all()
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")
    if not _can_access_client(emp, client):
        raise HTTPException(403, "Not your client")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    data: ClientUpdate,
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin_or_lead),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")
    if not _can_access_client(emp, client):
        raise HTTPException(403, "Not your client")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    emp: Employee = Depends(get_current_employee),
):
    if emp.role != EmployeeRole.admin:
        raise HTTPException(403, "Admin only")
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")
    db.delete(client)
    db.commit()
