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
import re # Import re for error parsing (Bug 3, 4)

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
        self.process: subprocess.Popen | None = None
        self.output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        self.stdin_queue: queue.Queue[str] = queue.Queue()
        self.stderr_buffer = "" # Buffer for stderr output to parse runtime errors
        self.stdout_buffer = "" # Buffer for stdout to parse handled exceptions
        self.open_files: list[str] = []
        self.tab_widgets: list[tk.Frame] = []
        self.editor_widgets: list[tk.Frame] = []
        self.current_tab_index = -1
        self.current_open_file: str | None = None
        self.code_editor: CodeEditor | None = None # Reference to the currently active CodeEditor instance
        self.active_editor: CodeEditor | None = None # Added for clarity and consistency (Bug 3, 4)
        self.is_running = False
        self.workspace_root_dir = initial_project_root_dir
        self.python_executable = sys.executable
        self.find_replace_dialog: 'FindReplaceDialog' | None = None #type: ignore
        
        self.file_type_icon_label: tk.Label
        self.file_name_label: tk.Label
        self.terminal_console: Terminal
        self.error_console: ConsoleUi # Declare error_console here

        self.autocomplete_enabled = tk.BooleanVar(value=True)
        self.proactive_errors_enabled = tk.BooleanVar(value=True)
        self.highlight_handled_exceptions = tk.BooleanVar(value=True) # New option

        self._load_icons()
        self._configure_styles()
        self._setup_layout()
        self._create_top_toolbar()
        self._create_menu_bar()
        self._create_main_content_area()
        self.after(50, self._process_output_queue) # Reduced delay for more responsive output
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

        # PriestyCode icon and label
        if self.priesty_icon:
            tk.Label(self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C").pack(side="left", padx=5)
        
        # File type icon and name label
        self.file_type_icon_label = tk.Label(self.top_toolbar_frame, bg="#3C3C3C")
        self.file_type_icon_label.pack(side="left", padx=(5,0))
        self.file_name_label = tk.Label(self.top_toolbar_frame, text="No File Open", fg="white", bg="#3C3C3C", font=("Segoe UI", 10, "bold"))
        self.file_name_label.pack(side="left", padx=(2, 10))

        # Buttons on the right side
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
        """Creates the main menu bar with File, Edit, Run, Workspace, Options, and Help menus."""
        menubar = tk.Menu(self, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white", relief="flat", borderwidth=0)
        self.config(menu=menubar)
        menu_kwargs = {"tearoff": 0, "bg": "#3C3C3C", "fg": "white", "activebackground": "#555555", "activeforeground": "white"}
        
        # File Menu
        file_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=self._new_file)
        file_menu.add_command(label="Open File...", command=self._open_file)
        file_menu.add_command(label="Save", command=self._save_file)
        file_menu.add_command(label="Save As...", command=self._save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        # Edit Menu
        edit_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=lambda: self.active_editor.text_area.edit_undo() if self.active_editor else None)
        edit_menu.add_command(label="Redo", command=lambda: self.active_editor.text_area.edit_redo() if self.active_editor else None)
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

        # Run Menu
        run_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Current File", command=self._run_code)
        run_menu.add_command(label="Stop Execution", command=self._stop_code)
        
        # Workspace Menu
        workspace_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Workspace", menu=workspace_menu)
        workspace_menu.add_command(label="Open Folder...", command=self._open_folder)
        workspace_menu.add_command(label="Refresh Explorer", command=lambda: self.file_explorer.populate_tree())
        workspace_menu.add_command(label="Create Virtual Environment", command=self._create_virtual_env)

        # Options Menu
        options_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_checkbutton(label="Enable Code Completion", variable=self.autocomplete_enabled,
                                      onvalue=True, offvalue=False, command=self._toggle_autocomplete)
        options_menu.add_checkbutton(label="Enable Proactive Error Checking", variable=self.proactive_errors_enabled,
                                      onvalue=True, offvalue=False, command=self._toggle_proactive_errors)
        # Add the new option to the menu
        options_menu.add_checkbutton(label="Highlight Handled Exceptions", variable=self.highlight_handled_exceptions,
                                      onvalue=True, offvalue=False)

        # Help Menu
        help_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _toggle_autocomplete(self):
        """Toggles the autocomplete feature in the active editor."""
        is_enabled = self.autocomplete_enabled.get()
        if self.active_editor: # Use active_editor
            self.active_editor.autocomplete_active = is_enabled

    def _toggle_proactive_errors(self):
        """Toggles proactive error checking in the active editor."""
        is_enabled = self.proactive_errors_enabled.get()
        if self.active_editor: # Use active_editor
            self.active_editor.set_proactive_error_checking(is_enabled)

    def _create_main_content_area(self):
        """Creates the main content area with file explorer, editor tabs, and output console."""
        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Left pane for File Explorer
        left_pane = ttk.Frame(self.main_paned_window)
        self.main_paned_window.add(left_pane, weight=1)
        self.file_explorer = FileExplorer(left_pane, self.workspace_root_dir, self._open_file_from_path, 
                                          folder_icon=self.folder_icon, python_icon=self.python_logo_icon, 
                                          git_icon=self.git_icon, unknown_icon=self.unknown_file_icon,
                                          txt_icon=self.txt_icon)
        self.file_explorer.pack(fill="both", expand=True)
        self.file_explorer.populate_tree()

        # Right pane for Editor and Output
        self.right_pane = ttk.PanedWindow(self.main_paned_window, orient=tk.VERTICAL)
        self.main_paned_window.add(self.right_pane, weight=4)

        # Editor Area (top part of right pane)
        editor_area_frame = tk.Frame(self.right_pane, bg="#2B2B2B")
        self.right_pane.add(editor_area_frame, weight=3)
        editor_area_frame.grid_rowconfigure(1, weight=1); editor_area_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_bar_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.tab_bar_frame.grid(row=0, column=0, sticky="ew")
        self.editor_content_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.editor_content_frame.grid(row=1, column=0, sticky="nsew")

        # Output Notebook (bottom part of right pane)
        self.output_notebook = ttk.Notebook(self.right_pane)
        self.right_pane.add(self.output_notebook, weight=1)
        
        # Terminal Tab
        self.terminal_console = Terminal(self.output_notebook, stdin_queue=self.stdin_queue, 
                                         cwd=self.workspace_root_dir, python_executable=self.python_executable)
        self.output_notebook.add(self.terminal_console, text="Terminal")

        # Errors Tab
        self.error_console = ConsoleUi(self.output_notebook)
        self.output_notebook.add(self.error_console, text="Errors")
        self.output_notebook.bind("<<NotebookTabChanged>>", self._on_output_tab_change)

    def _on_output_tab_change(self, event=None):
        """Handles tab changes in the output notebook, focusing the appropriate widget."""
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
            pass # Ignore if tab is being destroyed or invalid

    def _open_sandbox_if_empty(self):
        """Opens or creates a sandbox.py file if no files are open."""
        if not self.open_files:
            sandbox_path = os.path.join(self.workspace_root_dir, "sandbox.py")
            if not os.path.exists(sandbox_path):
                content = """# sandbox.py
import traceback

print("--- Welcome to the Sandbox ---")

# Example of a handled exception.
# This error will be caught, and its traceback will be printed.
try:
    # This line will cause a NameError
    print(hello)
except Exception:
    print("Caught an exception as expected!")
    # Use traceback.print_exc() to print the full details.
    # PriestyCode will detect this and highlight the line in orange.
    traceback.print_exc()


# Example of an unhandled exception (a crash).
# Uncomment the line below to see a runtime error (red highlight).
# print(10 / 0)

print("\\n--- End of Sandbox Execution ---")
"""
                try:
                    with open(sandbox_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.file_explorer.populate_tree() # Refresh file explorer
                except Exception as e:
                    messagebox.showerror("Sandbox Creation Failed", f"Could not create sandbox.py: {e}")
                    return
            self._add_new_tab(file_path=sandbox_path)

    def _check_virtual_env(self):
        """Checks for a virtual environment and sets the Python executable path."""
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
            # Warn if using Microsoft Store stub Python on Windows
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
        """Creates a virtual environment in the current workspace."""
        self.terminal_console.write("Creating virtual environment 'venv'... This may take a moment.\n")
        self.output_notebook.select(self.terminal_console) # Switch to terminal tab
        self.update_idletasks() # Update UI to show message immediately
        
        venv_dir = os.path.join(self.workspace_root_dir, "venv")
        if os.path.exists(venv_dir):
            messagebox.showwarning("Exists", "A 'venv' folder already exists in this workspace.")
            self.terminal_console.write("Operation cancelled: 'venv' already exists.\n")
            self.terminal_console.show_prompt()
            return

        def create():
            """Function to run in a separate thread for venv creation."""
            try:
                process = subprocess.run(
                    [sys.executable, "-m", "venv", venv_dir], 
                    check=True, capture_output=True, text=True,
                    cwd=self.workspace_root_dir
                )
                self.terminal_console.write(f"Successfully created virtual environment in:\n{venv_dir}\n")
                self.after(0, self._check_virtual_env) # Re-check Python executable
                self.after(0, self.file_explorer.populate_tree) # Refresh file explorer
            except subprocess.CalledProcessError as e:
                error_message = f"Failed to create virtual environment.\n\nSTDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}"
                self.terminal_console.write(error_message, "stderr_tag")
            except Exception as e:
                self.terminal_console.write(f"An unexpected error occurred: {e}\n", "stderr_tag")
            finally:
                self.after(0, self.terminal_console.show_prompt)

        threading.Thread(target=create, daemon=True).start()

    def _new_file(self):
        """Creates a new untitled file tab."""
        self._add_new_tab()

    def _open_file(self):
        """Opens a file dialog to select and open a file."""
        file_path = filedialog.askopenfilename(initialdir=self.workspace_root_dir,
                                               filetypes=[("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            self._open_file_from_path(file_path)

    def _open_folder(self):
        """Opens a folder dialog to select a new workspace root."""
        new_path = filedialog.askdirectory(title="Select a Folder to Open as Workspace", initialdir=self.workspace_root_dir)
        if not new_path or not os.path.isdir(new_path):
            return
        
        # Close all open tabs before changing workspace
        while self.open_files:
            if not self._close_tab(0, force_ask=True): # Ask to save if modified
                return # User cancelled closing tabs, so cancel opening new folder
        
        self.workspace_root_dir = new_path
        self.file_explorer.set_project_root(new_path) # Update file explorer root
        
        self.terminal_console.set_cwd(new_path) # Update terminal CWD
        self._check_virtual_env() # Re-check virtual environment for new workspace
        
        self.title(f"PriestyCode v1.0.0 - {os.path.basename(new_path)}") # Update window title

    def _open_file_from_path(self, file_path):
        """Opens a file from a given path, switching to it if already open."""
        if file_path in self.open_files:
            self._switch_to_tab(self.open_files.index(file_path))
        else:
            self._add_new_tab(file_path=file_path)

    def _add_new_tab(self, file_path=None, content=""):
        """Adds a new editor tab for a file."""
        editor_frame = tk.Frame(self.editor_content_frame, bg="#2B2B2B")
        
        # Pass autocomplete icons to the CodeEditor's AutocompleteManager
        autocomplete_icons = {
            'snippet': self.snippet_icon, 'keyword': self.keyword_icon,
            'function': self.function_icon, 'variable': self.variable_icon
        }
        editor = CodeEditor(editor_frame, error_console=self.error_console, autocomplete_icons=autocomplete_icons)
        editor.set_file_path(file_path if file_path else "Untitled-X.py") # Set file path for Bug 5
        
        editor.autocomplete_active = self.autocomplete_enabled.get()
        editor.set_proactive_error_checking(self.proactive_errors_enabled.get())
        editor.pack(fill="both", expand=True)

        # Load content if file_path is provided and not an untitled file
        if file_path and not file_path.startswith("Untitled-"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
                editor_frame.destroy()
                return
        elif not file_path:
            # Generate a unique name for untitled files
            count = 1
            untitled_name = f"Untitled-{count}.py"
            while untitled_name in self.open_files:
                count += 1
                untitled_name = f"Untitled-{count}.py"
            file_path = untitled_name

        editor.text_area.insert("1.0", content)
        editor.text_area.edit_modified(False) # Reset modified flag after loading content
        self.after(50, editor._on_content_changed) # Trigger initial highlighting and checks

        # Create the tab button in the tab bar
        tab = tk.Frame(self.tab_bar_frame, bg="#3C3C3C")
        tab.pack(side="left", fill="y", padx=(0, 1))
        
        # File icon on the tab
        icon = self._get_icon_for_file(file_path)
        icon_label = tk.Label(tab, bg="#3C3C3C")
        if icon:
            icon_label.config(image=icon)
        icon_label.pack(side="left", padx=(5, 2), pady=2)

        # File name label on the tab
        text_label = tk.Label(tab, text=os.path.basename(file_path), fg="white", bg="#3C3C3C", font=("Segoe UI", 9))
        text_label.pack(side="left", padx=(0, 5), pady=2)
        
        # Close button on the tab
        close_button = tk.Button(tab, text="\u2715", bg="#3C3C3C", fg="white", bd=0, relief="flat", activebackground="#E81123", activeforeground="white", font=("Segoe UI", 8, "bold"))
        close_button.pack(side="right", padx=(5, 5), pady=2)

        # Store references and bind events
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
        """Switches to the tab at the given index."""
        if not (0 <= index < len(self.tab_widgets)): return
        
        # Hide the currently active editor (if any)
        if self.current_tab_index != -1 and self.current_tab_index < len(self.editor_widgets):
            self.editor_widgets[self.current_tab_index].pack_forget()
            self._set_tab_appearance(self.tab_widgets[self.current_tab_index], active=False)
        
        # Update current tab index and file info
        self.current_tab_index = index
        self.current_open_file = self.open_files[index]
        
        # Show the new editor frame
        new_editor_frame = self.editor_widgets[index]
        new_editor_frame.pack(fill="both", expand=True)
        
        # Get reference to the CodeEditor instance within the frame
        self.code_editor = cast(CodeEditor, new_editor_frame.winfo_children()[0])
        self.active_editor = self.code_editor # Set active_editor (Bug 3, 4)

        self._set_tab_appearance(self.tab_widgets[index], active=True)
        self.code_editor.text_area.focus_set() # Focus the text area
        self._update_file_header(self.current_open_file)

    def _set_tab_appearance(self, tab_widget: tk.Frame, active: bool):
        """Sets the background color of a tab to indicate active/inactive state."""
        bg = "#2B2B2B" if active else "#3C3C3C"
        tab_widget.config(bg=bg)
        for child in tab_widget.winfo_children():
            if isinstance(child, (tk.Label, tk.Frame)):
                child.config(bg=bg)

    def _close_tab(self, index_to_close: int, force_ask: bool = False) -> bool:
        """Closes the tab at the given index, prompting to save if modified."""
        if not (0 <= index_to_close < len(self.open_files)): return False
        
        file_to_close_path = self.open_files[index_to_close]
        is_sandbox = os.path.basename(file_to_close_path) == "sandbox.py"
        
        editor_to_close = cast(CodeEditor, self.editor_widgets[index_to_close].winfo_children()[0])

        # Prompt to save if file is modified and not sandbox.py
        if editor_to_close.text_area.edit_modified() and not is_sandbox:
            message = f"Save changes to {os.path.basename(file_to_close_path)}?"
            if force_ask:
                message = f"Save changes to {os.path.basename(file_to_close_path)} before closing?"
            
            response = messagebox.askyesnocancel("Save on Close", message)
            if response is None: return False # User cancelled
            if response is True and not self._save_file(index_to_close): return False # Save failed

        # Destroy widgets and remove from lists
        self.tab_widgets[index_to_close].destroy()
        self.editor_widgets[index_to_close].destroy()
        self.tab_widgets.pop(index_to_close)
        self.editor_widgets.pop(index_to_close)
        self.open_files.pop(index_to_close)
        
        # Re-index close buttons and tab bindings for remaining tabs
        for i, tab in enumerate(self.tab_widgets):
            close_button = tab.winfo_children()[-1]
            close_button.config(command=lambda new_i=i: self._close_tab(new_i)) #type: ignore
            for child in tab.winfo_children()[:-1]:
                child.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
            tab.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
        
        # Determine which tab to activate next
        if not self.open_files:
            self.current_tab_index = -1; self.current_open_file = None; self.code_editor = None; self.active_editor = None
            self._update_file_header(None)
        else:
            new_active_index = self.current_tab_index
            if index_to_close < self.current_tab_index:
                new_active_index -= 1 # Shift index if a tab before it was closed
            elif index_to_close == self.current_tab_index:
                new_active_index = max(0, index_to_close - 1) # Activate previous or first tab
            
            if new_active_index >= len(self.open_files):
                new_active_index = len(self.open_files) - 1 # Adjust if last tab was closed

            self.current_tab_index = -1 # Force switch to re-apply appearance
            self._switch_to_tab(new_active_index)
        return True

    def _update_file_header(self, file_path):
        """Updates the file icon and name in the top toolbar."""
        icon = self._get_icon_for_file(file_path)
        if icon:
            self.file_type_icon_label.config(image=icon)
        self.file_name_label.config(text=os.path.basename(file_path) if file_path else "No File Open")

    def _get_icon_for_file(self, file_path):
        """Returns the appropriate icon for a given file path."""
        if not file_path:
            return self.unknown_file_icon
        if file_path.endswith(".py"):
            return self.python_logo_icon
        if file_path.endswith(".txt"):
            return self.txt_icon
        return self.unknown_file_icon

    def _save_file(self, index=None) -> bool:
        """Saves the content of the current or specified file."""
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        
        editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0])
        file_path = self.open_files[idx]

        if file_path.startswith("Untitled-"):
            return self._save_file_as(idx) # If untitled, prompt for save as
        try:
            with open(file_path, "w", encoding="utf-8") as f: 
                f.write(editor.text_area.get("1.0", "end-1c")) # Save all text except last newline
            editor.text_area.edit_modified(False) # Reset modified flag
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _save_file_as(self, index=None) -> bool:
        """Prompts the user to save the current file with a new name/location."""
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)): return False
        
        editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0])
        new_path = filedialog.asksaveasfilename(initialdir=self.workspace_root_dir,
                                                defaultextension=".py", filetypes=[("Python", "*.py")])
        if not new_path: return False # User cancelled
        try:
            with open(new_path, "w", encoding="utf-8") as f: 
                f.write(editor.text_area.get("1.0", "end-1c"))
            
            self.open_files[idx] = new_path # Update file path in list
            editor.set_file_path(new_path) # Update file path in editor instance (Bug 5)

            # Update tab appearance
            tab = self.tab_widgets[idx]
            icon_label = cast(tk.Label, tab.winfo_children()[0])
            text_label = cast(tk.Label, tab.winfo_children()[1])
            new_icon = self._get_icon_for_file(new_path)
            if new_icon:
                icon_label.config(image=new_icon)
            text_label.config(text=os.path.basename(new_path))

            if idx == self.current_tab_index:
                self.current_open_file = new_path
                self._update_file_header(new_path) # Update toolbar header

            editor.text_area.edit_modified(False)
            self.file_explorer.populate_tree() # Refresh file explorer to show new file
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _run_code(self):
        """Starts the execution of the current Python file."""
        if self.is_running:
            self._stop_code()
            return
            
        if not self.active_editor or not self.current_open_file: # Use active_editor
            messagebox.showerror("No File", "Please open a file to run.")
            return
            
        # Save file if it's untitled or modified
        if self.current_open_file.startswith("Untitled-") or self.active_editor.text_area.edit_modified():
            if not self._save_file():
                messagebox.showwarning("Run Cancelled", "File must be saved before running.")
                return

        self.active_editor.clear_error_highlight() 
        self.terminal_console.clear()
        self.error_console.clear() 
        # Reset both stdout and stderr buffers
        self.stderr_buffer = "" 
        self.stdout_buffer = ""
        self.is_running = True
        self._update_run_stop_button_state()
        self.terminal_console.set_interactive_mode(True) 
        self.output_notebook.select(self.terminal_console) 
        self.terminal_console.text.focus_set() 
        
        main_execution_thread = threading.Thread(target=self._execute_in_thread, daemon=True)
        main_execution_thread.start()

    def _start_process_and_threads(self, executable_path: str):
        """Starts the subprocess for code execution and its I/O threads."""
        file_to_run = self.current_open_file
        if not file_to_run:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, "Internal error: No file to execute."))
            return

        exec_dir = os.path.dirname(file_to_run)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0 
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1" 
        env["FORCE_COLOR"] = "1" 
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
                errors='replace', 
                bufsize=1, 
                env=env
            )
        except FileNotFoundError:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, f"Executable not found: {executable_path}"))
            return
        except Exception as e:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, f"Failed to start process: {e}"))
            return

        threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True).start()
        threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True).start()
        threading.Thread(target=self._write_to_stdin, daemon=True).start()
        
        threading.Thread(target=self._monitor_process, daemon=True).start()

    def _monitor_process(self):
        """Waits for the process to complete and then signals its end with the return code."""
        if self.process:
            return_code = self.process.wait() # Wait for the process to terminate and get return code
            self.output_queue.put((PROCESS_END_SIGNAL, return_code)) # type:ignore

    def _execute_in_thread(self):
        """Prepares and starts the subprocess execution."""
        try:
            self._start_process_and_threads(self.python_executable)
        except Exception as e:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, str(e)))
    
    def _read_stream_to_queue(self, stream, tag):
        """Reads a stream character by character and puts it on the output queue."""
        try:
            if stream:
                for char in iter(lambda: stream.read(1), ''): # Read character by character
                    self.output_queue.put((char, tag))
        except (ValueError, OSError):
            pass # Stream might close during reading
        finally:
            if stream:
                stream.close()

    def _write_to_stdin(self):
        """Reads from the stdin queue and writes to the process's stdin pipe."""
        while self.process and self.process.poll() is None: # While process is running
            try:
                data = self.stdin_queue.get(timeout=0.5) # Get data from queue with timeout
                if self.process and self.process.stdin:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
            except queue.Empty:
                continue # No data, continue looping
            except (BrokenPipeError, OSError, ValueError):
                break # Exit loop if pipe is broken or stream closed

    def _stop_code(self):
        """Stops the currently running code execution."""
        if not self.process or self.process.poll() is not None:
            self.is_running = False
            self._update_run_stop_button_state()
            return
            
        self.is_running = False 
        self.terminal_console.set_interactive_mode(False)
        
        while not self.stdin_queue.empty():
            try:
                self.stdin_queue.get_nowait()
            except queue.Empty:
                break
        
        try:
            self.process.terminate() 
            self.process.wait(timeout=2) 
            self.terminal_console.write("\n--- Process terminated by user ---\n", ("stderr_tag",))
        except (subprocess.TimeoutExpired, Exception):
            self.process.kill() 
            self.terminal_console.write("\n--- Process forcefully killed by user ---\n", ("stderr_tag",))
        
        self.process = None 
        self._update_run_stop_button_state()
        self.terminal_console.show_prompt() 

    def _update_run_stop_button_state(self):
        """Updates the run/stop button icon and command based on execution state."""
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
        """Opens the find and replace dialog."""
        if not self.active_editor: return 
        if self.find_replace_dialog and self.find_replace_dialog.winfo_exists():
            self.find_replace_dialog.lift() 
        else:
            self.find_replace_dialog = FindReplaceDialog(self, self.active_editor) 

    def _show_about(self):
        """Displays the about dialog."""
        messagebox.showinfo("About PriestyCode", "PriestyCode v1.0.0\nA simple, extensible IDE.\n\nCreated with Python and Tkinter.")

    def _clear_console(self):
        """Clears both the terminal and errors console."""
        self.terminal_console.clear()
        if not self.terminal_console.interactive_mode:
            self.terminal_console.show_prompt()
        self.error_console.clear()

    def _process_output_queue(self):
        """Processes output from the subprocess queue and updates the UI."""
        output_chunk = ""
        current_tag = None
        had_items = not self.output_queue.empty() 
        
        try:
            while not self.output_queue.empty():
                char, tag = self.output_queue.get_nowait()

                if char == PROCESS_END_SIGNAL:
                    if output_chunk: 
                        self.terminal_console.write(output_chunk, current_tag)
                        output_chunk = ""
                    
                    return_code = tag # This is now the return code from the process
                    
                    self.is_running = False
                    self._update_run_stop_button_state()
                    self.terminal_console.set_interactive_mode(False)
                    
                    # FIX: New logic to differentiate unhandled crashes vs. handled exceptions
                    full_traceback_text = self.stderr_buffer + self.stdout_buffer
                    
                    # Case 1: Unhandled Exception (Crash)
                    if return_code != 0 and "Traceback (most recent call last):" in self.stderr_buffer:
                        self._handle_error_output(self.stderr_buffer, "Runtime Error", "reactive")
                    # Case 2: Handled Exception (Successful exit, but traceback was printed)
                    elif return_code == 0 and "Traceback (most recent call last):" in full_traceback_text and self.highlight_handled_exceptions.get():
                        self._handle_error_output(full_traceback_text, "Handled Exception", "handled")
                    # Case 3: Other crash without a standard traceback
                    elif return_code != 0 and self.stderr_buffer.strip():
                        self.error_console.display_error("Execution Error", self.stderr_buffer.strip())
                        self.output_notebook.select(self.error_console)

                    self.stderr_buffer = ""
                    self.stdout_buffer = ""
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
                elif tag == "stdout_tag":
                    self.stdout_buffer += char

        except queue.Empty:
            pass
        finally:
            if output_chunk:
                self.terminal_console.write(output_chunk, current_tag)

            if self.is_running and had_items:
                self.terminal_console.prepare_for_input()
            
            self.after(50, self._process_output_queue)

    def _handle_error_output(self, error_text: str, default_title: str, highlight_type: str):
        """Parses error text and triggers UI updates for highlighting and error console."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        full_error_text = ansi_escape.sub('', error_text).strip()
        
        traceback_matches = list(re.finditer(r'File "(.*?)", line (\d+)', full_error_text))
        
        if traceback_matches:
            last_match = traceback_matches[-1]
            file_path_error = last_match.group(1)
            line_num_error = int(last_match.group(2))
            
            error_title = default_title
            last_lines = full_error_text.strip().split('\n')
            if last_lines:
                error_title_candidate = last_lines[-1].split(':')[0]
                if 'Error' in error_title_candidate or 'Exception' in error_title_candidate:
                    error_title = error_title_candidate

            try:
                error_file_index = -1
                norm_error_path = os.path.normcase(os.path.abspath(file_path_error))
                for i, open_file_path in enumerate(self.open_files):
                    if open_file_path and os.path.normcase(os.path.abspath(open_file_path)) == norm_error_path:
                        error_file_index = i
                        break
                
                if error_file_index != -1:
                    editor_frame = self.editor_widgets[error_file_index]
                    editor_instance = cast(CodeEditor, editor_frame.winfo_children()[0])
                    
                    if highlight_type == "reactive":
                        self.after(0, editor_instance.highlight_runtime_error, line_num_error, full_error_text)
                    elif highlight_type == "handled":
                        self.after(0, editor_instance.highlight_handled_exception, line_num_error, full_error_text)

            except Exception as e:
                print(f"Non-critical error: Could not highlight error in editor. Details: {e}")
            
            self.error_console.display_error(error_title, full_error_text)
            self.output_notebook.select(self.error_console)
        else:
            self.error_console.display_error(default_title, full_error_text)
            self.output_notebook.select(self.error_console)

    def run(self):
        """Starts the Tkinter event loop."""
        self.protocol("WM_DELETE_WINDOW", self._on_closing) 
        self.mainloop()

    def _on_closing(self):
        """Handles the window closing event, prompting to save modified files."""
        if self.is_running:
            self._stop_code() 
        
        while self.open_files:
            if not self._close_tab(0, force_ask=True):
                return
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