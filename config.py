import os
from pathlib import Path

from dotenv import load_dotenv


# Step 1: load local settings

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# Step 2: expose application settings

def get_setting(name, default=""):
    """Read local environment variables or deployed Streamlit secrets."""

    value = os.environ.get(name)
    if value:
        return value

    try:
        import streamlit as st

        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError, RuntimeError):
        return default


DATABASE_PATH = BASE_DIR / "data" / "railpulse_chatbot.db"
API_KEY = get_setting("LLM_API_KEY")
BASE_URL = get_setting("LLM_BASE_URL").rstrip("/")
MODEL = get_setting("LLM_MODEL")
API_STYLE = get_setting("LLM_API_STYLE", "responses").lower()
QUERY_ROW_LIMIT = 100
REQUEST_TIMEOUT_SECONDS = 90
