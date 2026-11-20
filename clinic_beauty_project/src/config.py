# -*- coding: utf-8 -*-
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "clinic.db"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
APPOINTMENT_STATUSES = ("رزرو", "انجام‌شده", "لغو شده")
