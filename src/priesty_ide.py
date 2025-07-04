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
    def __init__(self):
        super().__init__()
        self.title("PriestyCode v1.0.0")
        self.geometry("1300x850")
        self.config(bg="#2B2B2B")

        self.icon_size = 16
        self.process = None
        self.output_queue = queue.Queue()
        self.stdin_queue = queue.Queue()
        self.open_files = []
        self.tab_widgets = []
        self.editor_widgets = []
        self.current_tab_index = -1
        self.current_open_file = None
        self.code_editor = None
        self.is_running = False
        self.workspace_root_dir = initial_project_root_dir
        self.python_executable = sys.executable
        self.find_replace_dialog = None
        self.autocomplete_enabled = tk.BooleanVar(value=True)

        self._load_icons()
        self._configure_styles()
        self._setup_layout()
        self._create_top_toolbar()
        self._create_menu_bar()
        self._create_main_content_area()
        self.after(100, self._process_output_queue)
        self.after(200, self._check_virtual_env)
        self.after(500, self._open_sandbox_if_empty)

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
        file_menu.add_command(label="Exit", command=self.quit)

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

        options_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Enable Code Completion", variable=self.autocomplete_enabled,
                                      onvalue=True, offvalue=False, command=self._toggle_autocomplete)

        help_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _toggle_autocomplete(self):
        is_enabled = self.autocomplete_enabled.get()
        for editor_frame in self.editor_widgets:
            if editor_frame.winfo_exists():
                editor = editor_frame.winfo_children()[0]
                editor.autocomplete_active = is_enabled

    def _create_main_content_area(self):
        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        left_pane = ttk.Frame(self.main_paned_window)
        self.main_paned_window.add(left_pane, weight=1)
        self.file_explorer = FileExplorer(left_pane, self.workspace_root_dir, self._open_file_from_path, folder_icon=self.folder_icon, python_icon=self.python_logo_icon, git_icon=self.git_icon, unknown_icon=self.unknown_file_icon)
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
        self.terminal_console = Terminal(self.output_notebook, stdin_queue=self.stdin_queue)
        self.output_notebook.add(self.terminal_console, text="Terminal")
        self.error_console = ConsoleUi(self.output_notebook)
        self.output_notebook.add(self.error_console, text="Errors")
        self.output_notebook.bind("<<NotebookTabChanged>>", self._on_output_tab_change)

    def _on_output_tab_change(self, event=None):
        selected_tab_id = self.output_notebook.select()
        if not selected_tab_id:
            return
        tab_text = self.output_notebook.tab(selected_tab_id, "text")
        if tab_text == "Terminal":
            self.terminal_console.text.after(50, self.terminal_console.text.focus_set)
        elif tab_text == "Errors" and self.error_console:
            self.error_console.output_console.focus_set()

    def _open_sandbox_if_empty(self):
        if not self.open_files:
            sandbox_path = os.path.join(self.workspace_root_dir, "sandbox.py")
            if not os.path.exists(sandbox_path):
                content = """# sandbox.py
# This file is intended for temporary code execution and quick testing in your IDE.
# It serves as a scratchpad where you can write and run Python code without
# creating a new, permanent file for every small experiment or test.

# You can replace the sample code below with your own code at any time.
# Changes made here are typically not saved permanently unless you explicitly
# save this file or copy its contents elsewhere.

# --- Sample Code Section ---

# 1. Basic Output: Print a simple message
print("Hello from sandbox.py!")
print("This is a temporary file for quick Python tests.")

# 2. Variable Declaration and Basic Arithmetic
num1 = 10
num2 = 5
sum_result = num1 + num2
difference_result = num1 - num2
product_result = num1 * num2
division_result = num1 / num2 # Returns a float
floor_division_result = num1 // num2 # Returns an integer

print(f"\\nNumbers: {num1}, {num2}")
print(f"Sum: {sum_result}")
print(f"Difference: {difference_result}")
print(f"Product: {product_result}")
print(f"Division: {division_result}")
print(f"Floor Division: {floor_division_result}")

# 3. String Manipulation
greeting = "Hello"
name = "World"
full_message = greeting + ", " + name + "!"
print(f"\\nFull message: {full_message}")
print(f"Message in uppercase: {full_message.upper()}")
print(f"Message with 'o' replaced by '*': {full_message.replace('o', '*')}")

# 4. List Operations
my_list = [1, 2, 3, 4, 5]
print(f"\\nOriginal list: {my_list}")
my_list.append(6)
print(f"List after appending 6: {my_list}")
print(f"First element: {my_list[0]}")
print(f"Length of list: {len(my_list)}")

# 5. Conditional Statements (if-elif-else)
temperature = 25

if temperature > 30:
    print("\\nIt's hot outside!")
elif temperature > 20:
    print("\\nIt's a pleasant day.")
else:
    print("\\nIt's a bit chilly.")

# 6. Loops (for loop)
print("\\nCounting with a for loop:")
for i in range(3): # Loops from 0 to 2
    print(f"Count: {i}")

# 7. Function Definition and Call
def greet_user(user_name):
    \"\"\"
    This function takes a user's name and prints a personalized greeting.
    \"\"\"
    print(f"\\nHello, {user_name}! Welcome to the sandbox.")

# Call the function
greet_user("Python Enthusiast")
greet_user("Tester")

# --- End of Sample Code Section ---

# Feel free to delete or modify any of the above code and write your own.
# This file is your personal playground for Python code snippets!
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
        for venv_name in ('venv', '.venv'):
            path = os.path.join(self.workspace_root_dir, venv_name)
            if os.path.isdir(path):
                script_dir = 'Scripts' if sys.platform == 'win32' else 'bin'
                py_exec = os.path.join(path, script_dir, 'python.exe' if sys.platform == 'win32' else 'python')
                if os.path.exists(py_exec):
                    self.python_executable = py_exec
                    print(f"Virtual environment found and loaded: {self.python_executable}")
                    return
        if messagebox.askyesno("Virtual Environment", "No virtual environment found. Would you like to create one?"):
            threading.Thread(target=self._create_virtual_env, daemon=True).start()

    def _create_virtual_env(self):
        self.file_name_label.config(text="Creating venv...")
        try:
            venv_dir = os.path.join(self.workspace_root_dir, "venv")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True, capture_output=True, text=True)
            self._check_virtual_env()
            messagebox.showinfo("Success", "Virtual environment 'venv' created successfully.")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Failed to create venv.\n{e.stderr}")
        finally:
            self._update_file_header(self.current_open_file)

    def _new_file(self):
        self._add_new_tab()

    def _open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if file_path:
            self._open_file_from_path(file_path)

    def _open_file_from_path(self, file_path):
        if file_path in self.open_files:
            self._switch_to_tab(self.open_files.index(file_path))
        else:
            self._add_new_tab(file_path=file_path)

    def _add_new_tab(self, file_path=None, content=""):
        editor_frame = tk.Frame(self.editor_content_frame, bg="#2B2B2B")
        editor = CodeEditor(editor_frame, error_console=self.error_console)
        editor.autocomplete_active = self.autocomplete_enabled.get()
        editor.pack(fill="both", expand=True)
        if file_path and not file_path.startswith(("Untitled-")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
                editor_frame.destroy()
                return
        elif not file_path:
            count = 1
            while f"Untitled-{count}.py" in self.open_files:
                count += 1
            file_path = f"Untitled-{count}.py"
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

    def _switch_to_tab(self, index):
        if not (0 <= index < len(self.tab_widgets)): return
        if self.current_tab_index != -1 and self.current_tab_index < len(self.editor_widgets):
            self.editor_widgets[self.current_tab_index].pack_forget()
            self._set_tab_appearance(self.tab_widgets[self.current_tab_index], active=False)
        self.current_tab_index = index
        self.current_open_file = self.open_files[index]
        new_editor_frame = self.editor_widgets[index]
        new_editor_frame.pack(fill="both", expand=True)
        self.code_editor = new_editor_frame.winfo_children()[0]
        self._set_tab_appearance(self.tab_widgets[index], active=True)
        self.code_editor.text_area.focus_set()
        self._update_file_header(self.current_open_file)

    def _set_tab_appearance(self, tab_widget, active):
        bg = "#2B2B2B" if active else "#3C3C3C"
        tab_widget.config(bg=bg)
        for child in tab_widget.winfo_children():
            if not isinstance(child, tk.Button):
                child.config(bg=bg)

    def _close_tab(self, index_to_close):
        if not (0 <= index_to_close < len(self.open_files)): return
        editor_to_close = self.editor_widgets[index_to_close].winfo_children()[0]
        if editor_to_close.text_area.edit_modified():
            response = messagebox.askyesnocancel("Save on Close", f"Save changes to {os.path.basename(self.open_files[index_to_close])}?")
            if response is None: return
            if response is True and not self._save_file(index_to_close): return
        self.tab_widgets[index_to_close].destroy()
        self.editor_widgets[index_to_close].destroy()
        self.tab_widgets.pop(index_to_close)
        self.editor_widgets.pop(index_to_close)
        self.open_files.pop(index_to_close)
        for i, tab in enumerate(self.tab_widgets):
            for child in tab.winfo_children():
                if isinstance(child, tk.Button):
                    child.config(command=lambda new_i=i: self._close_tab(new_i))
                else:
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

    def _update_file_header(self, file_path):
        icon = self._get_icon_for_file(file_path)
        if icon: self.file_type_icon_label.config(image=icon)
        self.file_name_label.config(text=os.path.basename(file_path) if file_path else "No File Open")

    def _get_icon_for_file(self, file_path):
        return self.python_logo_icon if file_path and file_path.endswith(".py") else self.unknown_file_icon

    def _save_file(self, index=None):
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        file_path = self.open_files[idx]
        editor = self.editor_widgets[idx].winfo_children()[0]
        if file_path.startswith(("Untitled-")):
            return self._save_file_as(idx)
        try:
            with open(file_path, "w", encoding="utf-8") as f: f.write(editor.text_area.get("1.0", tk.END))
            editor.text_area.edit_modified(False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _save_file_as(self, index=None):
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        editor = self.editor_widgets[idx].winfo_children()[0]
        new_path = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python", "*.py")])
        if not new_path: return False
        try:
            with open(new_path, "w", encoding="utf-8") as f: f.write(editor.text_area.get("1.0", tk.END))
            self.open_files[idx] = new_path
            tab = self.tab_widgets[idx]
            for child in tab.winfo_children():
                if isinstance(child, tk.Label):
                    icon = self._get_icon_for_file(new_path)
                    if hasattr(child, 'image') and icon: child.config(image=icon)
                    elif not hasattr(child, 'image'): child.config(text=os.path.basename(new_path))
            self.current_open_file = new_path
            self._update_file_header(new_path)
            editor.text_area.edit_modified(False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _run_code(self):
        if self.is_running: self._stop_code(); return
        if not self.code_editor or self.current_open_file is None:
            messagebox.showerror("No File", "Please open a file to run.")
            return
        code = self.code_editor.text_area.get("1.0", tk.END)
        self.code_editor.clear_error_highlight()
        self.terminal_console.clear()
        self.is_running = True
        self._update_run_stop_button_state()
        self.terminal_console.set_interactive_mode(True)
        self.output_notebook.select(self.terminal_console)
        self.terminal_console.text.focus_set()
        threading.Thread(target=self._execute_in_thread, args=(code,), daemon=True).start()

    def _execute_in_thread(self, code_content):
        temp_file_path = None
        try:
            exec_dir = self.workspace_root_dir
            if self.current_open_file and not self.current_open_file.startswith(("Untitled-")):
                exec_dir = os.path.dirname(self.current_open_file)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".py", encoding="utf-8", dir=exec_dir) as temp_file:
                temp_file.write(code_content)
                temp_file_path = temp_file.name
            
            self.process = subprocess.Popen([self.python_executable, "-u", temp_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, text=True, cwd=exec_dir)
            stdout_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True)
            stdin_thread = threading.Thread(target=self._write_to_stdin, daemon=True)
            stdout_thread.start(); stderr_thread.start(); stdin_thread.start()
            self.process.wait()
            stdout_thread.join(); stderr_thread.join()
            self.output_queue.put((PROCESS_END_SIGNAL, None))
        except Exception as e:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, str(e)))
        finally:
            if temp_file_path and os.path.exists(temp_file_path): os.remove(temp_file_path)
            self.is_running = False
            self.after(0, self.terminal_console.set_interactive_mode, False)
            self.after(0, self._update_run_stop_button_state)
    
    def _read_stream_to_queue(self, stream, tag):
        try:
            if stream:
                for char in iter(lambda: stream.read(1), ''):
                    self.output_queue.put((char, tag))
        except Exception:
            pass
        finally:
            if stream: stream.close()

    def _write_to_stdin(self):
        while self.process and self.process.poll() is None:
            try:
                data = self.stdin_queue.get(timeout=0.5)
                if self.process.stdin:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
            except queue.Empty: continue
            except (BrokenPipeError, OSError): break

    def _stop_code(self):
        self.is_running = False
        self.terminal_console.set_interactive_mode(False)
        while not self.stdin_queue.empty():
            try: self.stdin_queue.get_nowait()
            except queue.Empty: break
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate(); self.process.wait(timeout=2)
                self.terminal_console.write("\n--- Process terminated by user ---\n", "stderr_tag")
            except Exception: self.process.kill()
        self._update_run_stop_button_state()

    def _update_run_stop_button_state(self):
        if self.is_running:
            icon, cmd = self.pause_icon, self._stop_code
        else:
            icon, cmd = self.run_icon, self._run_code
        self.run_stop_button.config(command=cmd)
        if icon: self.run_stop_button.config(image=icon)
        else: self.run_stop_button.config(text="Stop" if self.is_running else "Run", image="")

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

    def _process_output_queue(self):
        try:
            while True:
                line, tag = self.output_queue.get_nowait()
                if line == PROCESS_END_SIGNAL:
                    self.terminal_console.show_prompt()
                elif line == PROCESS_ERROR_SIGNAL:
                    if self.error_console:
                        self.error_console.format_error_output("Runtime Error", tag or "")
                else:
                    self.terminal_console.write(line, tag)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_output_queue)

    def run(self):
        self.mainloop()
        self._stop_code()

class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent, editor):
        super().__init__(parent)
        self.editor = editor; self.text_area = editor.text_area
        self.title("Find & Replace"); self.transient(parent)
        self.geometry("400x150"); self.configure(bg="#3C3C3C")
        tk.Label(self, text="Find:", bg="#3C3C3C", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.find_entry = tk.Entry(self, bg="#2B2B2B", fg="white", insertbackground="white")
        self.find_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(self, text="Replace:", bg="#3C3C3C", fg="white").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.replace_entry = tk.Entry(self, bg="#2B2B2B", fg="white", insertbackground="white")
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        button_frame = tk.Frame(self, bg="#3C3C3C"); button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        btn_kwargs = {"bg":"#555555", "fg":"white", "bd":1, "relief":"solid", "padx":5, "pady":2}
        tk.Button(button_frame, text="Find Next", command=self.find_next, **btn_kwargs).pack(side="left", padx=5)
        tk.Button(button_frame, text="Replace", command=self.replace, **btn_kwargs).pack(side="left", padx=5)
        tk.Button(button_frame, text="Replace All", command=self.replace_all, **btn_kwargs).pack(side="left", padx=5)
        self.grid_columnconfigure(1, weight=1); self.find_entry.focus_set()
    def find_next(self, start_pos=None): pass
    def replace(self): pass
    def replace_all(self): pass