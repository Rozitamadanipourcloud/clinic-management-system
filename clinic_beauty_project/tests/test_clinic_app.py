import sqlite3
import tempfile
import unittest
import  sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
  
from src.database import Database
from src.repository import ClinicRepository
from src.services import ClinicService, ReportService
# original import replaced below
# from clinic_app import Database, ClinicRepository, ClinicService, ReportService


class ClinicAppServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "test.db")
        self.repo = ClinicRepository(self.db)
        self.service = ClinicService(self.repo)
        self.reports = ReportService(self.repo)
        self.customer_id = self.service.add_customer("سارا احمدی", "09123456789", "مشتری آزمایشی")
        self.service_id = self.service.add_service("پاکسازی پوست", 500000, 60)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_customer_validation_and_duplicate_phone(self):
        with self.assertRaises(ValueError):
            self.service.add_customer("", "09111111111")
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.add_customer("مشتری دوم", "09123456789")
        self.service.update_customer(self.customer_id, "سارا محمدی", "09123456789", "ویرایش شد")
        self.assertEqual(self.repo.one("SELECT name FROM customers WHERE id=?", (self.customer_id,))["name"], "سارا محمدی")

    def test_service_validation(self):
        with self.assertRaises(ValueError):
            self.service.add_service("خدمت نامعتبر", 1000, 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.add_service("پاکسازی پوست", 700000, 30)

    def test_appointment_overlap_and_adjacent_slots(self):
        first = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-01 10:00")
        with self.assertRaises(ValueError):
            self.service.add_appointment(self.customer_id, self.service_id, "2030-01-01 10:30")
        second = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-01 11:00")
        self.assertNotEqual(first, second)

    def test_snapshot_is_stable_when_service_tariff_changes(self):
        appointment_id = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-02 10:00")
        self.service.update_service(self.service_id, "پاکسازی پوست", 800000, 90)
        row = self.repo.one("SELECT service_price, service_duration_minutes FROM appointments WHERE id=?", (appointment_id,))
        self.assertEqual(row["service_price"], 500000)
        self.assertEqual(row["service_duration_minutes"], 60)
        # بازه قبلی همچنان ۶۰ دقیقه است؛ نوبت ساعت ۱۱ باید مجاز باشد.
        next_id = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-02 11:00")
        self.assertTrue(next_id > appointment_id)

    def test_appointment_update_and_status(self):
        first = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-03 10:00")
        second = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-03 12:00")
        with self.assertRaises(ValueError):
            self.service.update_appointment(second, self.customer_id, self.service_id, "2030-01-03 10:30")
        self.service.change_appointment_status(first, "لغو شده")
        self.service.update_appointment(second, self.customer_id, self.service_id, "2030-01-03 10:30", "تغییر زمان")
        self.assertEqual(self.repo.one("SELECT start_time FROM appointments WHERE id=?", (second,))["start_time"], "2030-01-03 10:30")

    def test_multiple_payments_and_overpayment_protection(self):
        appointment_id = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-04 10:00")
        p1 = self.service.add_payment(appointment_id, 200000, "بیعانه")
        p2 = self.service.add_payment(appointment_id, 300000, "تسویه")
        with self.assertRaises(ValueError):
            self.service.add_payment(appointment_id, 1)
        with self.assertRaises(ValueError):
            self.service.update_payment(p1, appointment_id, 250001)
        self.service.update_payment(p1, appointment_id, 150000, "اصلاح پرداخت")
        total = self.repo.one("SELECT SUM(amount) AS total FROM payments WHERE appointment_id=?", (appointment_id,))["total"]
        self.assertEqual(total, 450000)
        self.service.delete_payment(p2)
        self.assertEqual(self.repo.one("SELECT COUNT(*) AS n FROM payments WHERE appointment_id=?", (appointment_id,))["n"], 1)

    def test_service_change_cannot_make_price_less_than_paid_amount(self):
        appointment_id = self.service.add_appointment(self.customer_id, self.service_id, "2030-01-05 10:00")
        self.service.add_payment(appointment_id, 400000)
        cheaper_service = self.service.add_service("خدمت ارزان", 300000, 20)
        with self.assertRaises(ValueError):
            self.service.update_appointment(appointment_id, self.customer_id, cheaper_service, "2030-01-05 10:00")

    def test_daily_monthly_reports(self):
        appointment_id = self.service.add_appointment(self.customer_id, self.service_id, "2030-02-10 10:00")
        self.service.add_payment(appointment_id, 100000)
        # تاریخ پرداخت را برای آزمون گزارش به تاریخ ثابت منتقل می‌کنیم.
        self.repo.execute("UPDATE payments SET paid_at='2030-02-10 13:00' WHERE appointment_id=?", (appointment_id,))
        self.db.conn.commit()
        daily = self.reports.daily("2030-02-10")
        monthly = self.reports.monthly("2030-02")
        self.assertEqual(daily["appointments"], 1)
        self.assertEqual(daily["income"], 100000)
        self.assertEqual(monthly["appointments"], 1)
        self.assertEqual(monthly["income"], 100000)

    def test_delete_customer_with_appointment_is_restricted(self):
        self.service.add_appointment(self.customer_id, self.service_id, "2030-03-01 10:00")
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.delete_customer(self.customer_id)


class LegacyMigrationTests(unittest.TestCase):
    def test_old_database_gets_snapshot_columns_and_status_migration(self):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "legacy.db"
        conn = sqlite3.connect(path)
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, notes TEXT DEFAULT '');
            CREATE TABLE services (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, price INTEGER NOT NULL, duration INTEGER NOT NULL DEFAULT 30);
            CREATE TABLE appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, service_id INTEGER NOT NULL, start_time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'رزرو', notes TEXT DEFAULT '', FOREIGN KEY(customer_id) REFERENCES customers(id), FOREIGN KEY(service_id) REFERENCES services(id));
            CREATE TABLE payments (id INTEGER PRIMARY KEY AUTOINCREMENT, appointment_id INTEGER NOT NULL, amount INTEGER NOT NULL, paid_at TEXT NOT NULL, note TEXT DEFAULT '', FOREIGN KEY(appointment_id) REFERENCES appointments(id));
            INSERT INTO customers(name,phone) VALUES('مشتری قدیمی','09120000000');
            INSERT INTO services(name,price,duration) VALUES('خدمت قدیمی',450000,45);
            INSERT INTO appointments(customer_id,service_id,start_time,status) VALUES(1,1,'2029-05-01 10:00','لغو');
        """)
        conn.commit()
        conn.close()
        db = Database(path)
        row = db.conn.execute("SELECT service_price, service_duration_minutes, status FROM appointments WHERE id=1").fetchone()
        self.assertEqual(row["service_price"], 450000)
        self.assertEqual(row["service_duration_minutes"], 45)
        self.assertEqual(row["status"], "لغو شده")
        db.close()
        temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
