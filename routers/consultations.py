"""Public consultation form — no auth required."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Consultation
from schemas import ConsultationCreate, ConsultationResponse

router = APIRouter(prefix="/api/consultations", tags=["consultations"])


@router.post("", response_model=ConsultationResponse, status_code=201)
def create_consultation(data: ConsultationCreate, db: Session = Depends(get_db)):
    c = Consultation(name=data.name, email=data.email, message=data.message or "")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("", response_model=list[ConsultationResponse])
def list_consultations(db: Session = Depends(get_db)):
    return db.query(Consultation).order_by(Consultation.created_at.desc()).all()
