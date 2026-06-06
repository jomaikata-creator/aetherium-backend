"""ASGI entry point for production (gunicorn + uvicorn workers).
Import the FastAPI app from main — separate from the dev runner.
"""
from main import app
