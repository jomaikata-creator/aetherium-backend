"""Seed the database with an initial admin employee."""
import os
from dotenv import load_dotenv
load_dotenv()

from passlib.context import CryptContext
from database import SessionLocal, engine, Base
from models import Employee, EmployeeRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_EMAIL = "aetherium@aetherium.dev"
ADMIN_PASSWORD = "aetherium12345"
ADMIN_NAME = "Admin"


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    existing = db.query(Employee).filter(Employee.email == ADMIN_EMAIL).first()
    if existing:
        print(f"Admin already exists: {existing.email}")
        db.close()
        return

    admin = Employee(
        email=ADMIN_EMAIL,
        password_hash=pwd_context.hash(ADMIN_PASSWORD),
        full_name=ADMIN_NAME,
        role=EmployeeRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    print(f"Admin created: {admin.email} (id={admin.id})")
    db.close()


if __name__ == "__main__":
    seed()
