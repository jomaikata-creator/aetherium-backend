"""Aetherium Backend — FastAPI application entry point."""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, SessionLocal
from models import Employee, EmployeeRole
from auth import hash_password
from routers import auth, employees, clients, projects, consultations, webhooks, invoices, reports


def _seed_admin():
    """Create default admin if none exists."""
    db = SessionLocal()
    try:
        if not db.query(Employee).filter(Employee.role == EmployeeRole.admin).first():
            admin = Employee(
                email="aetherium@aetherium.dev",
                password_hash=hash_password("aetherium12345"),
                full_name="Admin",
                role=EmployeeRole.admin,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"[seed] Admin created: aetherium@aetherium.dev")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


app = FastAPI(title="Aetherium API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(consultations.router)
app.include_router(webhooks.router)
app.include_router(invoices.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
