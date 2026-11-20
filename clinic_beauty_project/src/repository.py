# -*- coding: utf-8 -*-
"""لایه دسترسی به داده‌ها."""
from __future__ import annotations
import sqlite3
from typing import Any, Iterable
from src.database import Database

class ClinicRepository:
    def __init__(self, database: Database):
        self.db = database
        self.conn = database.conn

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, tuple(params))

    def customers(self, search: str = "") -> list[sqlite3.Row]:
        term = f"%{search.strip()}%"
        return self.all(
            """SELECT * FROM customers
               WHERE name LIKE ? OR phone LIKE ?
               ORDER BY name COLLATE NOCASE, id DESC""",
            (term, term),
        )

    def services(self) -> list[sqlite3.Row]:
        return self.all("SELECT * FROM services ORDER BY name COLLATE NOCASE")

    def appointments(self) -> list[sqlite3.Row]:
        return self.all(
            """SELECT a.id, a.customer_id, a.service_id, a.start_time, a.status,
                      a.notes, a.service_price, a.service_duration_minutes,
                      c.name AS customer_name, s.name AS service_name,
                      COALESCE((SELECT SUM(p.amount) FROM payments p
                                WHERE p.appointment_id=a.id), 0) AS paid
               FROM appointments a
               JOIN customers c ON c.id=a.customer_id
               JOIN services s ON s.id=a.service_id
               ORDER BY a.start_time DESC, a.id DESC"""
        )

    def payments(self) -> list[sqlite3.Row]:
        return self.all(
            """SELECT p.id, p.appointment_id, p.amount, p.paid_at, p.note,
                      c.name AS customer_name, s.name AS service_name,
                      a.start_time
               FROM payments p
               JOIN appointments a ON a.id=p.appointment_id
               JOIN customers c ON c.id=a.customer_id
               JOIN services s ON s.id=a.service_id
               ORDER BY p.paid_at DESC, p.id DESC"""
        )
