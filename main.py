"""Entry point so the desk API starts with `uvicorn main:app --reload --port 8000` from the hw5 folder.

The app itself lives in backend/main.py.
"""

from backend.main import app  # noqa: F401
