import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
import os
import subprocess
import sys
from PIL import Image, ImageTk

current_dir = os.path.dirname(__file__)
project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))
ICON_PATH = os.path.join(project_root_dir, 'assets', 'icons')

class PriestyCode(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("PriestyCode v0.1.0")
        self.geometry("1200x800")
        self.config(bg="#2B2B2B")

        try:
            pil_image = Image.open(os.path.join(ICON_PATH, 'priesty.png'))
            new_height = 24
            width, height = pil_image.size
            new_width = int(width * (new_height / height))
            resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.priesty_icon = ImageTk.PhotoImage(resized_image)

            priesty_icon_native = tk.PhotoImage(file=os.path.join(ICON_PATH, 'priesty.png'))
            self.iconphoto(True, priesty_icon_native)

            self.folder_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'folder_icon.png'))
            self.git_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'git_icon.png'))
            self.run_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'run.png'))
            self.unknown_file_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'unknwon.png'))

        except FileNotFoundError as e:
            print(f"Error: One or more icon files not found. {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
        except tk.TclError as e:
            print(f"Warning: Could not load icons. {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
        except Exception as e:
            print(f"Unexpected error loading icons: {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None

        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("DarkMenu.TMenu", background="#3C3C3C", foreground="white")
        self.style.map("DarkMenu.TMenu", background=[('active', '#555555')])

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_top_toolbar()
        self._create_menu_bar()

        self.main_content_frame = tk.Frame(self, bg="#2B2B2B")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew")

    def _create_top_toolbar(self):
        self.top_toolbar_frame = tk.Frame(self, bg="#3C3C3C", height=30)
        self.top_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.top_toolbar_frame.grid_propagate(False)

        self.top_toolbar_frame.grid_columnconfigure(0, weight=0)
        self.top_toolbar_frame.grid_columnconfigure(1, weight=1)
        self.top_toolbar_frame.grid_columnconfigure(2, weight=0)

        if self.priesty_icon:
            self.priesty_icon_label = tk.Label(self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C")
            self.priesty_icon_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.working_dir_path = os.path.abspath(project_root_dir)
        self.path_label = tk.Label(self.top_toolbar_frame, text=self.working_dir_path, bg="#3C3C3C", fg="#A0A0A0", font=("Segoe UI", 9))
        self.path_label.grid(row=0, column=2, padx=10, pady=2, sticky="e")

    def _create_menu_bar(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=lambda: messagebox.showinfo("New File", "New File functionality coming soon!"))
        file_menu.add_command(label="Open File...", command=lambda: messagebox.showinfo("Open File", "Open File functionality coming soon!"))
        file_menu.add_command(label="Save", command=lambda: messagebox.showinfo("Save File", "Save File functionality coming soon!"))
        file_menu.add_command(label="Save As...", command=lambda: messagebox.showinfo("Save As", "Save As functionality coming soon!"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        edit_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Cut", command=lambda: messagebox.showinfo("Edit", "Cut functionality coming soon!"))
        edit_menu.add_command(label="Copy", command=lambda: messagebox.showinfo("Edit", "Copy functionality coming soon!"))
        edit_menu.add_command(label="Paste", command=lambda: messagebox.showinfo("Edit", "Paste functionality coming soon!"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Undo", command=lambda: messagebox.showinfo("Edit", "Undo functionality coming soon!"))
        edit_menu.add_command(label="Redo", command=lambda: messagebox.showinfo("Edit", "Redo functionality coming soon!"))

        view_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Fullscreen", command=lambda: self.attributes('-fullscreen', not self.attributes('-fullscreen')))

        terminal_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Terminal", menu=terminal_menu)
        terminal_menu.add_command(label="New Terminal", command=lambda: messagebox.showinfo("Terminal", "New Terminal functionality coming soon!"))

        help_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About PriestyCode", command=lambda: messagebox.showinfo("About", "PriestyCode v0.1.0\nA simple Python IDE built with Tkinter."))

    def run(self):
        self.mainloop()
