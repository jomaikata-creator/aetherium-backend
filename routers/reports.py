"""Payroll reports — monthly commission calculations."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Employee, EmployeeRole, Project, ProjectStatus, Client
from auth import get_current_employee, require_admin

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/payroll")
def payroll_report(
    month: str = Query(description="YYYY-MM"),
    db: Session = Depends(get_db),
    emp: Employee = Depends(require_admin),
):
    """Calculate how much each employee should be paid for a given month.
    
    For each project, creative gets creative_percent% of full_price,
    and the creative's lead gets lead_percent% of full_price.
    Only projects in ready_to_deploy or completed are counted.
    """
    try:
        year, mon = map(int, month.split("-"))
    except (ValueError, AttributeError):
        raise HTTPException(400, "Month must be YYYY-MM format")

    # Eligible projects: ready_to_deploy or completed
    projects = (
        db.query(Project)
        .filter(
            Project.status.in_([ProjectStatus.ready_to_deploy, ProjectStatus.completed]),
        )
        .all()
    )

    # employee_id → {name, role, projects: [{name, percent, amount}], total}
    payouts: dict[int, dict] = {}

    for p in projects:
        client = p.client
        if not client or not client.assigned_to:
            continue

        creative = db.query(Employee).filter(Employee.id == client.assigned_to).first()
        if not creative:
            continue

        # Creative payout
        if p.creative_percent > 0:
            amount = round(p.full_price * p.creative_percent / 100, 2)
            if creative.id not in payouts:
                payouts[creative.id] = {
                    "employee_id": creative.id,
                    "full_name": creative.full_name,
                    "role": creative.role.value,
                    "projects": [],
                    "total": 0,
                }
            payouts[creative.id]["projects"].append({
                "project_name": p.project_name,
                "percent": p.creative_percent,
                "amount": amount,
            })
            payouts[creative.id]["total"] = round(payouts[creative.id]["total"] + amount, 2)

        # Lead payout (if creative has a manager)
        if p.lead_percent > 0 and creative.manager_id:
            lead = db.query(Employee).filter(Employee.id == creative.manager_id).first()
            if lead and lead.role == EmployeeRole.lead:
                amount = round(p.full_price * p.lead_percent / 100, 2)
                if lead.id not in payouts:
                    payouts[lead.id] = {
                        "employee_id": lead.id,
                        "full_name": lead.full_name,
                        "role": lead.role.value,
                        "projects": [],
                        "total": 0,
                    }
                payouts[lead.id]["projects"].append({
                    "project_name": p.project_name,
                    "percent": p.lead_percent,
                    "amount": amount,
                })
                payouts[lead.id]["total"] = round(payouts[lead.id]["total"] + amount, 2)

    return {
        "month": month,
        "generated_at": datetime.utcnow().isoformat(),
        "employees": sorted(payouts.values(), key=lambda x: x["total"], reverse=True),
        "grand_total": round(sum(e["total"] for e in payouts.values()), 2),
    }
