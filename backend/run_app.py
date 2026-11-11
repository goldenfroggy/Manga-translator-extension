#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launcher backend cho Python runtime local (backend\\runtime).

Python embeddable chạy isolated mode (python311._pth) nên `python -m app`
KHÔNG thấy package `app` dù cwd đúng — launcher tự thêm backend/ vào sys.path.
Chạy: backend\\runtime\\python.exe backend\\run_app.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from app.__main__ import main

if __name__ == "__main__":
    main()
