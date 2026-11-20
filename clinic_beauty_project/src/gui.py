# -*- coding: utf-8 -*-
"""رابط گرافیکی برنامه با Tkinter."""
from __future__ import annotations
import sqlite3
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk
from src.config import DB_PATH, DATETIME_FORMAT, APPOINTMENT_STATUSES
from src.database import Database
from src.repository import ClinicRepository
from src.services import ClinicService, ReportService

class ClinicApp(tk.Tk):
    def __init__(self, db_path: str | Path = DB_PATH):
        super().__init__()
        self.title("نرم‌افزار مدیریت و نوبت‌دهی کلینیک زیبایی")
        self.geometry("1250x780")
        self.minsize(1000, 650)

        self.database = Database(db_path)
        self.repo = ClinicRepository(self.database)
        self.service = ClinicService(self.repo)
        self.reports = ReportService(self.repo)

        self._configure_style()
        self._build_dashboard()

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.customer_tab = ttk.Frame(self.tabs)
        self.service_tab = ttk.Frame(self.tabs)
        self.appointment_tab = ttk.Frame(self.tabs)
        self.payment_tab = ttk.Frame(self.tabs)
        self.report_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.customer_tab, text="مشتریان")
        self.tabs.add(self.service_tab, text="خدمات")
        self.tabs.add(self.appointment_tab, text="نوبت‌ها")
        self.tabs.add(self.payment_tab, text="پرداخت‌ها")
        self.tabs.add(self.report_tab, text="گزارش‌ها")

        self._build_customer_tab()
        self._build_service_tab()
        self._build_appointment_tab()
        self._build_payment_tab()
        self._build_report_tab()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=27, font=("Tahoma", 9))
        style.configure("Treeview.Heading", font=("Tahoma", 9, "bold"))
        style.configure("TButton", padding=5, font=("Tahoma", 9))
        style.configure("TLabel", font=("Tahoma", 9))
        style.configure("TLabelframe.Label", font=("Tahoma", 9, "bold"))

    def _build_dashboard(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(header, text="سامانه مدیریت کلینیک زیبایی", font=("Tahoma", 15, "bold")).pack(side="right")
        ttk.Label(header, text="اطلاعات و عملیات کلینیک", foreground="#555").pack(side="left")

        self.dashboard_vars = {
            "customers": tk.StringVar(value="0"),
            "today_appointments": tk.StringVar(value="0"),
            "today_income": tk.StringVar(value="0 تومان"),
            "month_income": tk.StringVar(value="0 تومان"),
        }
        cards = ttk.Frame(self)
        cards.pack(fill="x", padx=10, pady=(4, 10))
        labels = [
            ("customers", "تعداد مشتریان"),
            ("today_appointments", "نوبت‌های رزرو امروز"),
            ("today_income", "دریافتی امروز"),
            ("month_income", "دریافتی این ماه"),
        ]
        for key, title in labels:
            card = ttk.LabelFrame(cards, text=title, padding=8)
            card.pack(side="right", fill="x", expand=True, padx=4)
            ttk.Label(card, textvariable=self.dashboard_vars[key], font=("Tahoma", 12, "bold")).pack()

    @staticmethod
    def _form_entry(parent, label: str, variable: tk.StringVar, width: int = 18) -> None:
        ttk.Label(parent, text=label).pack(side="right", padx=(8, 3))
        ttk.Entry(parent, textvariable=variable, width=width, justify="right").pack(side="right", padx=3)

    def _make_tree(self, parent, columns, headings, widths=None):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True, padx=7, pady=7)
        tree = ttk.Treeview(container, columns=columns, show="headings", selectmode="browse")
        widths = widths or {}
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=widths.get(col, 120), minwidth=65, anchor="center")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return tree

    @staticmethod
    def _selected_id(tree) -> int | None:
        selected = tree.selection()
        if not selected:
            return None
        try:
            return int(tree.item(selected[0], "values")[0])
        except (ValueError, IndexError, TypeError):
            return None

    @staticmethod
    def _clear_tree(tree) -> None:
        for item in tree.get_children():
            tree.delete(item)

    @staticmethod
    def _format_money(amount: int) -> str:
        return f"{int(amount):,}"

    def _show_error(self, error: Exception) -> None:
        messagebox.showerror("خطا", str(error), parent=self)

    # فرم مشتریان ----------------------------------------------------------
    def _build_customer_tab(self) -> None:
        form = ttk.LabelFrame(self.customer_tab, text="اطلاعات مشتری", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.c_name = tk.StringVar()
        self.c_phone = tk.StringVar()
        self.c_notes = tk.StringVar()
        self.c_search = tk.StringVar()
        self._form_entry(form, "نام:", self.c_name, 18)
        self._form_entry(form, "تلفن:", self.c_phone, 17)
        self._form_entry(form, "یادداشت:", self.c_notes, 24)
        ttk.Button(form, text="ثبت مشتری", command=self.add_customer).pack(side="right", padx=3)
        ttk.Button(form, text="ویرایش", command=self.update_customer).pack(side="right", padx=3)
        ttk.Button(form, text="حذف", command=self.delete_customer).pack(side="right", padx=3)
        ttk.Button(form, text="پاک‌کردن فرم", command=self.clear_customer).pack(side="right", padx=3)

        search = ttk.Frame(self.customer_tab)
        search.pack(fill="x", padx=9)
        ttk.Label(search, text="جست‌وجوی نام یا تلفن:").pack(side="right")
        ttk.Entry(search, textvariable=self.c_search, width=25, justify="right").pack(side="right", padx=5)
        ttk.Button(search, text="جست‌وجو", command=self.refresh_customers).pack(side="right", padx=3)
        ttk.Button(search, text="نمایش همه", command=lambda: (self.c_search.set(""), self.refresh_customers())).pack(side="right", padx=3)

        self.customer_tree = self._make_tree(
            self.customer_tab, ("id", "name", "phone", "notes"),
            ("شناسه", "نام مشتری", "شماره تلفن", "یادداشت"),
            {"id": 70, "name": 220, "phone": 170, "notes": 400},
        )
        self.customer_tree.bind("<<TreeviewSelect>>", self.customer_selected)

    def customer_selected(self, _event=None) -> None:
        selected = self.customer_tree.selection()
        if selected:
            values = self.customer_tree.item(selected[0], "values")
            self.c_name.set(values[1])
            self.c_phone.set(values[2])
            self.c_notes.set(values[3])

    def add_customer(self) -> None:
        try:
            self.service.add_customer(self.c_name.get(), self.c_phone.get(), self.c_notes.get())
            self.clear_customer()
            self.refresh_all()
            messagebox.showinfo("ثبت شد", "اطلاعات مشتری با موفقیت ثبت شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error("این شماره تلفن قبلاً ثبت شده است." if isinstance(exc, sqlite3.IntegrityError) else exc)

    def update_customer(self) -> None:
        customer_id = self._selected_id(self.customer_tree)
        if customer_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک مشتری را از جدول انتخاب کنید.", parent=self)
        try:
            self.service.update_customer(customer_id, self.c_name.get(), self.c_phone.get(), self.c_notes.get())
            self.refresh_all()
            messagebox.showinfo("ویرایش شد", "اطلاعات مشتری به‌روزرسانی شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error("این شماره تلفن قبلاً برای مشتری دیگری ثبت شده است." if isinstance(exc, sqlite3.IntegrityError) else exc)

    def delete_customer(self) -> None:
        customer_id = self._selected_id(self.customer_tree)
        if customer_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک مشتری را انتخاب کنید.", parent=self)
        if not messagebox.askyesno("تأیید حذف", "مشتری انتخاب‌شده حذف شود؟", parent=self):
            return
        try:
            self.service.delete_customer(customer_id)
            self.clear_customer()
            self.refresh_all()
        except sqlite3.IntegrityError:
            self._show_error("این مشتری دارای نوبت است؛ برای حفظ سوابق، حذف او مجاز نیست.")
        except ValueError as exc:
            self._show_error(exc)

    def clear_customer(self) -> None:
        self.c_name.set("")
        self.c_phone.set("")
        self.c_notes.set("")
        self.customer_tree.selection_remove(self.customer_tree.selection())

    def refresh_customers(self) -> None:
        self._clear_tree(self.customer_tree)
        for row in self.repo.customers(self.c_search.get()):
            self.customer_tree.insert("", "end", values=(row["id"], row["name"], row["phone"], row["notes"]))

    # فرم خدمات ------------------------------------------------------------
    def _build_service_tab(self) -> None:
        form = ttk.LabelFrame(self.service_tab, text="تعریف خدمت", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.s_name = tk.StringVar()
        self.s_price = tk.StringVar()
        self.s_duration = tk.StringVar(value="30")
        self._form_entry(form, "نام خدمت:", self.s_name, 20)
        self._form_entry(form, "قیمت (تومان):", self.s_price, 15)
        self._form_entry(form, "مدت (دقیقه):", self.s_duration, 12)
        ttk.Button(form, text="ثبت خدمت", command=self.add_service).pack(side="right", padx=3)
        ttk.Button(form, text="ویرایش", command=self.update_service).pack(side="right", padx=3)
        ttk.Button(form, text="حذف", command=self.delete_service).pack(side="right", padx=3)
        ttk.Button(form, text="پاک‌کردن فرم", command=self.clear_service).pack(side="right", padx=3)
        self.service_tree = self._make_tree(
            self.service_tab, ("id", "name", "price", "duration"),
            ("شناسه", "نام خدمت", "قیمت (تومان)", "مدت (دقیقه)"),
            {"id": 80, "name": 300, "price": 180, "duration": 160},
        )
        self.service_tree.bind("<<TreeviewSelect>>", self.service_selected)

    def service_selected(self, _event=None) -> None:
        selected = self.service_tree.selection()
        if selected:
            values = self.service_tree.item(selected[0], "values")
            self.s_name.set(values[1])
            self.s_price.set(values[2])
            self.s_duration.set(values[3])

    def add_service(self) -> None:
        try:
            self.service.add_service(self.s_name.get(), self.s_price.get(), self.s_duration.get())
            self.clear_service()
            self.refresh_all()
            messagebox.showinfo("ثبت شد", "خدمت با موفقیت ثبت شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error("نام این خدمت قبلاً ثبت شده است." if isinstance(exc, sqlite3.IntegrityError) else exc)

    def update_service(self) -> None:
        service_id = self._selected_id(self.service_tree)
        if service_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک خدمت را انتخاب کنید.", parent=self)
        try:
            self.service.update_service(service_id, self.s_name.get(), self.s_price.get(), self.s_duration.get())
            self.refresh_all()
            messagebox.showinfo("ویرایش شد", "اطلاعات خدمت به‌روزرسانی شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error("نام این خدمت برای خدمت دیگری استفاده شده است." if isinstance(exc, sqlite3.IntegrityError) else exc)

    def delete_service(self) -> None:
        service_id = self._selected_id(self.service_tree)
        if service_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک خدمت را انتخاب کنید.", parent=self)
        if not messagebox.askyesno("تأیید حذف", "خدمت انتخاب‌شده حذف شود؟", parent=self):
            return
        try:
            self.service.delete_service(service_id)
            self.clear_service()
            self.refresh_all()
        except sqlite3.IntegrityError:
            self._show_error("برای این خدمت نوبت ثبت شده است؛ حذف آن مجاز نیست.")
        except ValueError as exc:
            self._show_error(exc)

    def clear_service(self) -> None:
        self.s_name.set("")
        self.s_price.set("")
        self.s_duration.set("30")
        self.service_tree.selection_remove(self.service_tree.selection())

    def refresh_services(self) -> None:
        self._clear_tree(self.service_tree)
        for row in self.repo.services():
            self.service_tree.insert("", "end", values=(row["id"], row["name"], self._format_money(row["price"]), row["duration"]))

    # فرم نوبت‌ها ----------------------------------------------------------
    def _build_appointment_tab(self) -> None:
        form = ttk.LabelFrame(self.appointment_tab, text="ثبت یا ویرایش نوبت", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.a_customer = tk.StringVar()
        self.a_service = tk.StringVar()
        self.a_time = tk.StringVar(value=datetime.now().replace(second=0, microsecond=0).strftime(DATETIME_FORMAT))
        self.a_notes = tk.StringVar()
        self.a_status = tk.StringVar(value="رزرو")

        ttk.Label(form, text="مشتری:").pack(side="right", padx=(8, 3))
        self.customer_combo = ttk.Combobox(form, textvariable=self.a_customer, state="readonly", width=25)
        self.customer_combo.pack(side="right", padx=3)
        ttk.Label(form, text="خدمت:").pack(side="right", padx=(8, 3))
        self.service_combo = ttk.Combobox(form, textvariable=self.a_service, state="readonly", width=23)
        self.service_combo.pack(side="right", padx=3)
        self._form_entry(form, "زمان (YYYY-MM-DD HH:MM):", self.a_time, 19)
        self._form_entry(form, "یادداشت:", self.a_notes, 17)
        ttk.Button(form, text="ثبت نوبت جدید", command=self.add_appointment).pack(side="right", padx=3)
        ttk.Button(form, text="ذخیره ویرایش", command=self.update_appointment).pack(side="right", padx=3)
        ttk.Button(form, text="پاک‌کردن فرم", command=self.clear_appointment).pack(side="right", padx=3)

        status_bar = ttk.Frame(self.appointment_tab)
        status_bar.pack(fill="x", padx=10)
        ttk.Label(status_bar, text="وضعیت نوبت انتخاب‌شده:").pack(side="right", padx=4)
        self.status_combo = ttk.Combobox(status_bar, textvariable=self.a_status, values=APPOINTMENT_STATUSES, state="readonly", width=15)
        self.status_combo.pack(side="right", padx=4)
        ttk.Button(status_bar, text="ثبت تغییر وضعیت", command=self.change_appointment_status).pack(side="right", padx=4)
        ttk.Label(status_bar, text="برای ویرایش، ابتدا ردیف نوبت را انتخاب کنید.", foreground="#555").pack(side="left", padx=4)

        self.appointment_tree = self._make_tree(
            self.appointment_tab,
            ("id", "customer", "service", "time", "status", "price", "duration", "paid", "balance"),
            ("شناسه", "مشتری", "خدمت", "زمان", "وضعیت", "هزینه", "مدت", "پرداختی", "مانده"),
            {"id": 60, "customer": 130, "service": 130, "time": 145, "status": 90,
             "price": 110, "duration": 70, "paid": 100, "balance": 100},
        )
        self.appointment_tree.bind("<<TreeviewSelect>>", self.appointment_selected)

    def appointment_selected(self, _event=None) -> None:
        selected = self.appointment_tree.selection()
        if not selected:
            return
        appointment_id = int(self.appointment_tree.item(selected[0], "values")[0])
        row = self.repo.one("SELECT * FROM appointments WHERE id=?", (appointment_id,))
        if row is None:
            return
        self.a_customer.set(self.customer_labels_by_id.get(int(row["customer_id"]), ""))
        self.a_service.set(self.service_labels_by_id.get(int(row["service_id"]), ""))
        self.a_time.set(row["start_time"])
        self.a_notes.set(row["notes"])
        self.a_status.set(row["status"] if row["status"] in APPOINTMENT_STATUSES else "رزرو")

    def _appointment_form_ids(self) -> tuple[int, int]:
        customer_id = self.customer_map.get(self.a_customer.get())
        service_id = self.service_map.get(self.a_service.get())
        if customer_id is None:
            raise ValueError("یک مشتری معتبر انتخاب کنید.")
        if service_id is None:
            raise ValueError("یک خدمت معتبر انتخاب کنید.")
        return customer_id, service_id

    def add_appointment(self) -> None:
        try:
            customer_id, service_id = self._appointment_form_ids()
            self.service.add_appointment(customer_id, service_id, self.a_time.get(), self.a_notes.get())
            self.refresh_all()
            self.clear_appointment()
            messagebox.showinfo("ثبت شد", "نوبت با موفقیت ثبت شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error(exc)

    def update_appointment(self) -> None:
        appointment_id = self._selected_id(self.appointment_tree)
        if appointment_id is None:
            return messagebox.showwarning("توجه", "ابتدا نوبت موردنظر را از جدول انتخاب کنید.", parent=self)
        try:
            customer_id, service_id = self._appointment_form_ids()
            self.service.update_appointment(appointment_id, customer_id, service_id, self.a_time.get(), self.a_notes.get())
            self.refresh_all()
            messagebox.showinfo("ویرایش شد", "اطلاعات نوبت به‌روزرسانی شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error(exc)

    def change_appointment_status(self) -> None:
        appointment_id = self._selected_id(self.appointment_tree)
        if appointment_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک نوبت را انتخاب کنید.", parent=self)
        try:
            self.service.change_appointment_status(appointment_id, self.a_status.get())
            self.refresh_all()
            messagebox.showinfo("ثبت شد", "وضعیت نوبت تغییر کرد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error(exc)

    def clear_appointment(self) -> None:
        self.a_customer.set("")
        self.a_service.set("")
        self.a_time.set(datetime.now().replace(second=0, microsecond=0).strftime(DATETIME_FORMAT))
        self.a_notes.set("")
        self.a_status.set("رزرو")
        self.appointment_tree.selection_remove(self.appointment_tree.selection())

    def refresh_appointments(self) -> None:
        self._clear_tree(self.appointment_tree)
        for row in self.repo.appointments():
            paid = int(row["paid"])
            price = int(row["service_price"])
            balance = price - paid
            self.appointment_tree.insert(
                "", "end",
                values=(row["id"], row["customer_name"], row["service_name"], row["start_time"],
                        row["status"], self._format_money(price), row["service_duration_minutes"],
                        self._format_money(paid), self._format_money(balance)),
            )

    # فرم پرداخت‌ها --------------------------------------------------------
    def _build_payment_tab(self) -> None:
        form = ttk.LabelFrame(self.payment_tab, text="ثبت یا ویرایش پرداخت", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.p_appointment = tk.StringVar()
        self.p_amount = tk.StringVar()
        self.p_note = tk.StringVar()
        ttk.Label(form, text="نوبت:").pack(side="right", padx=(8, 3))
        self.payment_combo = ttk.Combobox(form, textvariable=self.p_appointment, state="readonly", width=48)
        self.payment_combo.pack(side="right", padx=3)
        self._form_entry(form, "مبلغ (تومان):", self.p_amount, 15)
        self._form_entry(form, "یادداشت:", self.p_note, 18)
        ttk.Button(form, text="ثبت پرداخت جدید", command=self.add_payment).pack(side="right", padx=3)
        ttk.Button(form, text="ویرایش پرداخت", command=self.update_payment).pack(side="right", padx=3)
        ttk.Button(form, text="حذف پرداخت", command=self.delete_payment).pack(side="right", padx=3)
        ttk.Button(form, text="پاک‌کردن فرم", command=self.clear_payment).pack(side="right", padx=3)
        self.payment_tree = self._make_tree(
            self.payment_tab, ("id", "appointment", "amount", "paid_at", "note"),
            ("شناسه پرداخت", "نوبت", "مبلغ (تومان)", "تاریخ پرداخت", "یادداشت"),
            {"id": 90, "appointment": 400, "amount": 150, "paid_at": 160, "note": 250},
        )
        self.payment_tree.bind("<<TreeviewSelect>>", self.payment_selected)

    def payment_selected(self, _event=None) -> None:
        selected = self.payment_tree.selection()
        if not selected:
            return
        values = self.payment_tree.item(selected[0], "values")
        payment_id = int(values[0])
        row = self.repo.one("SELECT * FROM payments WHERE id=?", (payment_id,))
        if row is None:
            return
        self.p_appointment.set(self.appointment_labels_by_id.get(int(row["appointment_id"]), ""))
        self.p_amount.set(str(row["amount"]))
        self.p_note.set(row["note"])

    def add_payment(self) -> None:
        try:
            appointment_id = self.appointment_map.get(self.p_appointment.get())
            if appointment_id is None:
                raise ValueError("یک نوبت معتبر انتخاب کنید.")
            self.service.add_payment(appointment_id, self.p_amount.get(), self.p_note.get())
            self.clear_payment()
            self.refresh_all()
            messagebox.showinfo("ثبت شد", "پرداخت با موفقیت ثبت شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error(exc)

    def update_payment(self) -> None:
        payment_id = self._selected_id(self.payment_tree)
        if payment_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک پرداخت را از جدول انتخاب کنید.", parent=self)
        try:
            appointment_id = self.appointment_map.get(self.p_appointment.get())
            if appointment_id is None:
                raise ValueError("یک نوبت معتبر انتخاب کنید.")
            self.service.update_payment(payment_id, appointment_id, self.p_amount.get(), self.p_note.get())
            self.refresh_all()
            messagebox.showinfo("ویرایش شد", "پرداخت به‌روزرسانی شد.", parent=self)
        except (ValueError, sqlite3.IntegrityError) as exc:
            self._show_error(exc)

    def delete_payment(self) -> None:
        payment_id = self._selected_id(self.payment_tree)
        if payment_id is None:
            return messagebox.showwarning("توجه", "ابتدا یک پرداخت را انتخاب کنید.", parent=self)
        if not messagebox.askyesno("تأیید حذف", "پرداخت انتخاب‌شده حذف شود؟", parent=self):
            return
        try:
            self.service.delete_payment(payment_id)
            self.clear_payment()
            self.refresh_all()
        except ValueError as exc:
            self._show_error(exc)

    def clear_payment(self) -> None:
        self.p_appointment.set("")
        self.p_amount.set("")
        self.p_note.set("")
        self.payment_tree.selection_remove(self.payment_tree.selection())

    def refresh_payments(self) -> None:
        self._clear_tree(self.payment_tree)
        for row in self.repo.payments():
            label = f"#{row['appointment_id']} | {row['customer_name']} | {row['service_name']} | {row['start_time']}"
            self.payment_tree.insert(
                "", "end",
                values=(row["id"], label, self._format_money(row["amount"]), row["paid_at"], row["note"]),
            )

    # گزارش‌ها -------------------------------------------------------------
    def _build_report_tab(self) -> None:
        form = ttk.LabelFrame(self.report_tab, text="تهیه گزارش", padding=8)
        form.pack(fill="x", padx=8, pady=8)
        self.report_date = tk.StringVar(value=date.today().isoformat())
        self.report_month = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self._form_entry(form, "روز (YYYY-MM-DD):", self.report_date, 15)
        ttk.Button(form, text="گزارش روزانه", command=self.daily_report).pack(side="right", padx=4)
        self._form_entry(form, "ماه (YYYY-MM):", self.report_month, 12)
        ttk.Button(form, text="گزارش ماهانه", command=self.monthly_report).pack(side="right", padx=4)
        ttk.Button(form, text="پاک‌کردن گزارش", command=lambda: self.report_text.delete("1.0", "end")).pack(side="right", padx=4)
        self.report_text = tk.Text(self.report_tab, height=20, wrap="word", font=("Tahoma", 10), padx=10, pady=10)
        self.report_text.pack(fill="both", expand=True, padx=8, pady=8)

    def daily_report(self) -> None:
        try:
            report = self.reports.daily(self.report_date.get())
            self._show_report(
                f"گزارش روزانه کلینیک\nتاریخ: {report['period']}\n\n"
                f"تعداد نوبت‌های غیرلغوشده: {report['appointments']}\n"
                f"تعداد نوبت‌های لغوشده: {report['cancelled']}\n"
                f"مجموع دریافتی ثبت‌شده در این روز: {self._format_money(report['income'])} تومان\n\n"
                "توجه: دریافتی بر اساس تاریخ ثبت پرداخت محاسبه می‌شود، نه تاریخ انجام خدمت."
            )
        except ValueError as exc:
            self._show_error(exc)

    def monthly_report(self) -> None:
        try:
            report = self.reports.monthly(self.report_month.get())
            self._show_report(
                f"گزارش ماهانه کلینیک\nماه: {report['period']}\n\n"
                f"تعداد نوبت‌های غیرلغوشده: {report['appointments']}\n"
                f"تعداد نوبت‌های لغوشده: {report['cancelled']}\n"
                f"مجموع دریافتی ثبت‌شده در این ماه: {self._format_money(report['income'])} تومان\n\n"
                "توجه: این گزارش درآمد/دریافتی ناخالص ثبت‌شده را نشان می‌دهد و محاسبه سود خالص نیست."
            )
        except ValueError as exc:
            self._show_error(exc)

    def _show_report(self, text: str) -> None:
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)

    # تازه‌سازی کلی --------------------------------------------------------
    def refresh_combos(self) -> None:
        customers = self.repo.customers()
        services = self.repo.services()
        self.customer_map = {f"{r['id']} - {r['name']} ({r['phone']})": int(r["id"]) for r in customers}
        self.service_map = {f"{r['id']} - {r['name']} ({self._format_money(r['price'])} تومان)": int(r["id"]) for r in services}
        self.customer_labels_by_id = {int(r["id"]): label for label, r in zip(self.customer_map, customers)}
        self.service_labels_by_id = {int(r["id"]): label for label, r in zip(self.service_map, services)}
        self.customer_combo["values"] = list(self.customer_map)
        self.service_combo["values"] = list(self.service_map)

        appointments = self.repo.all(
            """SELECT a.id, a.start_time, a.status, c.name AS customer_name, s.name AS service_name
               FROM appointments a JOIN customers c ON c.id=a.customer_id
               JOIN services s ON s.id=a.service_id
               WHERE a.status<>'لغو شده' ORDER BY a.start_time DESC"""
        )
        self.appointment_map = {}
        self.appointment_labels_by_id = {}
        for row in appointments:
            label = f"#{row['id']} - {row['customer_name']} / {row['service_name']} - {row['start_time']}"
            self.appointment_map[label] = int(row["id"])
            self.appointment_labels_by_id[int(row["id"])] = label
        self.payment_combo["values"] = list(self.appointment_map)

    def refresh_dashboard(self) -> None:
        stats = self.reports.dashboard()
        self.dashboard_vars["customers"].set(str(stats["customers"]))
        self.dashboard_vars["today_appointments"].set(str(stats["today_appointments"]))
        self.dashboard_vars["today_income"].set(f"{self._format_money(stats['today_income'])} تومان")
        self.dashboard_vars["month_income"].set(f"{self._format_money(stats['month_income'])} تومان")

    def refresh_all(self) -> None:
        self.refresh_customers()
        self.refresh_services()
        self.refresh_combos()
        self.refresh_appointments()
        self.refresh_payments()
        self.refresh_dashboard()

    def on_close(self) -> None:
        try:
            self.database.close()
        finally:
            self.destroy()
