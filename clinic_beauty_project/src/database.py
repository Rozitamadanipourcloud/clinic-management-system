# -*- coding: utf-8 -*-
"""مدیریت اتصال SQLite، ساخت جدول‌ها و ارتقای دیتابیس."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from src.config import DB_PATH

class Database:
    def __init__(self, path: str | Path = DB_PATH):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 15000")
        self.initialize()

    def initialize(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                price INTEGER NOT NULL CHECK(price >= 0),
                duration INTEGER NOT NULL DEFAULT 30 CHECK(duration > 0)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'رزرو',
                notes TEXT NOT NULL DEFAULT '',
                service_price INTEGER NOT NULL DEFAULT 0 CHECK(service_price >= 0),
                service_duration_minutes INTEGER NOT NULL DEFAULT 30
                    CHECK(service_duration_minutes > 0),
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
                FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                appointment_id INTEGER NOT NULL,
                amount INTEGER NOT NULL CHECK(amount > 0),
                paid_at TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_appointments_start
                ON appointments(start_time);
            CREATE INDEX IF NOT EXISTS idx_payments_paid_at
                ON payments(paid_at);
            CREATE INDEX IF NOT EXISTS idx_payments_appointment
                ON payments(appointment_id);
            """
        )

        # سازگاری با clinic.db ساخته‌شده توسط نسخه قبلی برنامه:
        appointment_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(appointments)").fetchall()
        }
        added_price_snapshot = "service_price" not in appointment_columns
        added_duration_snapshot = "service_duration_minutes" not in appointment_columns
        if added_price_snapshot:
            self.conn.execute(
                "ALTER TABLE appointments ADD COLUMN service_price INTEGER NOT NULL DEFAULT 0"
            )
        if added_duration_snapshot:
            self.conn.execute(
                "ALTER TABLE appointments ADD COLUMN service_duration_minutes INTEGER NOT NULL DEFAULT 30"
            )

        # برای رکوردهای نسخه قدیمی، قیمت و مدت فعلی خدمت به عنوان snapshot اولیه ثبت می‌شود.
        # این عملیات فقط در اولین ارتقا انجام می‌شود تا snapshot های جدیدتر بازنویسی نشوند.
        if added_price_snapshot:
            self.conn.execute(
                """UPDATE appointments
                   SET service_price = COALESCE((SELECT price FROM services WHERE services.id=appointments.service_id), 0)"""
            )
        if added_duration_snapshot:
            self.conn.execute(
                """UPDATE appointments
                   SET service_duration_minutes = COALESCE((SELECT duration FROM services WHERE services.id=appointments.service_id), 30)"""
            )
        self.conn.execute(
            "UPDATE appointments SET status='لغو شده' WHERE status='لغو'"
        )
        self.conn.commit()

    @contextmanager
    def transaction(self):
        """تراکنش اتمیک؛ برای جلوگیری از ثبت هم‌زمان نوبت‌های متداخل."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()
