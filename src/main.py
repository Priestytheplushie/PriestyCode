import tkinter as tk #hello
from tkinter import messagebox, scrolledtext, filedialog

try:
    from priesty_ide import PriestyCode
except Exception:
    from src.priesty_ide import PriestyCode

ide = PriestyCode()
ide.run()
