"""Configurações do OdontoManager (podem ser sobrescritas por variáveis de ambiente)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'odontomanager.db'}")
FRONTEND_DIR = BASE_DIR / "frontend"
PASSO_AGENDA_MIN = 15  # granularidade dos horários oferecidos na agenda
