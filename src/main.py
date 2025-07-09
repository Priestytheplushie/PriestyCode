import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog

try:
    from priesty_ide import PriestyCode
except Exception:
    from src.priesty_ide import PriestyCode

ide = PriestyCode()
ide.run()
