# -*- coding: utf-8 -*-
"""قواعد کسب‌وکار، اعتبارسنجی و گزارش‌گیری."""
from __future__ import annotations
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any
from src.repository import ClinicRepository
from src.config import DATETIME_FORMAT, APPOINTMENT_STATUSES

class ClinicService:
    def __init__(self, repo: ClinicRepository):
        self.repo = repo

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        result = str(value or "").strip()
        if not result:
            raise ValueError(f"واردکردن {label} الزامی است.")
        return result

    @staticmethod
    def _phone(value: str) -> str:
        phone = str(value or "").strip()
        if not re.fullmatch(r"[0-9+()\- ]{7,20}", phone) or sum(ch.isdigit() for ch in phone) < 7:
            raise ValueError("شماره تلفن معتبر نیست؛ حداقل ۷ رقم وارد کنید.")
        return phone

    @staticmethod
    def _positive_int(value: Any, label: str, allow_zero: bool = False) -> int:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"{label} باید عدد صحیح باشد.")
        if number < 0 or (number == 0 and not allow_zero):
            condition = "صفر یا بیشتر" if allow_zero else "بزرگ‌تر از صفر"
            raise ValueError(f"{label} باید {condition} باشد.")
        return number

    @staticmethod
    def parse_datetime(value: str) -> datetime:
        raw = str(value or "").strip()
        try:
            parsed = datetime.strptime(raw, DATETIME_FORMAT)
        except ValueError:
            raise ValueError("زمان باید با قالب YYYY-MM-DD HH:MM وارد شود؛ مثال: 2026-11-14 15:30")
        if parsed.strftime(DATETIME_FORMAT) != raw:
            raise ValueError("قالب زمان صحیح نیست. مثال: 2026-11-14 15:30")
        return parsed

    # مشتریان ---------------------------------------------------------------
    def add_customer(self, name: str, phone: str, notes: str = "") -> int:
        name = self._required_text(name, "نام مشتری")
        phone = self._phone(phone)
        with self.repo.conn:
            cur = self.repo.execute(
                "INSERT INTO customers(name, phone, notes) VALUES(?,?,?)",
                (name, phone, str(notes or "").strip()),
            )
        return int(cur.lastrowid)

    def update_customer(self, customer_id: int, name: str, phone: str, notes: str = "") -> None:
        name = self._required_text(name, "نام مشتری")
        phone = self._phone(phone)
        with self.repo.conn:
            cur = self.repo.execute(
                "UPDATE customers SET name=?, phone=?, notes=? WHERE id=?",
                (name, phone, str(notes or "").strip(), int(customer_id)),
            )
            if cur.rowcount == 0:
                raise ValueError("مشتری موردنظر پیدا نشد.")

    def delete_customer(self, customer_id: int) -> None:
        with self.repo.conn:
            cur = self.repo.execute("DELETE FROM customers WHERE id=?", (int(customer_id),))
            if cur.rowcount == 0:
                raise ValueError("مشتری موردنظر پیدا نشد.")

    # خدمات -----------------------------------------------------------------
    def add_service(self, name: str, price: Any, duration: Any) -> int:
        name = self._required_text(name, "نام خدمت")
        price_value = self._positive_int(price, "قیمت", allow_zero=True)
        duration_value = self._positive_int(duration, "مدت خدمت")
        with self.repo.conn:
            cur = self.repo.execute(
                "INSERT INTO services(name, price, duration) VALUES(?,?,?)",
                (name, price_value, duration_value),
            )
        return int(cur.lastrowid)

    def update_service(self, service_id: int, name: str, price: Any, duration: Any) -> None:
        name = self._required_text(name, "نام خدمت")
        price_value = self._positive_int(price, "قیمت", allow_zero=True)
        duration_value = self._positive_int(duration, "مدت خدمت")
        with self.repo.conn:
            cur = self.repo.execute(
                "UPDATE services SET name=?, price=?, duration=? WHERE id=?",
                (name, price_value, duration_value, int(service_id)),
            )
            if cur.rowcount == 0:
                raise ValueError("خدمت موردنظر پیدا نشد.")

    def delete_service(self, service_id: int) -> None:
        with self.repo.conn:
            cur = self.repo.execute("DELETE FROM services WHERE id=?", (int(service_id),))
            if cur.rowcount == 0:
                raise ValueError("خدمت موردنظر پیدا نشد.")

    # نوبت‌ها ---------------------------------------------------------------
    def _get_service(self, service_id: int) -> sqlite3.Row:
        row = self.repo.one("SELECT * FROM services WHERE id=?", (int(service_id),))
        if row is None:
            raise ValueError("خدمت انتخاب‌شده وجود ندارد.")
        return row

    def _get_customer(self, customer_id: int) -> sqlite3.Row:
        row = self.repo.one("SELECT * FROM customers WHERE id=?", (int(customer_id),))
        if row is None:
            raise ValueError("مشتری انتخاب‌شده وجود ندارد.")
        return row

    def _check_overlap(
        self,
        start: datetime,
        duration_minutes: int,
        exclude_appointment_id: int | None = None,
    ) -> None:
        end = start + timedelta(minutes=duration_minutes)
        rows = self.repo.all(
            """SELECT id, start_time, service_duration_minutes, status
               FROM appointments
               WHERE status NOT IN ('لغو شده', 'لغو')"""
        )
        for row in rows:
            if exclude_appointment_id is not None and int(row["id"]) == int(exclude_appointment_id):
                continue
            other_start = self.parse_datetime(row["start_time"])
            other_end = other_start + timedelta(minutes=int(row["service_duration_minutes"]))
            # بازه‌ها نیمه‌باز هستند؛ پایان یک نوبت می‌تواند دقیقاً شروع بعدی باشد.
            if start < other_end and end > other_start:
                raise ValueError(
                    f"این زمان با نوبت شماره {row['id']} تداخل دارد. "
                    f"زمان آن نوبت: {other_start.strftime(DATETIME_FORMAT)}"
                )

    def add_appointment(
        self, customer_id: int, service_id: int, start_time: str, notes: str = ""
    ) -> int:
        customer_id = int(customer_id)
        service_id = int(service_id)
        start = self.parse_datetime(start_time)
        with self.repo.db.transaction():
            self._get_customer(customer_id)
            service = self._get_service(service_id)
            duration = int(service["duration"])
            self._check_overlap(start, duration)
            cur = self.repo.execute(
                """INSERT INTO appointments
                   (customer_id, service_id, start_time, status, notes,
                    service_price, service_duration_minutes)
                   VALUES(?,?,?,'رزرو',?,?,?)""",
                (
                    customer_id,
                    service_id,
                    start.strftime(DATETIME_FORMAT),
                    str(notes or "").strip(),
                    int(service["price"]),
                    duration,
                ),
            )
        return int(cur.lastrowid)

    def update_appointment(
        self,
        appointment_id: int,
        customer_id: int,
        service_id: int,
        start_time: str,
        notes: str = "",
    ) -> None:
        appointment_id = int(appointment_id)
        customer_id = int(customer_id)
        service_id = int(service_id)
        start = self.parse_datetime(start_time)
        with self.repo.db.transaction():
            old = self.repo.one("SELECT * FROM appointments WHERE id=?", (appointment_id,))
            if old is None:
                raise ValueError("نوبت موردنظر پیدا نشد.")
            self._get_customer(customer_id)
            service = self._get_service(service_id)

            # اگر خدمت عوض نشده باشد snapshot مالی/زمانی قبلی حفظ می‌شود.
            if int(old["service_id"]) == service_id:
                price_snapshot = int(old["service_price"])
                duration_snapshot = int(old["service_duration_minutes"])
            else:
                price_snapshot = int(service["price"])
                duration_snapshot = int(service["duration"])

            total_paid = int(self.repo.one(
                "SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE appointment_id=?",
                (appointment_id,),
            )["total"])
            if total_paid > price_snapshot:
                raise ValueError(
                    f"مبلغ پرداخت‌شده این نوبت ({total_paid:,} تومان) از قیمت خدمت جدید "
                    f"({price_snapshot:,} تومان) بیشتر است؛ خدمت دیگری انتخاب کنید."
                )

            if old["status"] != "لغو شده":
                self._check_overlap(start, duration_snapshot, exclude_appointment_id=appointment_id)

            self.repo.execute(
                """UPDATE appointments
                   SET customer_id=?, service_id=?, start_time=?, notes=?,
                       service_price=?, service_duration_minutes=?
                   WHERE id=?""",
                (
                    customer_id,
                    service_id,
                    start.strftime(DATETIME_FORMAT),
                    str(notes or "").strip(),
                    price_snapshot,
                    duration_snapshot,
                    appointment_id,
                ),
            )

    def change_appointment_status(self, appointment_id: int, status: str) -> None:
        appointment_id = int(appointment_id)
        if status not in APPOINTMENT_STATUSES:
            raise ValueError("وضعیت انتخاب‌شده معتبر نیست.")
        with self.repo.db.transaction():
            appointment = self.repo.one(
                "SELECT * FROM appointments WHERE id=?", (appointment_id,)
            )
            if appointment is None:
                raise ValueError("نوبت موردنظر پیدا نشد.")
            if status != "لغو شده":
                self._check_overlap(
                    self.parse_datetime(appointment["start_time"]),
                    int(appointment["service_duration_minutes"]),
                    exclude_appointment_id=appointment_id,
                )
            self.repo.execute(
                "UPDATE appointments SET status=? WHERE id=?",
                (status, appointment_id),
            )

    # پرداخت‌ها -------------------------------------------------------------
    def _validate_payment_target(self, appointment_id: int) -> sqlite3.Row:
        appointment = self.repo.one(
            "SELECT * FROM appointments WHERE id=?", (int(appointment_id),)
        )
        if appointment is None:
            raise ValueError("نوبت انتخاب‌شده پیدا نشد.")
        if appointment["status"] == "لغو شده":
            raise ValueError("برای نوبت لغوشده امکان ثبت پرداخت جدید وجود ندارد.")
        return appointment

    def add_payment(self, appointment_id: int, amount: Any, note: str = "") -> int:
        amount_value = self._positive_int(amount, "مبلغ پرداخت")
        now = datetime.now().strftime(DATETIME_FORMAT)
        with self.repo.db.transaction():
            appointment = self._validate_payment_target(int(appointment_id))
            paid = int(
                self.repo.one(
                    "SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE appointment_id=?",
                    (int(appointment_id),),
                )["total"]
            )
            remaining = int(appointment["service_price"]) - paid
            if amount_value > remaining:
                raise ValueError(f"مبلغ واردشده از مانده نوبت بیشتر است. مانده فعلی: {remaining:,} تومان")
            cur = self.repo.execute(
                "INSERT INTO payments(appointment_id, amount, paid_at, note) VALUES(?,?,?,?)",
                (int(appointment_id), amount_value, now, str(note or "").strip()),
            )
        return int(cur.lastrowid)

    def update_payment(
        self, payment_id: int, appointment_id: int, amount: Any, note: str = ""
    ) -> None:
        payment_id = int(payment_id)
        appointment_id = int(appointment_id)
        amount_value = self._positive_int(amount, "مبلغ پرداخت")
        with self.repo.db.transaction():
            payment = self.repo.one("SELECT * FROM payments WHERE id=?", (payment_id,))
            if payment is None:
                raise ValueError("پرداخت موردنظر پیدا نشد.")
            appointment = self._validate_payment_target(appointment_id)
            paid_without_current = int(
                self.repo.one(
                    """SELECT COALESCE(SUM(amount),0) AS total FROM payments
                       WHERE appointment_id=? AND id<>?""",
                    (appointment_id, payment_id),
                )["total"]
            )
            if amount_value + paid_without_current > int(appointment["service_price"]):
                remaining = int(appointment["service_price"]) - paid_without_current
                raise ValueError(f"مبلغ بیش از سقف قابل ثبت است. حداکثر مبلغ این پرداخت: {remaining:,} تومان")
            self.repo.execute(
                "UPDATE payments SET appointment_id=?, amount=?, note=? WHERE id=?",
                (appointment_id, amount_value, str(note or "").strip(), payment_id),
            )

    def delete_payment(self, payment_id: int) -> None:
        with self.repo.conn:
            cur = self.repo.execute("DELETE FROM payments WHERE id=?", (int(payment_id),))
            if cur.rowcount == 0:
                raise ValueError("پرداخت موردنظر پیدا نشد.")

class ReportService:
    def __init__(self, repo: ClinicRepository):
        self.repo = repo

    def daily(self, day_text: str) -> dict[str, int | str]:
        try:
            day = date.fromisoformat(day_text.strip())
        except ValueError:
            raise ValueError("تاریخ باید با قالب YYYY-MM-DD وارد شود.")
        start = f"{day.isoformat()} 00:00"
        end = f"{day.isoformat()} 23:59"
        appointments = self.repo.one(
            """SELECT COUNT(*) AS total FROM appointments
               WHERE start_time BETWEEN ? AND ? AND status<>'لغو شده'""",
            (start, end),
        )["total"]
        cancelled = self.repo.one(
            """SELECT COUNT(*) AS total FROM appointments
               WHERE start_time BETWEEN ? AND ? AND status='لغو شده'""",
            (start, end),
        )["total"]
        income = self.repo.one(
            "SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE paid_at BETWEEN ? AND ?",
            (start, end),
        )["total"]
        return {"period": day.isoformat(), "appointments": int(appointments),
                "cancelled": int(cancelled), "income": int(income)}

    def monthly(self, month_text: str) -> dict[str, int | str]:
        raw = month_text.strip()
        try:
            parsed = datetime.strptime(raw, "%Y-%m")
        except ValueError:
            raise ValueError("ماه باید با قالب YYYY-MM وارد شود.")
        month = parsed.strftime("%Y-%m")
        appointments = self.repo.one(
            """SELECT COUNT(*) AS total FROM appointments
               WHERE substr(start_time,1,7)=? AND status<>'لغو شده'""",
            (month,),
        )["total"]
        cancelled = self.repo.one(
            """SELECT COUNT(*) AS total FROM appointments
               WHERE substr(start_time,1,7)=? AND status='لغو شده'""",
            (month,),
        )["total"]
        income = self.repo.one(
            "SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE substr(paid_at,1,7)=?",
            (month,),
        )["total"]
        return {"period": month, "appointments": int(appointments),
                "cancelled": int(cancelled), "income": int(income)}

    def dashboard(self) -> dict[str, int]:
        today = date.today().isoformat()
        month = today[:7]
        return {
            "customers": int(self.repo.one("SELECT COUNT(*) AS n FROM customers")["n"]),
            "today_appointments": int(self.repo.one(
                """SELECT COUNT(*) AS n FROM appointments
                   WHERE substr(start_time,1,10)=? AND status='رزرو'""", (today,)
            )["n"]),
            "today_income": int(self.repo.one(
                """SELECT COALESCE(SUM(amount),0) AS n FROM payments
                   WHERE substr(paid_at,1,10)=?""", (today,)
            )["n"]),
            "month_income": int(self.repo.one(
                """SELECT COALESCE(SUM(amount),0) AS n FROM payments
                   WHERE substr(paid_at,1,7)=?""", (month,)
            )["n"]),
        }
