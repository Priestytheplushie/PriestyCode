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
from typing import cast

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
    # ... (the first part of the class is unchanged)
    def __init__(self):
        super().__init__()
        self.title("PriestyCode v1.0.0")
        self.geometry("1300x850")
        self.config(bg="#2B2B2B")

        self.icon_size = 16
        self.process: subprocess.Popen | None = None
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.stdin_queue: queue.Queue[str] = queue.Queue()
        self.stderr_buffer = ""
        self.open_files: list[str] = []
        self.tab_widgets: list[tk.Frame] = []
        self.editor_widgets: list[tk.Frame] = []
        self.current_tab_index = -1
        self.current_open_file: str | None = None
        self.code_editor: CodeEditor | None = None
        self.is_running = False
        self.workspace_root_dir = initial_project_root_dir
        self.python_executable = sys.executable
        self.find_replace_dialog: 'FindReplaceDialog' | None = None
        
        self.file_type_icon_label: tk.Label
        self.file_name_label: tk.Label
        self.terminal_console: Terminal

        self.autocomplete_enabled = tk.BooleanVar(value=True)
        self.proactive_errors_enabled = tk.BooleanVar(value=True)

        self._load_icons()
        self._configure_styles()
        self._setup_layout()
        self._create_top_toolbar()
        self._create_menu_bar()
        self._create_main_content_area()
        self.after(50, self._process_output_queue) # Reduced delay for more responsive output
        self.after(200, self._check_virtual_env)
        self.after(500, self._open_sandbox_if_empty)
    
    # ... (all methods from _load_icons to _save_file_as are unchanged)
    def _load_icons(self):
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

        self.snippet_icon = self._load_and_resize_icon('snippet_icon.png')
        self.keyword_icon = self._load_and_resize_icon('keyword_icon.png')
        self.function_icon = self._load_and_resize_icon('function_icon.png')
        self.variable_icon = self._load_and_resize_icon('variable_icon.png')

    def _load_and_resize_icon(self, icon_name, size=None, is_photo_image=False):
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
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("TPanedwindow", background="#2B2B2B")
        self.style.configure("TNotebook", background="#2B2B2B", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#3C3C3C", foreground="white", padding=[10, 5], font=("Segoe UI", 10), borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", "#2B2B2B"), ("active", "#555555")])

    def _setup_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _create_top_toolbar(self):
        self.top_toolbar_frame = tk.Frame(self, bg="#3C3C3C", height=30)
        self.top_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.top_toolbar_frame.grid_propagate(False)
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
        file_menu.add_command(label="New File", command=self._new_file)
        file_menu.add_command(label="Open File...", command=self._open_file)
        file_menu.add_command(label="Save", command=self._save_file)
        file_menu.add_command(label="Save As...", command=self._save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        edit_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=lambda: self.code_editor.text_area.edit_undo() if self.code_editor else None)
        edit_menu.add_command(label="Redo", command=lambda: self.code_editor.text_area.edit_redo() if self.code_editor else None)
        edit_menu.add_separator()
        def event_gen(event_name):
            widget = self.focus_get()
            if widget:
                widget.event_generate(event_name)
        edit_menu.add_command(label="Cut", command=lambda: event_gen("<<Cut>>"))
        edit_menu.add_command(label="Copy", command=lambda: event_gen("<<Copy>>"))
        edit_menu.add_command(label="Paste", command=lambda: event_gen("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Find/Replace", command=self._open_find_replace_dialog)

        run_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Current File", command=self._run_code)
        run_menu.add_command(label="Stop Execution", command=self._stop_code)
        
        workspace_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Workspace", menu=workspace_menu)
        workspace_menu.add_command(label="Open Folder...", command=self._open_folder)
        workspace_menu.add_command(label="Refresh Explorer", command=lambda: self.file_explorer.populate_tree())
        workspace_menu.add_command(label="Create Virtual Environment", command=self._create_virtual_env)

        options_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Enable Code Completion", variable=self.autocomplete_enabled,
                                      onvalue=True, offvalue=False, command=self._toggle_autocomplete)
        options_menu.add_checkbutton(label="Enable Proactive Error Checking", variable=self.proactive_errors_enabled,
                                      onvalue=True, offvalue=False, command=self._toggle_proactive_errors)

        help_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _toggle_autocomplete(self):
        is_enabled = self.autocomplete_enabled.get()
        if self.code_editor:
            self.code_editor.autocomplete_active = is_enabled

    def _toggle_proactive_errors(self):
        is_enabled = self.proactive_errors_enabled.get()
        if self.code_editor:
            self.code_editor.set_proactive_error_checking(is_enabled)

    def _create_main_content_area(self):
        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        left_pane = ttk.Frame(self.main_paned_window)
        self.main_paned_window.add(left_pane, weight=1)
        self.file_explorer = FileExplorer(left_pane, self.workspace_root_dir, self._open_file_from_path, 
                                          folder_icon=self.folder_icon, python_icon=self.python_logo_icon, 
                                          git_icon=self.git_icon, unknown_icon=self.unknown_file_icon,
                                          txt_icon=self.txt_icon)
        self.file_explorer.pack(fill="both", expand=True)
        self.file_explorer.populate_tree()
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
            selected_tab_id = self.output_notebook.select()
            if not selected_tab_id:
                return
            tab_text = self.output_notebook.tab(selected_tab_id, "text")
            if tab_text == "Terminal":
                self.terminal_console.text.after(50, self.terminal_console.text.focus_set)
            elif tab_text == "Errors" and self.error_console:
                self.error_console.output_console.focus_set()
        except tk.TclError:
            pass 

    def _open_sandbox_if_empty(self):
        if not self.open_files:
            sandbox_path = os.path.join(self.workspace_root_dir, "sandbox.py")
            if not os.path.exists(sandbox_path):
                content = """# sandbox.py
# This is a scratchpad for testing Python code.

print("--- Welcome to the Sandbox ---")

# Example of user input. The terminal will wait for you to type something.
try:
    user_name = input("Please enter your name: ")
    print(f"Hello, {user_name}! Your input was received.")
except EOFError:
    print("\\nInput stream closed. Running non-interactively.")

# --- Sample Code Section ---
# 1. Basic Output: Print a simple message
print("\\nHello from sandbox.py!")
print("This is a temporary file for quick Python tests.")

# 2. Variable Declaration and Basic Arithmetic
num1 = 10
num2 = 5
sum_result = num1 + num2
product_result = num1 * num2

print(f"\\nSum of {num1} and {num2} is: {sum_result}")
print(f"Product of {num1} and {num2} is: {product_result}")

# 3. Looping with a for loop
print("\\nCounting with a for loop:")
for i in range(3): # Loops from 0 to 2
    print(f"Count: {i}")

# 4. Function Definition and Call
def greet_user(name):
    \"\"\"This function prints a personalized greeting.\"\"\"
    print(f"\\nHello, {name}! Welcome to the function.")

greet_user("Python Enthusiast")

print("\\n--- End of Sandbox Execution ---")
"""
                try:
                    with open(sandbox_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.file_explorer.populate_tree()
                except Exception as e:
                    messagebox.showerror("Sandbox Creation Failed", f"Could not create sandbox.py: {e}")
                    return
            self._add_new_tab(file_path=sandbox_path)

    def _check_virtual_env(self):
        found_venv = False
        py_exec_path = ""
        for venv_name in ('.venv', 'venv'): 
            path = os.path.join(self.workspace_root_dir, venv_name)
            if os.path.isdir(path):
                script_dir = 'Scripts' if sys.platform == 'win32' else 'bin'
                potential_path = os.path.join(path, script_dir, 'python.exe' if sys.platform == 'win32' else 'python')
                
                if os.path.exists(potential_path):
                    py_exec_path = os.path.abspath(potential_path)
                    self.python_executable = py_exec_path
                    found_venv = True
                    break 
        
        if not found_venv:
            py_exec_path = os.path.abspath(sys.executable)
            if sys.platform == 'win32' and 'windowsapps' in py_exec_path.lower():
                messagebox.showwarning(
                    "Python Path Warning",
                    f"The detected Python executable is a Microsoft Store stub:\n{py_exec_path}\n\n"
                    "This may cause issues with the terminal and running code. "
                    "Please install Python from python.org and ensure it's on your PATH, or open a workspace with a virtual environment."
                )
            self.python_executable = py_exec_path
        
        print(f"Using Python executable: {self.python_executable}")
        if hasattr(self, 'terminal_console'):
            self.terminal_console.set_python_executable(self.python_executable)
            if not self.terminal_console.interactive_mode:
                self.terminal_console.clear()
                self.terminal_console.show_prompt()

    def _create_virtual_env(self):
        self.terminal_console.write("Creating virtual environment 'venv'... This may take a moment.\n")
        self.output_notebook.select(self.terminal_console)
        self.update_idletasks()
        
        venv_dir = os.path.join(self.workspace_root_dir, "venv")
        if os.path.exists(venv_dir):
            messagebox.showwarning("Exists", "A 'venv' folder already exists in this workspace.")
            self.terminal_console.write("Operation cancelled: 'venv' already exists.\n")
            self.terminal_console.show_prompt()
            return

        def create():
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "venv", venv_dir], 
                    check=True, capture_output=True, text=True,
                    cwd=self.workspace_root_dir
                )
                self.terminal_console.write(f"Successfully created virtual environment in:\n{venv_dir}\n")
                self.after(0, self._check_virtual_env)
                self.after(0, self.file_explorer.populate_tree)
            except subprocess.CalledProcessError as e:
                error_message = f"Failed to create virtual environment.\n\nSTDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}"
                self.terminal_console.write(error_message, "stderr_tag")
            except Exception as e:
                self.terminal_console.write(f"An unexpected error occurred: {e}\n", "stderr_tag")
            finally:
                self.after(0, self.terminal_console.show_prompt)

        threading.Thread(target=create, daemon=True).start()

    def _new_file(self):
        self._add_new_tab()

    def _open_file(self):
        file_path = filedialog.askopenfilename(initialdir=self.workspace_root_dir,
                                               filetypes=[("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            self._open_file_from_path(file_path)

    def _open_folder(self):
        new_path = filedialog.askdirectory(title="Select a Folder to Open as Workspace", initialdir=self.workspace_root_dir)
        if not new_path or not os.path.isdir(new_path):
            return
        
        while self.open_files:
            if not self._close_tab(0, force_ask=True):
                return
        
        self.workspace_root_dir = new_path
        self.file_explorer.set_project_root(new_path)
        
        self.terminal_console.cwd = new_path
        self._check_virtual_env()
        
        self.title(f"PriestyCode v1.0.0 - {os.path.basename(new_path)}")

    def _open_file_from_path(self, file_path):
        if file_path in self.open_files:
            self._switch_to_tab(self.open_files.index(file_path))
        else:
            self._add_new_tab(file_path=file_path)

    def _add_new_tab(self, file_path=None, content=""):
        editor_frame = tk.Frame(self.editor_content_frame, bg="#2B2B2B")
        
        autocomplete_icons = {
            'snippet': self.snippet_icon, 'keyword': self.keyword_icon,
            'function': self.function_icon, 'variable': self.variable_icon
        }
        editor = CodeEditor(editor_frame, error_console=self.error_console, autocomplete_icons=autocomplete_icons)
        
        editor.autocomplete_active = self.autocomplete_enabled.get()
        editor.set_proactive_error_checking(self.proactive_errors_enabled.get())
        editor.pack(fill="both", expand=True)

        if file_path and not file_path.startswith("Untitled-"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
                editor_frame.destroy()
                return
        elif not file_path:
            count = 1
            untitled_name = f"Untitled-{count}.py"
            while untitled_name in self.open_files:
                count += 1
                untitled_name = f"Untitled-{count}.py"
            file_path = untitled_name

        editor.text_area.insert("1.0", content)
        editor.text_area.edit_modified(False)
        self.after(50, editor._on_content_changed)

        tab = tk.Frame(self.tab_bar_frame, bg="#3C3C3C")
        tab.pack(side="left", fill="y", padx=(0, 1))
        
        icon = self._get_icon_for_file(file_path)
        icon_label = tk.Label(tab, bg="#3C3C3C")
        if icon:
            icon_label.config(image=icon)
        icon_label.pack(side="left", padx=(5, 2), pady=2)

        text_label = tk.Label(tab, text=os.path.basename(file_path), fg="white", bg="#3C3C3C", font=("Segoe UI", 9))
        text_label.pack(side="left", padx=(0, 5), pady=2)
        close_button = tk.Button(tab, text="\u2715", bg="#3C3C3C", fg="white", bd=0, relief="flat", activebackground="#E81123", activeforeground="white", font=("Segoe UI", 8, "bold"))
        close_button.pack(side="right", padx=(5, 5), pady=2)

        new_index = len(self.open_files)
        tab.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        icon_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        text_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        close_button.config(command=lambda i=new_index: self._close_tab(i))

        self.open_files.append(file_path)
        self.editor_widgets.append(editor_frame)
        self.tab_widgets.append(tab)
        self._switch_to_tab(new_index)

    def _switch_to_tab(self, index: int):
        if not (0 <= index < len(self.tab_widgets)): return
        if self.current_tab_index != -1 and self.current_tab_index < len(self.editor_widgets):
            self.editor_widgets[self.current_tab_index].pack_forget()
            self._set_tab_appearance(self.tab_widgets[self.current_tab_index], active=False)
        self.current_tab_index = index
        self.current_open_file = self.open_files[index]
        new_editor_frame = self.editor_widgets[index]
        new_editor_frame.pack(fill="both", expand=True)
        self.code_editor = cast(CodeEditor, new_editor_frame.winfo_children()[0])
        self._set_tab_appearance(self.tab_widgets[index], active=True)
        self.code_editor.text_area.focus_set()
        self._update_file_header(self.current_open_file)

    def _set_tab_appearance(self, tab_widget: tk.Frame, active: bool):
        bg = "#2B2B2B" if active else "#3C3C3C"
        tab_widget.config(bg=bg)
        for child in tab_widget.winfo_children():
            if isinstance(child, (tk.Label, tk.Frame)):
                child.config(bg=bg)

    def _close_tab(self, index_to_close: int, force_ask: bool = False) -> bool:
        if not (0 <= index_to_close < len(self.open_files)): return False
        
        file_to_close_path = self.open_files[index_to_close]
        is_sandbox = os.path.basename(file_to_close_path) == "sandbox.py"
        
        editor_to_close = cast(CodeEditor, self.editor_widgets[index_to_close].winfo_children()[0])

        if editor_to_close.text_area.edit_modified() and not is_sandbox:
            message = f"Save changes to {os.path.basename(file_to_close_path)}?"
            if force_ask:
                message = f"Save changes to {os.path.basename(file_to_close_path)} before closing?"
            
            response = messagebox.askyesnocancel("Save on Close", message)
            if response is None: return False
            if response is True and not self._save_file(index_to_close): return False

        self.tab_widgets[index_to_close].destroy()
        self.editor_widgets[index_to_close].destroy()
        self.tab_widgets.pop(index_to_close)
        self.editor_widgets.pop(index_to_close)
        self.open_files.pop(index_to_close)
        
        for i, tab in enumerate(self.tab_widgets):
            close_button = tab.winfo_children()[-1]
            close_button.config(command=lambda new_i=i: self._close_tab(new_i))
            for child in tab.winfo_children()[:-1]:
                child.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
            tab.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
        
        if not self.open_files:
            self.current_tab_index = -1; self.current_open_file = None; self.code_editor = None
            self._update_file_header(None)
        else:
            new_active_index = self.current_tab_index
            if index_to_close < self.current_tab_index:
                new_active_index -= 1
            elif index_to_close == self.current_tab_index:
                new_active_index = max(0, index_to_close - 1)
            
            if new_active_index >= len(self.open_files):
                new_active_index = len(self.open_files) - 1

            self.current_tab_index = -1 
            self._switch_to_tab(new_active_index)
        return True

    def _update_file_header(self, file_path):
        icon = self._get_icon_for_file(file_path)
        if icon:
            self.file_type_icon_label.config(image=icon)
        self.file_name_label.config(text=os.path.basename(file_path) if file_path else "No File Open")

    def _get_icon_for_file(self, file_path):
        if not file_path:
            return self.unknown_file_icon
        if file_path.endswith(".py"):
            return self.python_logo_icon
        if file_path.endswith(".txt"):
            return self.txt_icon
        return self.unknown_file_icon

    def _save_file(self, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        
        editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0])
        file_path = self.open_files[idx]

        if file_path.startswith("Untitled-"):
            return self._save_file_as(idx)
        try:
            with open(file_path, "w", encoding="utf-8") as f: 
                f.write(editor.text_area.get("1.0", "end-1c"))
            editor.text_area.edit_modified(False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _save_file_as(self, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        
        editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0])
        new_path = filedialog.asksaveasfilename(initialdir=self.workspace_root_dir,
                                                defaultextension=".py", filetypes=[("Python", "*.py")])
        if not new_path: return False
        try:
            with open(new_path, "w", encoding="utf-8") as f: 
                f.write(editor.text_area.get("1.0", "end-1c"))
            
            self.open_files[idx] = new_path
            tab = self.tab_widgets[idx]
            
            icon_label = cast(tk.Label, tab.winfo_children()[0])
            text_label = cast(tk.Label, tab.winfo_children()[1])
            new_icon = self._get_icon_for_file(new_path)
            if new_icon:
                icon_label.config(image=new_icon)
            text_label.config(text=os.path.basename(new_path))

            if idx == self.current_tab_index:
                self.current_open_file = new_path
                self._update_file_header(new_path)

            editor.text_area.edit_modified(False)
            self.file_explorer.populate_tree()
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    # === vvv ALL METHODS BELOW THIS LINE ARE REPLACED vvv ===

    def _run_code(self):
        if self.is_running:
            self._stop_code()
            return
            
        if not self.code_editor or not self.current_open_file:
            messagebox.showerror("No File", "Please open a file to run.")
            return
            
        if self.current_open_file.startswith("Untitled-") or self.code_editor.text_area.edit_modified():
            if not self._save_file():
                messagebox.showwarning("Run Cancelled", "File must be saved before running.")
                return

        self.code_editor.clear_error_highlight()
        self.terminal_console.clear()
        self.error_console.clear()
        self.stderr_buffer = ""
        self.is_running = True
        self._update_run_stop_button_state()
        self.terminal_console.set_interactive_mode(True)
        self.output_notebook.select(self.terminal_console)
        self.terminal_console.text.focus_set()
        
        # The main execution is now started in a separate thread
        main_execution_thread = threading.Thread(target=self._execute_in_thread, daemon=True)
        main_execution_thread.start()

    def _start_process_and_threads(self, executable_path: str):
        file_to_run = self.current_open_file
        if not file_to_run:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, "Internal error: No file to execute."))
            return

        exec_dir = os.path.dirname(file_to_run)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        # This line forces the child process to use UTF-8, fixing the error.
        env["PYTHONUTF8"] = "1"
        
        try:
            self.process = subprocess.Popen(
                [executable_path, file_to_run],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                cwd=exec_dir,
                creationflags=creationflags,
                encoding='utf-8',
                errors='replace', # Add error handling for robustness
                bufsize=1,
                env=env
            )
        except FileNotFoundError:
            # Handle case where python executable itself is not found
            self.output_queue.put((PROCESS_ERROR_SIGNAL, f"Executable not found: {executable_path}"))
            return
        except Exception as e:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, f"Failed to start process: {e}"))
            return

        # Start threads for I/O
        threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True).start()
        threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True).start()
        threading.Thread(target=self._write_to_stdin, daemon=True).start()
        
        # Start a thread to monitor when the process finishes
        threading.Thread(target=self._monitor_process, daemon=True).start()

    def _monitor_process(self):
        """Waits for the process to complete and then signals its end."""
        if self.process:
            self.process.wait()
            self.output_queue.put((PROCESS_END_SIGNAL, None))

    def _execute_in_thread(self):
        """Prepares and starts the subprocess execution."""
        try:
            # This logic now just finds the python executable and starts the process.
            # The waiting is handled by the _monitor_process thread.
            self._start_process_and_threads(self.python_executable)
        except Exception as e:
            # This will catch errors in _start_process_and_threads, like file not found.
            self.output_queue.put((PROCESS_ERROR_SIGNAL, str(e)))
    
    def _read_stream_to_queue(self, stream, tag):
        """Reads a stream character by character and puts it on the output queue."""
        try:
            if stream:
                for char in iter(lambda: stream.read(1), ''):
                    self.output_queue.put((char, tag))
        except (ValueError, OSError):
            pass
        finally:
            if stream:
                stream.close()

    def _write_to_stdin(self):
        """Reads from the stdin queue and writes to the process's stdin pipe."""
        while self.process and self.process.poll() is None:
            try:
                data = self.stdin_queue.get(timeout=0.5)
                if self.process and self.process.stdin:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
            except queue.Empty:
                continue
            except (BrokenPipeError, OSError, ValueError):
                # ValueError can be raised if stdin is closed.
                break

    def _stop_code(self):
        if not self.process or self.process.poll() is not None:
            self.is_running = False
            self._update_run_stop_button_state()
            return
            
        self.is_running = False # Set state immediately
        self.terminal_console.set_interactive_mode(False)
        
        # Clear any pending input
        while not self.stdin_queue.empty():
            try:
                self.stdin_queue.get_nowait()
            except queue.Empty:
                break
        
        try:
            self.process.terminate()
            # Use a short timeout to avoid hanging the UI
            self.process.wait(timeout=2)
            self.terminal_console.write("\n--- Process terminated by user ---\n", ("stderr_tag",))
        except (subprocess.TimeoutExpired, Exception):
            self.process.kill()
            self.terminal_console.write("\n--- Process forcefully killed by user ---\n", ("stderr_tag",))
        
        self.process = None
        self._update_run_stop_button_state()
        self.terminal_console.show_prompt()

    def _update_run_stop_button_state(self):
        if self.is_running:
            icon, cmd = self.pause_icon, self._stop_code
        else:
            icon, cmd = self.run_icon, self._run_code
        self.run_stop_button.config(command=cmd)
        if icon:
            self.run_stop_button.config(image=icon)
        else:
            self.run_stop_button.config(text="Stop" if self.is_running else "Run")

    def _open_find_replace_dialog(self):
        if not self.code_editor: return
        if self.find_replace_dialog and self.find_replace_dialog.winfo_exists():
            self.find_replace_dialog.lift()
        else:
            self.find_replace_dialog = FindReplaceDialog(self, self.code_editor)

    def _show_about(self):
        messagebox.showinfo("About PriestyCode", "PriestyCode v1.0.0\nA simple, extensible IDE.\n\nCreated with Python and Tkinter.")

    def _clear_console(self):
        self.terminal_console.clear()
        if not self.terminal_console.interactive_mode:
            self.terminal_console.show_prompt()
        self.error_console.clear()

    def _process_output_queue(self):
        output_chunk = ""
        current_tag = None
        had_items = not self.output_queue.empty()
        
        try:
            while not self.output_queue.empty():
                char, tag = self.output_queue.get_nowait()

                if char == PROCESS_END_SIGNAL:
                    if output_chunk: # Write any remaining chunk
                        self.terminal_console.write(output_chunk, current_tag)
                        output_chunk = ""
                    
                    self.is_running = False
                    self._update_run_stop_button_state()
                    self.terminal_console.set_interactive_mode(False)

                    if "Traceback (most recent call last):" in self.stderr_buffer or \
                       "SyntaxError:" in self.stderr_buffer or \
                       "Exception:" in self.stderr_buffer:
                        self.error_console.display_error("Runtime Error", self.stderr_buffer)
                        self.output_notebook.select(self.error_console)
                    self.stderr_buffer = ""
                    continue

                if char == PROCESS_ERROR_SIGNAL:
                    self.is_running = False
                    self._update_run_stop_button_state()
                    self.terminal_console.set_interactive_mode(False)
                    self.error_console.display_error("Execution Error", tag or "")
                    self.output_notebook.select(self.error_console)
                    continue

                if tag != current_tag and output_chunk:
                    self.terminal_console.write(output_chunk, current_tag)
                    output_chunk = ""

                current_tag = tag
                output_chunk += char
                if tag == "stderr_tag":
                    self.stderr_buffer += char

        except queue.Empty:
            pass
        finally:
            if output_chunk:
                self.terminal_console.write(output_chunk, current_tag)

            if self.is_running and had_items:
                # This prepares the terminal for user input after the prompt is printed
                self.terminal_console.prepare_for_input()
            
            self.after(50, self._process_output_queue)

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.mainloop()

    def _on_closing(self):
        if self.is_running:
            self._stop_code()
        
        while self.open_files:
            if not self._close_tab(0, force_ask=True):
                return
        self.destroy()

# The FindReplaceDialog class remains unchanged
class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent, editor: CodeEditor):
        super().__init__(parent)
        self.editor = editor
        self.text_area = editor.text_area
        self.title("Find & Replace")
        self.transient(parent)
        self.geometry("400x150")
        self.configure(bg="#3C3C3C")
        
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
    
    def find_next(self, start_pos=None):
        pass
    
    def replace(self):
        pass

    def replace_all(self):
        pass