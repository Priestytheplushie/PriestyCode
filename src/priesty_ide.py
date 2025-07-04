# priesty_ide.py

import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import subprocess
import sys
import tempfile
from PIL import Image, ImageTk
import threading
import queue
import time
from typing import cast, Union
import re
import shutil

from code_editor import CodeEditor
from console_ui import ConsoleUi
from terminal import Terminal
from file_explorer import FileExplorer

current_dir = os.path.dirname(__file__)
initial_project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))
ICON_PATH = os.path.join(initial_project_root_dir, 'assets', 'icons')

PROCESS_END_SIGNAL = "<<ProcessEnd>>"
PROCESS_ERROR_SIGNAL = "<<ProcessError>>"

class PriestyCode(tk.Tk):
    BINARY_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.exe', '.dll', '.so',
        '.zip', '.rar', '.7z', '.tar', '.gz', '.pdf', '.doc', '.docx', '.xls',
        '.xlsx', '.ppt', '.pptx', '.o', '.a', '.obj', '.lib', '.mp3', '.mp4',
        '.avi', '.mov', '.wav', '.flac', '.pyc'
    }

    def __init__(self):
        super().__init__()
        self.title("PriestyCode v1.0.0")
        self.geometry("1300x850")
        self.config(bg="#2B2B2B")

        self.icon_size = 16
        self.process: subprocess.Popen | None = None
        # FIX 1: Correct queue type hint
        self.output_queue: queue.Queue[tuple[str, Union[str, int, None]]] = queue.Queue()
        self.stdin_queue: queue.Queue[str] = queue.Queue()
        self.stderr_buffer = ""
        self.stdout_buffer = ""
        self.open_files: list[str] = []
        self.tab_widgets: list[tk.Frame] = []
        self.editor_widgets: list[tk.Frame] = []
        self.current_tab_index = -1
        self.current_open_file: str | None = None
        self.active_editor: CodeEditor | None = None
        self.is_running = False
        self.workspace_root_dir = initial_project_root_dir
        self.python_executable = sys.executable
        self.find_replace_dialog: 'FindReplaceDialog' | None = None #type: ignore
        self.venv_warning_shown = False
        
        self.file_type_icon_label: tk.Label
        self.file_name_label: tk.Label
        self.terminal_console: Terminal
        self.error_console: ConsoleUi
        self.file_explorer: FileExplorer

        self.autocomplete_enabled = tk.BooleanVar(value=True)
        self.proactive_errors_enabled = tk.BooleanVar(value=True)
        self.highlight_handled_exceptions = tk.BooleanVar(value=True)

        self._load_icons()
        self._configure_styles()
        self._setup_layout()
        self._create_top_toolbar()
        self._create_menu_bar()
        self._create_main_content_area()
        self._bind_shortcuts()
        
        self.after(50, self._process_output_queue)
        self.after(200, self._check_virtual_env)
        self.after(500, self._open_sandbox_if_empty)
    
    def _load_icons(self):
        """Loads and resizes icons used throughout the IDE."""
        self.window_icon = self._load_and_resize_icon('priesty.png', is_photo_image=True)
        if isinstance(self.window_icon, tk.PhotoImage):
            self.iconphoto(True, self.window_icon)
        
        ico_path = os.path.join(ICON_PATH, 'Priesty.ico')
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception as e:
                print(f"Warning: Could not set .ico file: {e}")

        self.priesty_icon = self._load_and_resize_icon('priesty.png', size=24)
        self.folder_icon = self._load_and_resize_icon('folder_icon.png')
        self.git_icon = self._load_and_resize_icon('git_icon.png')
        self.run_icon = self._load_and_resize_icon('run.png', size=24)
        self.pause_icon = self._load_and_resize_icon('pause.png', size=24)
        self.unknown_file_icon = self._load_and_resize_icon('unknwon.png')
        self.clear_icon = self._load_and_resize_icon('clear_icon.png', size=24)
        self.python_logo_icon = self._load_and_resize_icon('python_logo.png')
        self.close_icon = self._load_and_resize_icon('close_icon.png', size=12)
        self.txt_icon = self._load_and_resize_icon('txt_icon.png')

        # Icons for autocomplete manager
        self.snippet_icon = self._load_and_resize_icon('snippet_icon.png')
        self.keyword_icon = self._load_and_resize_icon('keyword_icon.png')
        self.function_icon = self._load_and_resize_icon('function_icon.png')
        self.variable_icon = self._load_and_resize_icon('variable_icon.png')

    def _load_and_resize_icon(self, icon_name, size=None, is_photo_image=False):
        """Helper to load, resize, and return a PhotoImage from an icon file."""
        try:
            path = os.path.join(ICON_PATH, icon_name)
            if not os.path.exists(path): return None
            if is_photo_image: return tk.PhotoImage(file=path)
            
            pil_image = Image.open(path)
            if size is None: size = self.icon_size
            
            aspect_ratio = pil_image.width / pil_image.height
            resized_image = pil_image.resize((int(aspect_ratio * size), size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized_image)
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            return None

    def _configure_styles(self):
        """Configures the ttk styles for various widgets."""
        self.style = ttk.Style(self)
        self.style.theme_use("default") # Use default theme as a base
        self.style.configure("TPanedwindow", background="#2B2B2B")
        self.style.configure("TNotebook", background="#2B2B2B", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#3C3C3C", foreground="white", padding=[10, 5], font=("Segoe UI", 10), borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", "#2B2B2B"), ("active", "#555555")])

    def _setup_layout(self):
        """Sets up the main grid layout for the IDE window."""
        self.grid_rowconfigure(1, weight=1) # Main content area expands vertically
        self.grid_columnconfigure(0, weight=1) # Main content area expands horizontally

    def _create_top_toolbar(self):
        """Creates the top toolbar with IDE name, file info, and run/clear buttons."""
        self.top_toolbar_frame = tk.Frame(self, bg="#3C3C3C", height=30)
        self.top_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.top_toolbar_frame.grid_propagate(False) # Prevent frame from resizing to fit contents

        if self.priesty_icon:
            tk.Label(self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C").pack(side="left", padx=5)
        
        self.file_type_icon_label = tk.Label(self.top_toolbar_frame, bg="#3C3C3C")
        self.file_type_icon_label.pack(side="left", padx=(5,0))
        self.file_name_label = tk.Label(self.top_toolbar_frame, text="No File Open", fg="white", bg="#3C3C3C", font=("Segoe UI", 10, "bold"))
        self.file_name_label.pack(side="left", padx=(2, 10))

        btn_kwargs = {"bg": "#3C3C3C", "bd": 0, "activebackground": "#555555", "highlightthickness": 0}
        self.clear_console_button = tk.Button(self.top_toolbar_frame, command=self._clear_console, **btn_kwargs)
        if self.clear_icon: self.clear_console_button.config(image=self.clear_icon)
        else: self.clear_console_button.config(text="Clear", fg="white")
        self.clear_console_button.pack(side="right", padx=5)

        self.run_stop_button = tk.Button(self.top_toolbar_frame, command=self._run_code, **btn_kwargs)
        if self.run_icon: self.run_stop_button.config(image=self.run_icon)
        else: self.run_stop_button.config(text="Run", fg="white")
        self.run_stop_button.pack(side="right", padx=5)

    def _create_menu_bar(self):
        menubar = tk.Menu(self, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white", relief="flat", borderwidth=0)
        self.config(menu=menubar)
        menu_kwargs = {"tearoff": 0, "bg": "#3C3C3C", "fg": "white", "activebackground": "#555555", "activeforeground": "white"}
        
        file_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="File", menu=file_menu)
        
        new_menu = tk.Menu(file_menu, **menu_kwargs)
        file_menu.add_cascade(label="New...", menu=new_menu)
        new_menu.add_command(label="Python File", command=lambda: self._new_file())
        new_menu.add_command(label="Text File", command=lambda: self._new_file(extension=".txt"))

        file_menu.add_command(label="Open File...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Folder...", command=self._open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self._save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        edit_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self._handle_undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self._handle_redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        def event_gen(event_name):
            try: self.focus_get().event_generate(event_name) # type: ignore
            except (AttributeError, tk.TclError): pass
        edit_menu.add_command(label="Cut", command=lambda: event_gen("<<Cut>>"), accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=lambda: event_gen("<<Copy>>"), accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=lambda: event_gen("<<Paste>>"), accelerator="Ctrl+V")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find/Replace", command=self._open_find_replace_dialog, accelerator="Ctrl+F")

        refactor_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Refactor", menu=refactor_menu)
        refactor_menu.add_command(label="Move Active File...", command=self._move_active_file)
        refactor_menu.add_command(label="Duplicate Active File...", command=self._duplicate_active_file)

        run_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Current File", command=self._run_code, accelerator="F5")
        run_menu.add_command(label="Stop Execution", command=self._stop_code, accelerator="Ctrl+F2")
        
        workspace_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Workspace", menu=workspace_menu)
        workspace_menu.add_command(label="Refresh Explorer", command=lambda: self.file_explorer.populate_tree())
        workspace_menu.add_command(label="Create Virtual Environment", command=self._create_virtual_env)

        options_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Enable Code Completion", variable=self.autocomplete_enabled, command=self._toggle_autocomplete)
        options_menu.add_checkbutton(label="Enable Proactive Error Checking", variable=self.proactive_errors_enabled, command=self._toggle_proactive_errors)
        options_menu.add_checkbutton(label="Highlight Handled Exceptions", variable=self.highlight_handled_exceptions)

        help_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _toggle_autocomplete(self):
        if self.active_editor: self.active_editor.autocomplete_active = self.autocomplete_enabled.get()

    def _toggle_proactive_errors(self):
        if self.active_editor: self.active_editor.set_proactive_error_checking(self.proactive_errors_enabled.get())

    def _create_main_content_area(self):
        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        left_pane = ttk.Frame(self.main_paned_window)
        self.main_paned_window.add(left_pane, weight=1)
        self.file_explorer = FileExplorer(left_pane, self, self.workspace_root_dir, self._open_file_from_path, 
                                          folder_icon=self.folder_icon, python_icon=self.python_logo_icon, 
                                          git_icon=self.git_icon, unknown_icon=self.unknown_file_icon,
                                          txt_icon=self.txt_icon)
        self.file_explorer.pack(fill="both", expand=True)

        self.right_pane = ttk.PanedWindow(self.main_paned_window, orient=tk.VERTICAL)
        self.main_paned_window.add(self.right_pane, weight=4)

        editor_area_frame = tk.Frame(self.right_pane, bg="#2B2B2B")
        self.right_pane.add(editor_area_frame, weight=3)
        editor_area_frame.grid_rowconfigure(1, weight=1); editor_area_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_bar_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.tab_bar_frame.grid(row=0, column=0, sticky="ew")
        self.editor_content_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.editor_content_frame.grid(row=1, column=0, sticky="nsew")

        self.output_notebook = ttk.Notebook(self.right_pane)
        self.right_pane.add(self.output_notebook, weight=1)
        
        self.terminal_console = Terminal(self.output_notebook, stdin_queue=self.stdin_queue, 
                                         cwd=self.workspace_root_dir, python_executable=self.python_executable)
        self.output_notebook.add(self.terminal_console, text="Terminal")

        self.error_console = ConsoleUi(self.output_notebook)
        self.output_notebook.add(self.error_console, text="Errors")
        self.output_notebook.bind("<<NotebookTabChanged>>", self._on_output_tab_change)

    def _on_output_tab_change(self, event=None):
        try:
            tab_text = self.output_notebook.tab(self.output_notebook.select(), "text")
            if tab_text == "Terminal": self.terminal_console.text.after(50, self.terminal_console.text.focus_set)
            elif tab_text == "Errors" and self.error_console: self.error_console.output_console.focus_set()
        except tk.TclError: pass

    def _open_sandbox_if_empty(self):
        if not self.open_files:
            sandbox_path = os.path.join(self.workspace_root_dir, "sandbox.py")
            if not os.path.exists(sandbox_path):
                content = "# sandbox.py\nimport traceback\n\nprint('--- Welcome to the Sandbox ---')\n"
                try:
                    with open(sandbox_path, "w", encoding="utf-8") as f: f.write(content)
                    self.file_explorer.populate_tree()
                except Exception as e:
                    messagebox.showerror("Sandbox Creation Failed", f"Could not create sandbox.py: {e}")
                    return
            self._open_file_from_path(sandbox_path)

    def _check_virtual_env(self):
        found_venv = False
        for venv_name in ('.venv', 'venv'): 
            path = os.path.join(self.workspace_root_dir, venv_name)
            if os.path.isdir(path):
                script_dir = 'Scripts' if sys.platform == 'win32' else 'bin'
                potential_path = os.path.join(path, script_dir, 'python.exe' if sys.platform == 'win32' else 'python')
                if os.path.exists(potential_path):
                    self.python_executable = os.path.abspath(potential_path)
                    found_venv = True
                    break 
        
        if not found_venv:
            self.python_executable = sys.executable
            if not self.venv_warning_shown:
                self.venv_warning_shown = True
                if messagebox.askyesno("Virtual Environment Recommended", "No virtual environment was found. It is highly recommended to use one.\n\nWould you like to create one now?"):
                    self._create_virtual_env()
        
        if hasattr(self, 'terminal_console'):
            self.terminal_console.set_python_executable(self.python_executable)
            self.terminal_console.clear(); self.terminal_console.show_prompt()

    def _create_virtual_env(self):
        self.terminal_console.write("Creating virtual environment 'venv'... This may take a moment.\n")
        self.output_notebook.select(self.terminal_console)
        self.update_idletasks()
        venv_dir = os.path.join(self.workspace_root_dir, "venv")
        if os.path.exists(venv_dir):
            messagebox.showwarning("Exists", "A 'venv' folder already exists.")
            return

        def create():
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True, capture_output=True, text=True, cwd=self.workspace_root_dir)
                self.after(0, self._check_virtual_env); self.after(0, self.file_explorer.populate_tree)
            except Exception as e: self.terminal_console.write(f"Failed to create venv: {e}\n", "stderr_tag")
            finally: self.after(0, self.terminal_console.show_prompt)

        threading.Thread(target=create, daemon=True).start()

    def _new_file(self, extension=".py"):
        self._add_new_tab(extension=extension)

    def _open_file(self, event=None):
        file_path = filedialog.askopenfilename(initialdir=self.workspace_root_dir, filetypes=[("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*")])
        if file_path: self._open_file_from_path(file_path)

    def _open_folder(self):
        new_path = filedialog.askdirectory(title="Select Workspace Folder", initialdir=self.workspace_root_dir)
        if not new_path or not os.path.isdir(new_path): return
        while self.open_files:
            if not self._close_tab(0, force_ask=True): return
        self.workspace_root_dir, self.venv_warning_shown = new_path, False
        self.file_explorer.set_project_root(new_path); self.terminal_console.set_cwd(new_path)
        self._check_virtual_env()
        self.title(f"PriestyCode - {os.path.basename(new_path)}")

    def _open_file_from_path(self, file_path):
        _, extension = os.path.splitext(file_path)
        if extension.lower() in self.BINARY_EXTENSIONS:
            messagebox.showerror("Cannot Open File", f"The file '{os.path.basename(file_path)}' appears to be a binary file.")
            return

        if file_path in self.open_files: self._switch_to_tab(self.open_files.index(file_path))
        else: self._add_new_tab(file_path=file_path)

    def _add_new_tab(self, file_path=None, content="", extension=".py"):
        editor_frame = tk.Frame(self.editor_content_frame, bg="#2B2B2B")
        editor = CodeEditor(editor_frame, error_console=self.error_console, autocomplete_icons={'snippet':self.snippet_icon, 'keyword':self.keyword_icon, 'function':self.function_icon, 'variable':self.variable_icon, 'class':self.function_icon})
        editor.pack(fill="both", expand=True)

        if file_path and not file_path.startswith("Untitled-"):
            try:
                with open(file_path, "r", encoding="utf-8") as f: content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}"); editor_frame.destroy(); return
        elif not file_path:
            count = 1; untitled_name = f"Untitled-{count}{extension}"
            while untitled_name in self.open_files: count += 1; untitled_name = f"Untitled-{count}{extension}"
            file_path = untitled_name

        editor.set_file_path(file_path); editor.text_area.insert("1.0", content); editor.text_area.edit_modified(False)
        self.after(50, editor._on_content_changed)

        tab = tk.Frame(self.tab_bar_frame, bg="#3C3C3C"); tab.pack(side="left", fill="y", padx=(0, 1))
        icon, new_index = self._get_icon_for_file(file_path), len(self.open_files)
        icon_label = tk.Label(tab, image=icon, bg="#3C3C3C") if icon else tk.Label(tab, bg="#3C3C3C")
        icon_label.pack(side="left", padx=(5, 2), pady=2)
        text_label = tk.Label(tab, text=os.path.basename(file_path), fg="white", bg="#3C3C3C", font=("Segoe UI", 9)); text_label.pack(side="left", padx=(0, 5), pady=2)
        close_button = tk.Button(tab, text="\u2715", bg="#3C3C3C", fg="white", bd=0, relief="flat", activebackground="#E81123", activeforeground="white", font=("Segoe UI", 8, "bold")); close_button.pack(side="right", padx=(5, 5), pady=2)
        
        tab.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i)); icon_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        text_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i)); close_button.config(command=lambda i=new_index: self._close_tab(i))

        self.open_files.append(file_path); self.editor_widgets.append(editor_frame); self.tab_widgets.append(tab)
        self._switch_to_tab(new_index)

    def _switch_to_tab(self, index: int):
        if not (0 <= index < len(self.tab_widgets)): return
        
        if self.active_editor: self.editor_widgets[self.current_tab_index].pack_forget(); self._set_tab_appearance(self.tab_widgets[self.current_tab_index], active=False)
        
        self.current_tab_index = index; self.current_open_file = self.open_files[index]
        new_editor_frame = self.editor_widgets[index]; new_editor_frame.pack(fill="both", expand=True)
        self.active_editor = cast(CodeEditor, new_editor_frame.winfo_children()[0])

        self._set_tab_appearance(self.tab_widgets[index], active=True)
        self.active_editor.text_area.focus_set(); self._update_file_header(self.current_open_file)

    def _set_tab_appearance(self, tab_widget, active):
        bg = "#2B2B2B" if active else "#3C3C3C"; tab_widget.config(bg=bg)
        for child in tab_widget.winfo_children():
            if isinstance(child, (tk.Label, tk.Frame)): child.config(bg=bg)

    def _close_tab(self, index_to_close, force_ask=False, force_close=False) -> bool:
        if not (0 <= index_to_close < len(self.open_files)): return False
        
        editor_to_close = cast(CodeEditor, self.editor_widgets[index_to_close].winfo_children()[0])
        if not force_close and editor_to_close.text_area.edit_modified():
            response = messagebox.askyesnocancel("Save on Close", f"Save changes to {os.path.basename(self.open_files[index_to_close])}?")
            if response is None: return False
            if response and not self._save_file(index_to_close): return False

        self.tab_widgets.pop(index_to_close).destroy(); self.editor_widgets.pop(index_to_close).destroy(); self.open_files.pop(index_to_close)
        
        for i, tab in enumerate(self.tab_widgets):
            close_button = cast(tk.Button, tab.winfo_children()[-1]); close_button.config(command=lambda new_i=i: self._close_tab(new_i))
            for child in tab.winfo_children()[:-1]: child.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
            tab.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
        
        if not self.open_files: self.active_editor = None; self._update_file_header(None)
        else:
            new_idx = max(0, min(index_to_close, len(self.open_files) - 1))
            self._switch_to_tab(new_idx)
        return True

    def _update_file_header(self, file_path):
        icon = self._get_icon_for_file(file_path)
        if icon: self.file_type_icon_label.config(image=icon)
        self.file_name_label.config(text=os.path.basename(file_path) if file_path else "No File Open")

    def _get_icon_for_file(self, file_path):
        if not file_path: return self.unknown_file_icon
        ext = os.path.splitext(file_path)[1]
        if ext == ".py": return self.python_logo_icon
        if ext == ".txt": return self.txt_icon
        return self.unknown_file_icon

    def _save_file(self, event=None, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        file_path = self.open_files[idx]
        if file_path.startswith("Untitled-"): return self._save_file_as(index=idx)
        try:
            with open(file_path, "w", encoding="utf-8") as f: f.write(cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0]).text_area.get("1.0", "end-1c"))
            cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0]).text_area.edit_modified(False)
            return True
        except Exception as e: messagebox.showerror("Save Error", f"Failed to save: {e}"); return False

    def _save_file_as(self, event=None, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        new_path = filedialog.asksaveasfilename(initialdir=self.workspace_root_dir, defaultextension=".py", filetypes=[("Python", "*.py")])
        if not new_path: return False
        try:
            with open(new_path, "w", encoding="utf-8") as f: f.write(cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0]).text_area.get("1.0", "end-1c"))
            self.handle_file_rename(self.open_files[idx], new_path); self.file_explorer.populate_tree()
            return True
        except Exception as e: messagebox.showerror("Save Error", f"Failed to save: {e}"); return False

    def _run_code(self, event=None):
        if self.is_running: self._stop_code(); return
        if not self.active_editor or not self.current_open_file: messagebox.showerror("No File", "Please open a file to run."); return
        if self.current_open_file.startswith("Untitled-") or self.active_editor.text_area.edit_modified():
            if not self._save_file(): messagebox.showwarning("Run Cancelled", "File must be saved before running."); return

        self.active_editor.clear_error_highlight(); self.terminal_console.clear(); self.error_console.clear()
        self.stderr_buffer, self.stdout_buffer, self.is_running = "", "", True
        self._update_run_stop_button_state(); self.terminal_console.set_interactive_mode(True)
        self.output_notebook.select(self.terminal_console); self.terminal_console.text.focus_set()
        threading.Thread(target=self._execute_in_thread, daemon=True).start()

    def _start_process_and_threads(self, executable_path):
        if not self.current_open_file: self.output_queue.put((PROCESS_ERROR_SIGNAL, "No file to run.")); return
        env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"; env["PYTHONUTF8"] = "1"
        try:
            self.process = subprocess.Popen([executable_path, self.current_open_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, cwd=os.path.dirname(self.current_open_file), creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0, encoding='utf-8', errors='replace', bufsize=1, env=env)
            threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True).start()
            threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True).start()
            threading.Thread(target=self._write_to_stdin, daemon=True).start()
            threading.Thread(target=self._monitor_process, daemon=True).start()
        except Exception as e: self.output_queue.put((PROCESS_ERROR_SIGNAL, f"Failed to start process: {e}"))

    def _monitor_process(self):
        if self.process: self.output_queue.put((PROCESS_END_SIGNAL, self.process.wait()))

    def _execute_in_thread(self):
        try: self._start_process_and_threads(self.python_executable)
        except Exception as e: self.output_queue.put((PROCESS_ERROR_SIGNAL, str(e)))
    
    def _read_stream_to_queue(self, stream, tag):
        try:
            if stream:
                for char in iter(lambda: stream.read(1), ''): self.output_queue.put((char, tag))
        finally:
            if stream: stream.close()

    def _write_to_stdin(self):
        while self.process and self.process.poll() is None:
            try:
                if self.process.stdin: self.process.stdin.write(self.stdin_queue.get(timeout=0.5)); self.process.stdin.flush()
            except queue.Empty: continue
            except (IOError, ValueError): break

    def _stop_code(self, event=None):
        if not self.process or self.process.poll() is not None: self.is_running = False; self._update_run_stop_button_state(); return
        self.is_running = False; self.terminal_console.set_interactive_mode(False)
        while not self.stdin_queue.empty():
            try: self.stdin_queue.get_nowait()
            except queue.Empty: break
        try: self.process.terminate(); self.process.wait(timeout=2); self.terminal_console.write("\n--- Process terminated ---\n", ("stderr_tag",))
        except: self.process.kill(); self.terminal_console.write("\n--- Process killed ---\n", ("stderr_tag",))
        self.process = None; self._update_run_stop_button_state(); self.terminal_console.show_prompt() 

    def _update_run_stop_button_state(self):
        if self.is_running: icon, cmd, text = self.pause_icon, self._stop_code, "Stop"
        else: icon, cmd, text = self.run_icon, self._run_code, "Run"
        self.run_stop_button.config(command=cmd)
        # FIX 2: Explicitly check for icon to satisfy type checker
        if icon: self.run_stop_button.config(image=icon)
        else: self.run_stop_button.config(text=text)

    def _open_find_replace_dialog(self, event=None):
        if not self.active_editor: return 
        if self.find_replace_dialog and self.find_replace_dialog.winfo_exists(): self.find_replace_dialog.lift() 
        else: self.find_replace_dialog = FindReplaceDialog(self, self.active_editor) 

    def _show_about(self):
        messagebox.showinfo("About PriestyCode", "PriestyCode v1.0.0\nA simple, extensible IDE.\n\nCreated with Python and Tkinter.")

    def _clear_console(self):
        self.terminal_console.clear(); self.error_console.clear()
        if not self.terminal_console.interactive_mode: self.terminal_console.show_prompt()

    def _process_output_queue(self):
        try:
            while not self.output_queue.empty():
                char, tag = self.output_queue.get_nowait()
                if char == PROCESS_END_SIGNAL:
                    self.is_running = False; self._update_run_stop_button_state(); self.terminal_console.set_interactive_mode(False)
                    if isinstance(tag, int): # Check if tag is the integer return code
                        full_traceback = self.stderr_buffer + self.stdout_buffer
                        if tag != 0 and "Traceback" in self.stderr_buffer: self._handle_error_output(self.stderr_buffer, "Runtime Error", "reactive")
                        elif tag == 0 and "Traceback" in full_traceback and self.highlight_handled_exceptions.get(): self._handle_error_output(full_traceback, "Handled Exception", "handled")
                        elif tag != 0 and self.stderr_buffer.strip(): self.error_console.display_error("Execution Error", self.stderr_buffer.strip()); self.output_notebook.select(self.error_console)
                    self.stderr_buffer, self.stdout_buffer = "", ""
                elif char == PROCESS_ERROR_SIGNAL:
                    self.is_running = False; self._update_run_stop_button_state(); self.terminal_console.set_interactive_mode(False)
                    self.error_console.display_error("Execution Error", str(tag)); self.output_notebook.select(self.error_console)
                else:
                    self.terminal_console.write(char, (str(tag),))
                    if tag == "stderr_tag": self.stderr_buffer += char
                    elif tag == "stdout_tag": self.stdout_buffer += char
        except queue.Empty: pass
        finally: self.after(50, self._process_output_queue)

    def _handle_error_output(self, error_text, default_title, highlight_type):
        full_error_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', error_text).strip()
        traceback_matches = list(re.finditer(r'File "(.*?)", line (\d+)', full_error_text))
        if traceback_matches:
            file_path, line_num = traceback_matches[-1].groups()
            last_line = full_error_text.strip().split('\n')[-1]
            error_title = last_line.split(':')[0] if 'Error' in last_line or 'Exception' in last_line else default_title
            norm_error_path = os.path.normcase(os.path.abspath(file_path))
            for i, open_path in enumerate(self.open_files):
                if open_path and os.path.normcase(os.path.abspath(open_path)) == norm_error_path:
                    editor = cast(CodeEditor, self.editor_widgets[i].winfo_children()[0])
                    highlight_method = getattr(editor, f"highlight_{highlight_type}_error", None)
                    if highlight_method: self.after(0, highlight_method, int(line_num), full_error_text)
                    break
            self.error_console.display_error(error_title, full_error_text); self.output_notebook.select(self.error_console)
        else: self.error_console.display_error(default_title, full_error_text); self.output_notebook.select(self.error_console)

    def run(self): self.protocol("WM_DELETE_WINDOW", self._on_closing); self.mainloop()
        
    def run_file_from_explorer(self, path): self._open_file_from_path(path); self.after(100, self._run_code)

    def handle_file_rename(self, old_path, new_path):
        old_path_norm = os.path.normcase(old_path)
        if os.path.isdir(new_path): # Folder move
            for i, open_file in enumerate(list(self.open_files)):
                if os.path.normcase(open_file).startswith(old_path_norm + os.sep):
                    new_file_path = new_path + open_file[len(old_path):]
                    self.handle_file_rename(open_file, new_file_path)
            return
        if old_path in self.open_files:
            idx = self.open_files.index(old_path)
            self.open_files[idx] = new_path
            editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0]); editor.set_file_path(new_path)
            text_label = cast(tk.Label, self.tab_widgets[idx].winfo_children()[1]); text_label.config(text=os.path.basename(new_path))
            if idx == self.current_tab_index: self._update_file_header(new_path)

    def handle_file_delete(self, path: str):
        path_norm = os.path.normcase(path)
        for open_file in list(self.open_files):
            if os.path.normcase(open_file).startswith(path_norm):
                self._close_tab(self.open_files.index(open_file), force_close=True)

    def _move_active_file(self):
        if not self.current_open_file or not os.path.exists(self.current_open_file): messagebox.showinfo("Move File", "Open a saved file to move it."); return
        self.file_explorer.move_item(self.current_open_file)
        
    def _duplicate_active_file(self):
        if not self.active_editor or not self.current_open_file or not os.path.exists(self.current_open_file): messagebox.showinfo("Duplicate File", "An active, saved file must be open."); return
        base, ext = os.path.splitext(self.current_open_file); new_path_suggestion = f"{base}_copy{ext}"
        new_path = filedialog.asksaveasfilename(title="Duplicate As...", initialfile=os.path.basename(new_path_suggestion), initialdir=os.path.dirname(self.current_open_file), defaultextension=ext, filetypes=[("All files", "*.*")])
        if not new_path: return
        try: shutil.copy(self.current_open_file, new_path); self.file_explorer.populate_tree(); self._open_file_from_path(new_path)
        except Exception as e: messagebox.showerror("Duplicate Failed", f"Could not duplicate file: {e}")

    def _bind_shortcuts(self):
        self.bind_all("<Control-o>", self._open_file)
        self.bind_all("<Control-s>", self._save_file)
        self.bind_all("<Control-S>", self._save_file_as)
        self.bind_all("<Control-f>", self._open_find_replace_dialog)
        self.bind_all("<F5>", self._run_code)
        self.bind_all("<Control-F2>", self._stop_code)
        self.bind_all("<Control-z>", self._handle_undo)
        self.bind_all("<Control-y>", self._handle_redo)
        if sys.platform != "darwin": self.bind_all("<Control-Shift-Z>", self._handle_redo)
            
    def _handle_undo(self, event=None):
        if self.active_editor:
            try: self.active_editor.text_area.edit_undo()
            except tk.TclError: pass
        return "break"
    
    def _handle_redo(self, event=None):
        if self.active_editor:
            try: self.active_editor.text_area.edit_redo()
            except tk.TclError: pass
        return "break"

    def _on_closing(self):
        if self.is_running: self._stop_code() 
        while self.open_files:
            if not self._close_tab(0, force_ask=True): return
        self.destroy()

class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent, editor: CodeEditor):
        super().__init__(parent)
        self.editor = editor
        self.text_area = editor.text_area
        self.title("Find & Replace")
        self.transient(parent)
        self.geometry("400x150")
        self.configure(bg="#3C3C3C")
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)
        
        tk.Label(self, text="Find:", bg="#3C3C3C", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.find_entry = tk.Entry(self, bg="#2B2B2B", fg="white", insertbackground="white")
        self.find_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        tk.Label(self, text="Replace:", bg="#3C3C3C", fg="white").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.replace_entry = tk.Entry(self, bg="#2B2B2B", fg="white", insertbackground="white")
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        button_frame = tk.Frame(self, bg="#3C3C3C")
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        btn_kwargs = {"bg":"#555555", "fg":"white", "bd":1, "relief":"solid", "padx":5, "pady":2}
        tk.Button(button_frame, text="Find Next", command=self.find_next, **btn_kwargs).pack(side="left", padx=5)
        tk.Button(button_frame, text="Replace", command=self.replace, **btn_kwargs).pack(side="left", padx=5)
        tk.Button(button_frame, text="Replace All", command=self.replace_all, **btn_kwargs).pack(side="left", padx=5)
        
        self.grid_columnconfigure(1, weight=1)
        self.find_entry.focus_set()

    def find_next(self):
        find_term = self.find_entry.get()
        if not find_term: return

        start_pos = self.text_area.index(tk.INSERT)
        match_pos = self.text_area.search(find_term, start_pos, stopindex=tk.END)
        
        if not match_pos: # Wrap around search
            match_pos = self.text_area.search(find_term, "1.0", stopindex=tk.END)

        if match_pos:
            end_pos = f"{match_pos}+{len(find_term)}c"
            self.text_area.tag_remove("sel", "1.0", tk.END)
            self.text_area.tag_add("sel", match_pos, end_pos)
            self.text_area.mark_set(tk.INSERT, end_pos)
            self.text_area.see(match_pos)
            self.text_area.focus_set()
        else:
            messagebox.showinfo("Find", f"Could not find '{find_term}'", parent=self)
            
    def replace(self):
        find_term = self.find_entry.get()
        replace_term = self.replace_entry.get()
        
        if not find_term: return
        
        selection = self.text_area.tag_ranges("sel")
        if selection:
            start, end = selection
            # Check if the selected text actually matches the find term
            if self.text_area.get(start, end) == find_term:
                self.text_area.delete(start, end)
                self.text_area.insert(start, replace_term)
        
        self.find_next()

    def replace_all(self):
        find_term = self.find_entry.get()
        replace_term = self.replace_entry.get()
        
        if not find_term: return
        
        content = self.text_area.get("1.0", tk.END)
        new_content = content.replace(find_term, replace_term)
        
        if content != new_content:
            replacements = content.count(find_term)
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", new_content)
            messagebox.showinfo("Replace All", f"Replaced {replacements} occurrence(s).", parent=self)
        else:
            messagebox.showinfo("Replace All", "No occurrences found.", parent=self)
    
    def close_dialog(self):
        # Clean up selection when closing
        self.text_area.tag_remove("sel", "1.0", tk.END)
        self.destroy()  