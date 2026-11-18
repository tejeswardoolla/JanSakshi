"""
JanSakshi Serverless API Entrypoint for Vercel.
Exports the FastAPI `app` instance.
"""
import sys
import os

# Add backend directory to sys.path so 'app' and its submodules resolve cleanly
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Import the main FastAPI application instance
from app.main import app  # noqa: E402
