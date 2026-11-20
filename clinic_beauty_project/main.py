# -*- coding: utf-8 -*-
"""نقطه شروع برنامه. اجرا: python main.py"""
import sqlite3
import tkinter as tk
from tkinter import messagebox
from src.gui import ClinicApp

if __name__ == "__main__":
    try:
        app = ClinicApp()
        app.mainloop()
    except sqlite3.Error as exc:
        messagebox.showerror("خطای پایگاه داده", str(exc))
        raise
