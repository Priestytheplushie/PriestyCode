# priesty_ide.py

import tkinter as tk
from tkinter import messagebox, filedialog, ttk, simpledialog
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
import json
from platformdirs import user_config_dir

try:
    from code_editor import CodeEditor
    from console_ui import ConsoleUi
    from terminal import Terminal
    from file_explorer import FileExplorer
    # ADD THIS IMPORT
    from source_control_ui import SourceControlUI
except Exception:
    from src.code_editor import CodeEditor
    from src.console_ui import ConsoleUi
    from src.terminal import Terminal
    from src.file_explorer import FileExplorer
    # ADD THIS IMPORT
    from src.source_control_ui import SourceControlUI


# --- Core Application Paths ---
current_dir = os.path.dirname(__file__)
initial_project_root_dir = os.path.abspath(os.path.join(current_dir, ".."))
ICON_PATH = os.path.join(initial_project_root_dir, "assets", "icons")

# --- Settings File Path (using platformdirs) ---
APP_NAME = "PriestyCode"
_settings_dir = user_config_dir(appname=APP_NAME, roaming=True)
os.makedirs(_settings_dir, exist_ok=True)
SETTINGS_PATH = os.path.join(_settings_dir, "settings.json")

PROCESS_END_SIGNAL = "<<ProcessEnd>>"
PROCESS_ERROR_SIGNAL = "<<ProcessError>>"


class PriestyCode(tk.Tk):
    BINARY_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".exe",
        ".dll",
        ".so",
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".o",
        ".a",
        ".obj",
        ".lib",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wav",
        ".flac",
        ".pyc",
    }

    def __init__(self):
        super().__init__()
        self.title("PriestyCode v1.0.0")
        # MODIFIED: Increase default width for new panel
        self.geometry("1450x850") 
        self.config(bg="#2B2B2B")

        self.icon_size = 16
        self.process: subprocess.Popen | None = None
        self.output_queue: queue.Queue[tuple[str, Union[str, int, None]]] = (
            queue.Queue()
        )
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
        self.find_replace_dialog: "FindReplaceDialog" | None = None  # type: ignore
        self.venv_warning_shown = False
        self.temp_run_file: str | None = None

        self.file_type_icon_label: tk.Label
        self.file_name_label: tk.Label
        self.error_console: ConsoleUi
        self.file_explorer: FileExplorer
        # ADDED: Initialize source_control_ui to None
        self.source_control_ui: SourceControlUI | None = None

        # --- Terminal Management ---
        self.terminals: list[Terminal] = []
        self.terminal_ui_map: dict[Terminal, tk.Frame] = {}
        self.active_terminal: Terminal | None = None
        self.terminal_content_frame: tk.Frame
        self.terminal_tabs_sidebar: tk.Frame
        self.add_terminal_button: tk.Button
        self.output_notebook: ttk.Notebook

        # --- Settings Management ---
        self.autosave_timer: str | None = None
        self._initialize_settings_vars()
        self._load_settings()

        self._load_icons()
        self._configure_styles()
        self._setup_layout()
        self._create_top_toolbar()
        self._create_menu_bar() # Menu bar created BEFORE source_control_ui is initialized
        self._create_main_content_area()
        # ADD THIS
        self._create_status_bar()
        self._bind_shortcuts()
        
        self.after(1, self._apply_font_size)
        self.after(50, self._process_output_queue)
        self.after(200, self._check_virtual_env)
        # MODIFIED: Update Git info after checking venv
        self.after(300, self.update_git_info)
        self.after(500, self._open_sandbox_if_empty)
    
    def _initialize_settings_vars(self):
        """Initializes all tk.Vars for settings with default values."""
        self.autocomplete_enabled = tk.BooleanVar(value=True)
        self.proactive_errors_enabled = tk.BooleanVar(value=True)
        self.highlight_handled_exceptions = tk.BooleanVar(value=True)
        self.fullscreen_var = tk.BooleanVar(value=False)
        self.autosave_enabled = tk.BooleanVar(value=False)
        self.autoindent_enabled = tk.BooleanVar(value=True)
        self.tooltips_enabled = tk.BooleanVar(value=True)
        self.font_size = tk.IntVar(value=10)

    def _load_settings(self):
        """Loads settings from a JSON file."""
        try:
            with open(SETTINGS_PATH, "r") as f:
                settings = json.load(f)

            self.autocomplete_enabled.set(settings.get("autocomplete_enabled", True))
            self.proactive_errors_enabled.set(
                settings.get("proactive_errors_enabled", True)
            )
            self.highlight_handled_exceptions.set(
                settings.get("highlight_handled_exceptions", True)
            )
            self.autosave_enabled.set(settings.get("autosave_enabled", False))
            self.autoindent_enabled.set(settings.get("autoindent_enabled", True))
            self.tooltips_enabled.set(settings.get("tooltips_enabled", True))
            self.font_size.set(settings.get("font_size", 10))
        except (FileNotFoundError, json.JSONDecodeError):
            self._save_settings()

    def _save_settings(self, event=None):
        """Saves current settings to a JSON file."""
        settings = {
            "autocomplete_enabled": self.autocomplete_enabled.get(),
            "proactive_errors_enabled": self.proactive_errors_enabled.get(),
            "highlight_handled_exceptions": self.highlight_handled_exceptions.get(),
            "autosave_enabled": self.autosave_enabled.get(),
            "autoindent_enabled": self.autoindent_enabled.get(),
            "tooltips_enabled": self.tooltips_enabled.get(),
            "font_size": self.font_size.get(),
        }
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _load_icons(self):
        """Loads and resizes icons used throughout the IDE."""
        self.window_icon = self._load_and_resize_icon(
            "priesty.png", is_photo_image=True
        )
        if isinstance(self.window_icon, tk.PhotoImage):
            self.iconphoto(True, self.window_icon)

        ico_path = os.path.join(ICON_PATH, "Priesty.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception as e:
                print(f"Warning: Could not set .ico file: {e}")

        self.priesty_icon = self._load_and_resize_icon("priesty.png", size=24)
        self.folder_icon = self._load_and_resize_icon("folder_icon.png")
        self.git_icon = self._load_and_resize_icon("git_icon.png")
        self.run_icon = self._load_and_resize_icon("run.png", size=24)
        self.pause_icon = self._load_and_resize_icon("pause.png", size=24)
        self.unknown_file_icon = self._load_and_resize_icon("unknwon.png")
        self.python_logo_icon = self._load_and_resize_icon("python_logo.png")
        self.close_icon = self._load_and_resize_icon("close_icon.png", size=12)
        self.txt_icon = self._load_and_resize_icon("txt_icon.png")
        self.md_icon = self._load_and_resize_icon("markdown_icon.png")
        self.add_icon = self._load_and_resize_icon("add_icon.png", size=16)
        self.terminal_icon = self._load_and_resize_icon("terminal_icon.png", size=16)

        # Icons for autocomplete manager
        self.snippet_icon = self._load_and_resize_icon("snippet_icon.png")
        self.keyword_icon = self._load_and_resize_icon("keyword_icon.png")
        self.function_icon = self._load_and_resize_icon("function_icon.png")
        self.variable_icon = self._load_and_resize_icon("variable_icon.png")

    def _load_and_resize_icon(self, icon_name, size=None, is_photo_image=False):
        """Helper to load, resize, and return a PhotoImage from an icon file."""
        try:
            path = os.path.join(ICON_PATH, icon_name)
            if not os.path.exists(path):
                return None
            if is_photo_image:
                return tk.PhotoImage(file=path)

            pil_image = Image.open(path)
            if size is None:
                size = self.icon_size

            aspect_ratio = pil_image.width / pil_image.height
            resized_image = pil_image.resize(
                (int(aspect_ratio * size), size), Image.Resampling.LANCZOS
            )
            return ImageTk.PhotoImage(resized_image)
        except Exception as e:
            print(f"Error loading icon {icon_name}: {e}")
            return None

    def _configure_styles(self):
        """Configures the ttk styles for various widgets."""
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("TPanedwindow", background="#2B2B2B")
        self.style.configure("TNotebook", background="#2B2B2B", borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background="#3C3C3C",
            foreground="white",
            padding=[10, 5],
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        self.style.map(
            "TNotebook.Tab", background=[("selected", "#2B2B2B"), ("active", "#555555")]
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#3C3C3C",
            foreground="white",
            relief="flat",
        )
        self.style.map("Treeview.Heading", background=[("active", "#555555")])
    
    def _setup_layout(self):
        """Sets up the main grid layout for the IDE window."""
        # MODIFIED: Add row for status bar
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0) # Status bar row
        self.grid_columnconfigure(0, weight=1)

    def _create_top_toolbar(self):
        """Creates the top toolbar with IDE name, file info, and run button."""
        self.top_toolbar_frame = tk.Frame(self, bg="#3C3C3C", height=30)
        self.top_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.top_toolbar_frame.grid_propagate(False)

        if self.priesty_icon:
            tk.Label(
                self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C"
            ).pack(side="left", padx=5)

        self.file_type_icon_label = tk.Label(self.top_toolbar_frame, bg="#3C3C3C")
        self.file_type_icon_label.pack(side="left", padx=(5, 0))
        self.file_name_label = tk.Label(
            self.top_toolbar_frame,
            text="No File Open",
            fg="white",
            bg="#3C3C3C",
            font=("Segoe UI", 10, "bold"),
        )
        self.file_name_label.pack(side="left", padx=(2, 10))

        btn_kwargs = {
            "bg": "#3C3C3C",
            "bd": 0,
            "activebackground": "#555555",
            "highlightthickness": 0,
        }

        self.run_stop_button = tk.Button(
            self.top_toolbar_frame, command=self._run_code, **btn_kwargs
        )
        if self.run_icon:
            self.run_stop_button.config(image=self.run_icon)
        else:
            self.run_stop_button.config(text="Run", fg="white")
        self.run_stop_button.pack(side="right", padx=5)

    def _create_menu_bar(self):
        menubar = tk.Menu(
            self,
            bg="#3C3C3C",
            fg="white",
            activebackground="#555555",
            activeforeground="white",
            relief="flat",
            borderwidth=0,
        )
        self.config(menu=menubar)
        menu_kwargs = {
            "tearoff": 0,
            "bg": "#3C3C3C",
            "fg": "white",
            "activebackground": "#555555",
            "activeforeground": "white",
        }

        file_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="File", menu=file_menu)

        new_menu = tk.Menu(file_menu, **menu_kwargs)
        file_menu.add_cascade(label="New...", menu=new_menu)
        new_menu.add_command(label="Python File", command=lambda: self._new_file())
        new_menu.add_command(
            label="Text File", command=lambda: self._new_file(extension=".txt")
        )

        file_menu.add_command(
            label="Open File...", command=self._open_file, accelerator="Ctrl+O"
        )
        file_menu.add_command(label="Open Folder...", command=self._open_folder)
        file_menu.add_command(label="Open Sandbox", command=self._open_new_sandbox_tab)
        file_menu.add_separator()
        file_menu.add_command(
            label="Save", command=self._save_file, accelerator="Ctrl+S"
        )
        file_menu.add_command(
            label="Save As...", command=self._save_file_as, accelerator="Ctrl+Shift+S"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        edit_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(
            label="Undo", command=self._handle_undo, accelerator="Ctrl+Z"
        )
        edit_menu.add_command(
            label="Redo", command=self._handle_redo, accelerator="Ctrl+Y"
        )
        edit_menu.add_separator()

        def event_gen(event_name):
            try:
                self.focus_get().event_generate(event_name)  # type: ignore
            except (AttributeError, tk.TclError):
                pass

        edit_menu.add_command(
            label="Cut", command=lambda: event_gen("<<Cut>>"), accelerator="Ctrl+X"
        )
        edit_menu.add_command(
            label="Copy", command=lambda: event_gen("<<Copy>>"), accelerator="Ctrl+C"
        )
        edit_menu.add_command(
            label="Paste", command=lambda: event_gen("<<Paste>>"), accelerator="Ctrl+V"
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Find/Replace",
            command=self._open_find_replace_dialog,
            accelerator="Ctrl+F",
        )

        refactor_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Refactor", menu=refactor_menu)
        refactor_menu.add_command(label="Rename...", command=self._rename_active_file)
        refactor_menu.add_command(
            label="Move Active File...", command=self._move_active_file
        )
        refactor_menu.add_command(
            label="Duplicate Active File...", command=self._duplicate_active_file
        )

        run_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(
            label="Run Current File", command=self._run_code, accelerator="F5"
        )
        run_menu.add_command(
            label="Stop Execution", command=self._stop_code, accelerator="Ctrl+F2"
        )

        terminal_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Terminal", menu=terminal_menu)
        terminal_menu.add_command(
            label="New Terminal Tab", command=self._create_new_terminal
        )
        terminal_menu.add_separator()
        terminal_menu.add_command(
            label="Clear Active Terminal/Console",
            command=self._clear_active_output_view,
        )
        terminal_menu.add_command(
            label="Clear Problems", command=lambda: self.error_console.clear()
        )

        window_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Window", menu=window_menu)
        window_menu.add_command(
            label="Open New IDE Window", command=self._open_new_window
        )
        window_menu.add_checkbutton(
            label="Full Screen",
            onvalue=True,
            offvalue=False,
            variable=self.fullscreen_var,
            command=self._toggle_fullscreen,
            accelerator="F11",
        )
        window_menu.add_separator()
        window_menu.add_command(label="Reset Layout", command=self._reset_layout)
        window_menu.add_separator()
        window_menu.add_command(
            label="Open External Terminal", command=self._open_external_terminal
        )

        workspace_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Workspace", menu=workspace_menu)
        workspace_menu.add_command(
            label="Refresh Explorer", command=lambda: self.file_explorer.populate_tree()
        )
        workspace_menu.add_separator()
        workspace_menu.add_command(
            label="Change Interpreter", command=self._change_interpreter
        )
        workspace_menu.add_command(
            label="Create Virtual Environment", command=self._create_virtual_env
        )
        workspace_menu.add_command(
            label="Install Requirements", command=self._install_requirements
        )
        
        # --- ADD NEW SOURCE CONTROL MENU ---
        source_control_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Source Control", menu=source_control_menu)
        # MODIFIED: Call wrapper methods that check for source_control_ui's existence
        source_control_menu.add_command(label="Refresh", command=self._sc_refresh)
        source_control_menu.add_command(label="Commit...", command=self._sc_commit_action)
        source_control_menu.add_command(label="Push", command=self._sc_push_action)
        source_control_menu.add_command(label="Pull", command=self._sc_pull_action)
        source_control_menu.add_separator()
        source_control_menu.add_command(label="Initialize Repository", command=self._sc_init_repo)
        source_control_menu.add_command(label="Clone Repository...", command=self._clone_repo)


        settings_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_checkbutton(
            label="Enable Code Completion",
            variable=self.autocomplete_enabled,
            command=self._toggle_autocomplete,
        )
        settings_menu.add_checkbutton(
            label="Enable Proactive Error Checking",
            variable=self.proactive_errors_enabled,
            command=self._toggle_proactive_errors,
        )
        settings_menu.add_checkbutton(
            label="Highlight Handled Exceptions",
            variable=self.highlight_handled_exceptions,
            command=self._save_settings,
        )
        settings_menu.add_separator()
        settings_menu.add_checkbutton(
            label="Autosave",
            variable=self.autosave_enabled,
            command=self._save_settings,
        )
        settings_menu.add_checkbutton(
            label="Auto Indentation",
            variable=self.autoindent_enabled,
            command=self._save_settings,
        )
        settings_menu.add_checkbutton(
            label="Syntax Tooltips",
            variable=self.tooltips_enabled,
            command=self._save_settings,
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Zoom In", command=self._zoom_in, accelerator="Ctrl++"
        )
        settings_menu.add_command(
            label="Zoom Out", command=self._zoom_out, accelerator="Ctrl+-"
        )
        settings_menu.add_command(
            label="Reset Zoom", command=self._reset_zoom, accelerator="Ctrl+0"
        )

        help_menu = tk.Menu(menubar, **menu_kwargs)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _toggle_autocomplete(self):
        if self.active_editor:
            self.active_editor.autocomplete_active = self.autocomplete_enabled.get()
        self._save_settings()

    def _toggle_proactive_errors(self):
        if self.active_editor:
            self.active_editor.set_proactive_error_checking(
                self.proactive_errors_enabled.get()
            )
        self._save_settings()

    def _create_main_content_area(self):
        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        left_notebook = ttk.Notebook(self.main_paned_window)
        self.main_paned_window.add(left_notebook, weight=1)

        # --- File Explorer Tab ---
        explorer_frame = tk.Frame(left_notebook, bg="#2B2B2B")
        self.file_explorer = FileExplorer(
            explorer_frame,
            self,
            self.workspace_root_dir,
            self._open_file_from_path,
            folder_icon=self.folder_icon,
            python_icon=self.python_logo_icon,
            git_icon=self.git_icon,
            unknown_icon=self.unknown_file_icon,
            txt_icon=self.txt_icon,
            md_icon=self.md_icon,
        )
        self.file_explorer.pack(fill="both", expand=True)
        left_notebook.add(explorer_frame, text="Explorer")

        # --- Source Control Tab ---
        sc_frame = tk.Frame(left_notebook, bg="#2B2B2B")
        self.source_control_ui = SourceControlUI(
            sc_frame,
            self, # parent_app
            self._open_file_from_path, # open_file_callback
            self.workspace_root_dir # workspace_root_dir
        )
        self.source_control_ui.pack(fill="both", expand=True)
        left_notebook.add(sc_frame, text="Source Control")

        self.right_pane = ttk.PanedWindow(self.main_paned_window, orient=tk.VERTICAL)
        self.main_paned_window.add(self.right_pane, weight=4)
        
        editor_area_frame = tk.Frame(self.right_pane, bg="#2B2B2B")
        self.right_pane.add(editor_area_frame, weight=3)
        editor_area_frame.grid_rowconfigure(1, weight=1)
        editor_area_frame.grid_columnconfigure(0, weight=1)

        self.tab_bar_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.tab_bar_frame.grid(row=0, column=0, sticky="ew")
        self.editor_content_frame = tk.Frame(editor_area_frame, bg="#2B2B2B")
        self.editor_content_frame.grid(row=1, column=0, sticky="nsew")

        output_container = tk.Frame(self.right_pane)
        self.right_pane.add(output_container, weight=1)

        self.output_notebook = ttk.Notebook(output_container)
        self.output_notebook.pack(fill="both", expand=True)

        terminal_page = tk.Frame(self.output_notebook, bg="#2B2B2B")
        terminal_page.grid_columnconfigure(0, weight=1)
        terminal_page.grid_rowconfigure(0, weight=1)
        self.terminal_content_frame = tk.Frame(terminal_page)
        self.terminal_content_frame.grid(row=0, column=0, sticky="nsew")
        self.terminal_tabs_sidebar = tk.Frame(terminal_page, bg="#2B2B2B", width=150)
        self.terminal_tabs_sidebar.grid(row=0, column=1, sticky="ns")
        self.terminal_tabs_sidebar.pack_propagate(False)
        self.add_terminal_button = tk.Button(self.terminal_tabs_sidebar, text=" New", command=self._create_new_terminal, bg="#3C3C3C", fg="white", bd=0, activebackground="#555555", font=("Segoe UI", 8), relief="flat", image=self.add_icon, compound="left", padx=5)  # type: ignore
        self.add_terminal_button.pack(side="bottom", fill="x", pady=5, padx=5)

        error_page = tk.Frame(self.output_notebook, bg="#1E1E1E")
        self.error_console = ConsoleUi(
            error_page, jump_callback=self._jump_to_error_location
        )
        self.error_console.pack(fill="both", expand=True)

        self.output_notebook.add(terminal_page, text="TERMINAL")
        self.output_notebook.add(error_page, text="PROBLEMS")

        self._create_new_terminal()  # Create the first terminal

    # --- ADD NEW STATUS BAR METHODS ---
    def _create_status_bar(self):
        """Creates the bottom status bar."""
        self.status_bar = tk.Frame(self, bg="#3C3C3C", height=22)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.status_bar.grid_propagate(False)
        
        self.git_status_label = tk.Label(self.status_bar, text="Git status...", bg="#3C3C3C", fg="white", font=("Segoe UI", 8))
        self.git_status_label.pack(side="left", padx=10)

    def update_git_status_bar(self, text: str):
        """Updates the text in the Git status bar label."""
        self.git_status_label.config(text=text)
        
    def update_git_info(self):
        """Refreshes all Git-related UI components."""
        # Check if source_control_ui is initialized before calling refresh
        if self.source_control_ui:
            self.source_control_ui.refresh()

    # --- ADD NEW GIT-RELATED MENU COMMAND WRAPPERS ---
    def _sc_refresh(self):
        if self.source_control_ui:
            self.source_control_ui.refresh()

    def _sc_commit_action(self):
        if self.source_control_ui:
            self.source_control_ui._commit_action()

    def _sc_push_action(self):
        if self.source_control_ui:
            self.source_control_ui._push_action()

    def _sc_pull_action(self):
        if self.source_control_ui:
            self.source_control_ui._pull_action()

    def _sc_init_repo(self):
        if self.source_control_ui:
            self.source_control_ui._init_repo()

    def _clone_repo(self):
        repo_url = simpledialog.askstring("Clone Repository", "Enter repository URL:", parent=self)
        if not repo_url:
            return
            
        target_dir = filedialog.askdirectory(title="Select folder to clone into", initialdir=os.path.dirname(self.workspace_root_dir))
        if not target_dir:
            return
            
        messagebox.showinfo("Cloning...", f"Cloning '{repo_url}' into '{target_dir}'. This may take a moment.")
        
        def run_clone():
            # We can't use the instance's git_logic because it's tied to a project root.
            # So we run a one-off command.
            try:
                process = subprocess.Popen(
                    ["git", "clone", repo_url, target_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                stdout, stderr = process.communicate()
                if process.returncode == 0:
                    if messagebox.askyesno("Clone Successful", "Repository cloned successfully. Open the new folder?"):
                        # This needs to run on the main thread
                        self.after(0, self._open_folder, target_dir)
                else:
                    messagebox.showerror("Clone Failed", stderr)
            except Exception as e:
                messagebox.showerror("Clone Error", str(e))
                
        threading.Thread(target=run_clone, daemon=True).start()

    def _jump_to_error_location(self, file_path, line):
        self._open_file_from_path(file_path)

        def scroll_to_line():
            if self.active_editor and self.active_editor.winfo_exists():
                self.active_editor.text_area.mark_set(tk.INSERT, f"{line}.0")
                self.active_editor.text_area.see(tk.INSERT)
                self.active_editor.text_area.focus_set()

        self.after(50, scroll_to_line)

    def _create_new_terminal(self):
        new_terminal = Terminal(
            self.terminal_content_frame,
            stdin_queue=self.stdin_queue,
            cwd=self.workspace_root_dir,
            python_executable=self.python_executable,
        )

        tab_frame = tk.Frame(self.terminal_tabs_sidebar, bg="#2B2B2B")

        icon_label = tk.Label(tab_frame, bg="#2B2B2B")
        if self.terminal_icon:
            icon_label.config(image=self.terminal_icon)
        icon_label.pack(side="left", padx=(5, 2))

        name_label = tk.Label(
            tab_frame,
            text=f"Terminal {len(self.terminals) + 1}",
            bg="#2B2B2B",
            fg="white",
            font=("Segoe UI", 9),
            anchor="w",
        )
        name_label.pack(side="left", fill="x", expand=True)
        new_terminal.display_name_widget = name_label

        close_button = tk.Button(
            tab_frame,
            text="\u2715",
            bg="#2B2B2B",
            fg="#CCCCCC",
            bd=0,
            activebackground="#E81123",
            activeforeground="white",
            relief="flat",
            command=lambda t=new_terminal: self._close_terminal(t),
        )
        close_button.pack(side="right", padx=(0, 5))
        tab_frame.pack(side="top", fill="x", pady=(1, 0), padx=2)

        for widget in [tab_frame, icon_label, name_label]:
            widget.bind(
                "<Button-1>", lambda e, t=new_terminal: self._switch_terminal(t)
            )
            widget.bind(
                "<Button-3>",
                lambda e, t=new_terminal: self._show_terminal_context_menu(e, t),
            )

        self.terminals.append(new_terminal)
        self.terminal_ui_map[new_terminal] = tab_frame
        self._switch_terminal(new_terminal)
        self.output_notebook.select(0)
        self._apply_font_size()
        return new_terminal

    def _switch_terminal(self, terminal_to_activate: Terminal):
        if self.active_terminal == terminal_to_activate:
            return

        if self.active_terminal and self.active_terminal in self.terminal_ui_map:
            self.active_terminal.pack_forget()
            self.terminal_ui_map[self.active_terminal].config(bg="#2B2B2B")
            for child in self.terminal_ui_map[self.active_terminal].winfo_children():
                child.config(bg="#2B2B2B")  # type: ignore

        self.active_terminal = terminal_to_activate
        if self.active_terminal:
            self.active_terminal.pack(fill="both", expand=True)
            if self.active_terminal in self.terminal_ui_map:
                self.terminal_ui_map[self.active_terminal].config(bg="#3C3C3C")
                for child in self.terminal_ui_map[
                    self.active_terminal
                ].winfo_children():
                    child.config(bg="#3C3C3C")  # type: ignore
            self.active_terminal.text.focus_set()

    def _close_terminal(self, terminal_to_close: Terminal):
        if len(self.terminals) <= 1:
            messagebox.showwarning(
                "Close Terminal", "Cannot close the last terminal.", parent=self
            )
            return

        was_active = self.active_terminal == terminal_to_close

        if terminal_to_close in self.terminal_ui_map:
            self.terminal_ui_map[terminal_to_close].destroy()
            del self.terminal_ui_map[terminal_to_close]

        terminal_to_close.destroy()
        self.terminals.remove(terminal_to_close)

        if was_active:
            self._switch_terminal(self.terminals[-1] if self.terminals else None)  # type: ignore

    def _show_terminal_context_menu(self, event, terminal: Terminal):
        context_menu = tk.Menu(
            self,
            tearoff=0,
            bg="#3C3C3C",
            fg="white",
            activebackground="#555555",
            activeforeground="white",
        )
        context_menu.add_command(
            label="Rename...", command=lambda: self._rename_terminal(terminal)
        )
        context_menu.add_command(
            label="Close", command=lambda: self._close_terminal(terminal)
        )
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _rename_terminal(self, terminal: Terminal):
        current_name = terminal.display_name_widget.cget("text")  # type: ignore
        new_name = simpledialog.askstring(
            "Rename Terminal", "Enter new name:", initialvalue=current_name, parent=self
        )
        if new_name and new_name.strip():
            terminal.display_name_widget.config(text=new_name.strip())  # type: ignore

    def _get_run_terminal(self) -> Terminal:
        if not self.active_terminal:
            return (
                self._create_new_terminal() if not self.terminals else self.terminals[0]
            )
        return self.active_terminal

    def _open_sandbox_if_empty(self):
        if not self.open_files:
            self._open_new_sandbox_tab()

    def _open_new_sandbox_tab(self, event=None):
        content = '# PriestyCode Sandbox\n# This is a temporary file. Save it to keep your changes.\n\nprint("Hello, Sandbox!")\n'
        self._add_new_tab(file_path="sandbox.py", content=content)

    def _check_virtual_env(self):
        found_venv = False
        for venv_name in (".venv", "venv"):
            path = os.path.join(self.workspace_root_dir, venv_name)
            if os.path.isdir(path):
                script_dir = "Scripts" if sys.platform == "win32" else "bin"
                potential_path = os.path.join(
                    path,
                    script_dir,
                    "python.exe" if sys.platform == "win32" else "python",
                )
                if os.path.exists(potential_path):
                    self.python_executable = os.path.abspath(potential_path)
                    found_venv = True
                    break

        if not found_venv:
            self.python_executable = sys.executable
            if not self.venv_warning_shown:
                self.venv_warning_shown = True
                if messagebox.askyesno(
                    "Virtual Environment Recommended",
                    "No virtual environment was found. It is highly recommended to use one.\n\nWould you like to create one now?",
                ):
                    self._create_virtual_env()

        for term in self.terminals:
            term.set_python_executable(self.python_executable)
            term.clear()
            term.show_prompt()

    def _create_virtual_env(self):
        run_terminal = self._get_run_terminal()
        run_terminal.write(
            "Creating virtual environment 'venv'... This may take a moment.\n"
        )
        self.output_notebook.select(0)
        self.update_idletasks()
        venv_dir = os.path.join(self.workspace_root_dir, "venv")
        if os.path.exists(venv_dir):
            messagebox.showwarning("Exists", "A 'venv' folder already exists.")
            return

        def create():
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", venv_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.workspace_root_dir,
                )
                self.after(0, self._check_virtual_env)
                self.after(0, self.file_explorer.populate_tree)
            except Exception as e:
                run_terminal.write(f"Failed to create venv: {e}\n", "stderr_tag")
            finally:
                self.after(0, run_terminal.show_prompt)

        threading.Thread(target=create, daemon=True).start()

    def _change_interpreter(self):
        filetypes = (
            [
                ("Python Executable", "python.exe"),
                ("Python Executable", "python"),
                ("All files", "*.*"),
            ]
            if sys.platform == "win32"
            else [("Python Executable", "python*"), ("All files", "*.*")]
        )
        new_path = filedialog.askopenfilename(
            title="Select Python Interpreter",
            initialdir=os.path.dirname(self.python_executable),
            filetypes=filetypes,
        )
        if new_path and os.path.exists(new_path):
            self.python_executable = new_path
            self.venv_warning_shown = True
            for term in self.terminals:
                term.set_python_executable(self.python_executable)
                term.clear()
                term.show_prompt()
            messagebox.showinfo(
                "Interpreter Changed",
                f"Python interpreter set to:\n{self.python_executable}",
                parent=self,
            )

    def _install_requirements(self):
        requirements_path = os.path.join(self.workspace_root_dir, "requirements.txt")
        if not os.path.exists(requirements_path):
            messagebox.showwarning(
                "Not Found",
                "No requirements.txt file found in the workspace root.",
                parent=self,
            )
            return
        run_terminal = self._get_run_terminal()
        self.output_notebook.select(0)
        self._switch_terminal(run_terminal)
        command = f'"{self.python_executable}" -m pip install -r "{requirements_path}"'
        run_terminal.write(f"Executing: {command}\n", ("info_tag",))
        self.update_idletasks()
        run_terminal._handle_shell_command(command)

    def _new_file(self, extension=".py"):
        self._add_new_tab(extension=extension)

    def _open_file(self, event=None):
        file_path = filedialog.askopenfilename(
            initialdir=self.workspace_root_dir,
            filetypes=[
                ("Python files", "*.py"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            self._open_file_from_path(file_path)

    def _open_folder(self, new_path=None):
        if not new_path:
            new_path = filedialog.askdirectory(
                title="Select Workspace Folder", initialdir=self.workspace_root_dir
            )
        if not new_path or not os.path.isdir(new_path):
            return
            
        while self.open_files:
            if not self._close_tab(0, force_ask=True):
                return
        self.workspace_root_dir, self.venv_warning_shown = new_path, False
        self.file_explorer.set_project_root(new_path)
        [term.set_cwd(new_path) for term in self.terminals]
        self._check_virtual_env()
        # ADD THIS
        self.update_git_info()
        self.title(f"PriestyCode - {os.path.basename(new_path)}")

    def _open_file_from_path(self, file_path):
        if not file_path or file_path == "N/A":
            messagebox.showerror(
                "Error",
                f"Failed to open file: No such file or directory: '{file_path}'",
            )
            return

        _, extension = os.path.splitext(file_path)
        if extension.lower() in self.BINARY_EXTENSIONS:
            messagebox.showerror(
                "Cannot Open File",
                f"The file '{os.path.basename(file_path)}' appears to be a binary file.",
            )
            return
        if os.path.basename(file_path) == "sandbox.py":
            for open_path in self.open_files:
                if os.path.basename(open_path) == "sandbox.py":
                    self._switch_to_tab(self.open_files.index(open_path))
                    return
            self._open_new_sandbox_tab()
            return
        if file_path in self.open_files:
            self._switch_to_tab(self.open_files.index(file_path))
        else:
            self._add_new_tab(file_path=file_path)

    def _add_new_tab(self, file_path=None, content="", extension=".py"):
        editor_frame = tk.Frame(self.editor_content_frame, bg="#2B2B2B")
        editor = CodeEditor(
            editor_frame,
            error_console=self.error_console,
            autocomplete_icons={
                "snippet": self.snippet_icon,
                "keyword": self.keyword_icon,
                "function": self.function_icon,
                "variable": self.variable_icon,
                "class": self.function_icon,
            },
            autoindent_var=self.autoindent_enabled,
            tooltips_var=self.tooltips_enabled,
        )
        editor.pack(fill="both", expand=True)

        is_sandbox = file_path == "sandbox.py"
        is_untitled = False
        if file_path and not is_sandbox and not file_path.startswith("Untitled-"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
                editor_frame.destroy()
                return
        elif not file_path or file_path.startswith("Untitled-"):
            is_untitled = True
            count = 1
            untitled_name = f"Untitled-{count}{extension}"
            while untitled_name in self.open_files:
                count += 1
                untitled_name = f"Untitled-{count}{extension}"
            file_path = untitled_name

        editor.set_file_path(file_path)
        editor.text_area.insert("1.0", content)
        editor.text_area.edit_modified(is_sandbox or is_untitled)
        self.after(50, editor._on_content_changed)
        editor.text_area.bind("<<Change>>", self._schedule_autosave)
        self.after(1, lambda: editor.set_font_size(self.font_size.get()))

        tab = tk.Frame(self.tab_bar_frame, bg="#3C3C3C")
        tab.pack(side="left", fill="y", padx=(0, 1))
        icon, new_index = self._get_icon_for_file(file_path), len(self.open_files)
        icon_label = (
            tk.Label(tab, image=icon, bg="#3C3C3C")
            if icon
            else tk.Label(tab, bg="#3C3C3C")
        )
        icon_label.pack(side="left", padx=(5, 2), pady=2)
        text_label = tk.Label(
            tab,
            text=os.path.basename(file_path),
            fg="white",
            bg="#3C3C3C",
            font=("Segoe UI", 9),
        )
        text_label.pack(side="left", padx=(0, 5), pady=2)
        close_button = tk.Button(
            tab,
            text="\u2715",
            bg="#3C3C3C",
            fg="white",
            bd=0,
            relief="flat",
            activebackground="#E81123",
            activeforeground="white",
            font=("Segoe UI", 8, "bold"),
        )
        close_button.pack(side="right", padx=(5, 5), pady=2)

        tab.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        icon_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        text_label.bind("<Button-1>", lambda e, i=new_index: self._switch_to_tab(i))
        close_button.config(command=lambda i=new_index: self._close_tab(i))

        self.open_files.append(file_path)
        self.editor_widgets.append(editor_frame)
        self.tab_widgets.append(tab)
        self._switch_to_tab(new_index)

    def _switch_to_tab(self, index: int):
        if not (0 <= index < len(self.tab_widgets)):
            return
        if (
            self.active_editor
            and self.current_tab_index >= 0
            and self.current_tab_index < len(self.editor_widgets)
        ):
            self.editor_widgets[self.current_tab_index].pack_forget()
            self._set_tab_appearance(
                self.tab_widgets[self.current_tab_index], active=False
            )

        self.current_tab_index, self.current_open_file = index, self.open_files[index]
        new_editor_frame = self.editor_widgets[index]
        new_editor_frame.pack(fill="both", expand=True)
        self.active_editor = cast(CodeEditor, new_editor_frame.winfo_children()[0])
        self.active_editor.autocomplete_active = self.autocomplete_enabled.get()
        self.active_editor.set_proactive_error_checking(
            self.proactive_errors_enabled.get()
        )
        self._set_tab_appearance(self.tab_widgets[index], active=True)
        self.active_editor.text_area.focus_set()
        self._update_file_header(self.current_open_file)

    def _set_tab_appearance(self, tab_widget, active):
        bg = "#2B2B2B" if active else "#3C3C3C"
        tab_widget.config(bg=bg)
        for child in tab_widget.winfo_children():
            if isinstance(child, (tk.Label, tk.Frame)):
                child.config(bg=bg)

    def _close_tab(self, index_to_close, force_ask=False, force_close=False) -> bool:
        if not (0 <= index_to_close < len(self.open_files)):
            return False
        file_path_to_close = self.open_files[index_to_close]
        is_sandbox = os.path.basename(file_path_to_close) == "sandbox.py"
        editor_to_close = cast(
            CodeEditor, self.editor_widgets[index_to_close].winfo_children()[0]
        )

        if (
            not force_close
            and editor_to_close.text_area.edit_modified()
            and not is_sandbox
        ):
            response = messagebox.askyesnocancel(
                "Save on Close",
                f"Save changes to {os.path.basename(file_path_to_close)}?",
            )
            if response is None:
                return False
            if response and not self._save_file(index=index_to_close):
                return False

        self.tab_widgets.pop(index_to_close).destroy()
        self.editor_widgets.pop(index_to_close).destroy()
        self.open_files.pop(index_to_close)
        for i, tab in enumerate(self.tab_widgets):
            close_button = cast(tk.Button, tab.winfo_children()[-1])
            close_button.config(command=lambda new_i=i: self._close_tab(new_i))
            for child in tab.winfo_children()[:-1]:
                child.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))
            tab.bind("<Button-1>", lambda e, new_i=i: self._switch_to_tab(new_i))

        if not self.open_files:
            self.active_editor = None
            self.current_tab_index = -1
            self._update_file_header(None)
        else:
            self._switch_to_tab(max(0, min(index_to_close, len(self.open_files) - 1)))
        return True

    def _update_file_header(self, file_path):
        icon = self._get_icon_for_file(file_path)
        if icon:
            self.file_type_icon_label.config(image=icon)
        self.file_name_label.config(
            text=os.path.basename(file_path) if file_path else "No File Open"
        )

    def _get_icon_for_file(self, file_path):
        if not file_path:
            return self.unknown_file_icon
        ext = os.path.splitext(file_path)[1]
        if ext == ".py":
            return self.python_logo_icon
        if ext == ".txt":
            return self.txt_icon
        if ext == ".md":
            return self.md_icon
        return self.unknown_file_icon

    def _save_file(self, event=None, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)):
            return False
        file_path, editor = self.open_files[idx], cast(
            CodeEditor, self.editor_widgets[idx].winfo_children()[0]
        )
        if file_path.startswith("Untitled-") or file_path == "sandbox.py":
            return self._save_file_as(index=idx)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(editor.text_area.get("1.0", "end-1c"))
            editor.text_area.edit_modified(False)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _save_file_as(self, event=None, index=None) -> bool:
        idx = self.current_tab_index if index is None else index
        if not (0 <= idx < len(self.open_files)):
            return False
        old_path = self.open_files[idx]
        initial_file = (
            os.path.basename(old_path) if old_path != "sandbox.py" else "sandbox.py"
        )
        new_path = filedialog.asksaveasfilename(
            initialdir=self.workspace_root_dir,
            initialfile=initial_file,
            defaultextension=".py",
            filetypes=[("Python", "*.py"), ("All files", "*.*")],
        )
        if not new_path:
            return False
        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(
                    cast(
                        CodeEditor, self.editor_widgets[idx].winfo_children()[0]
                    ).text_area.get("1.0", "end-1c")
                )
            if not old_path.startswith("Untitled-"):
                self.handle_file_rename(old_path, new_path)
            else:
                self.open_files[idx], editor = new_path, cast(
                    CodeEditor, self.editor_widgets[idx].winfo_children()[0]
                )
                editor.set_file_path(new_path)
                editor.text_area.edit_modified(False)
                cast(tk.Label, self.tab_widgets[idx].winfo_children()[1]).config(
                    text=os.path.basename(new_path)
                )
                if idx == self.current_tab_index:
                    self._update_file_header(new_path)
            self.file_explorer.populate_tree()
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")
            return False

    def _schedule_autosave(self, event=None):
        if self.autosave_timer:
            self.after_cancel(self.autosave_timer)
        if self.autosave_enabled.get():
            self.autosave_timer = self.after(2000, self._perform_autosave)

    def _perform_autosave(self):
        if self.active_editor and self.active_editor.text_area.edit_modified():
            self._save_file()

    def _run_code(self, event=None):
        if self.is_running:
            self._stop_code()
            return
        if not self.active_editor or not self.current_open_file:
            messagebox.showerror("No File", "Please open a file to run.")
            return
        is_sandbox = self.current_open_file == "sandbox.py"
        if not is_sandbox and (
            self.current_open_file.startswith("Untitled-")
            or self.active_editor.text_area.edit_modified()
        ):
            if not self._save_file():
                messagebox.showwarning(
                    "Run Cancelled", "File must be saved before running."
                )
                return

        run_terminal = self._get_run_terminal()
        self.active_editor.clear_error_highlight()
        self.error_console.clear(runtime_only=True)
        run_terminal.clear()

        self.stderr_buffer, self.stdout_buffer, self.is_running = "", "", True
        self._update_run_stop_button_state()
        run_terminal.set_interactive_mode(True)
        self.output_notebook.select(0)
        self._switch_terminal(run_terminal)
        file_to_run = self.current_open_file
        if is_sandbox:
            try:
                temp_file = tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".py", delete=False, encoding="utf-8"
                )
                temp_file.write(self.active_editor.text_area.get("1.0", "end-1c"))
                temp_file.close()
                self.temp_run_file = temp_file.name
                file_to_run = self.temp_run_file
            except Exception as e:
                messagebox.showerror(
                    "Sandbox Error", f"Could not create temporary file for sandbox: {e}"
                )
                self._cleanup_after_run()
                return
        threading.Thread(
            target=self._execute_in_thread, args=(file_to_run,), daemon=True
        ).start()

    def _start_process_and_threads(self, executable_path, file_path_to_run):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONUTF8"] = "1"
        try:
            cwd = (
                self.workspace_root_dir
                if self.temp_run_file
                else os.path.dirname(file_path_to_run)
            )
            self.process = subprocess.Popen(
                [executable_path, file_path_to_run],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                cwd=cwd,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
            stdout_thread = threading.Thread(
                target=self._read_stream_to_queue,
                args=(self.process.stdout, "stdout_tag"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self._read_stream_to_queue,
                args=(self.process.stderr, "stderr_tag"),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()
            threading.Thread(target=self._write_to_stdin, daemon=True).start()
            threading.Thread(
                target=self._monitor_process,
                args=(stdout_thread, stderr_thread),
                daemon=True,
            ).start()
        except Exception as e:
            self.output_queue.put(
                (PROCESS_ERROR_SIGNAL, f"Failed to start process: {e}")
            )

    def _monitor_process(
        self, stdout_thread: threading.Thread, stderr_thread: threading.Thread
    ):
        if self.process:
            return_code = self.process.wait()
            stdout_thread.join()
            stderr_thread.join()
            self.output_queue.put((PROCESS_END_SIGNAL, return_code))

    def _execute_in_thread(self, file_to_run_override=None):
        file_path = file_to_run_override or self.current_open_file
        if not file_path:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, "No file to run."))
            return
        try:
            self._start_process_and_threads(self.python_executable, file_path)
        except Exception as e:
            self.output_queue.put((PROCESS_ERROR_SIGNAL, str(e)))

    def _read_stream_to_queue(self, stream, tag):
        try:
            if stream:
                for char in iter(lambda: stream.read(1), ""):
                    self.output_queue.put((char, tag))
        finally:
            if stream:
                stream.close()

    def _write_to_stdin(self):
        while self.process and self.process.poll() is None:
            try:
                if self.process.stdin:
                    self.process.stdin.write(self.stdin_queue.get(timeout=0.5))
                    self.process.stdin.flush()
            except queue.Empty:
                continue
            except (IOError, ValueError):
                break

    def _stop_code(self, event=None):
        if not self.process or self.process.poll() is not None:
            self._cleanup_after_run()
            return
        run_terminal = self._get_run_terminal()
        if run_terminal:
            run_terminal.set_interactive_mode(False)
        while not self.stdin_queue.empty():
            try:
                self.stdin_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
            if run_terminal:
                run_terminal.write("\n--- Process terminated ---\n", ("stderr_tag",))
        except Exception:
            self.process.kill()
            if run_terminal:
                run_terminal.write("\n--- Process Killed ---\n", ("stderr_tag",))
        self.process = None
        self._cleanup_after_run()
        if run_terminal:
            run_terminal.show_prompt()

    def _cleanup_after_run(self):
        self.is_running = False
        self._update_run_stop_button_state()
        if self.temp_run_file:
            try:
                os.remove(self.temp_run_file)
            except OSError as e:
                print(f"Error cleaning up temp file: {e}")
            finally:
                self.temp_run_file = None

    def _update_run_stop_button_state(self):
        icon, cmd, text = (
            (self.pause_icon, self._stop_code, "Stop")
            if self.is_running
            else (self.run_icon, self._run_code, "Run")
        )
        self.run_stop_button.config(command=cmd)
        if icon:
            self.run_stop_button.config(image=icon)
        else:
            self.run_stop_button.config(text=text)

    def _open_find_replace_dialog(self, event=None):
        if not self.active_editor:
            return
        if self.find_replace_dialog and self.find_replace_dialog.winfo_exists():
            self.find_replace_dialog.lift()
        else:
            self.find_replace_dialog = FindReplaceDialog(self, self.active_editor)

    def _show_about(self):
        messagebox.showinfo(
            "About PriestyCode",
            "PriestyCode v1.0.0\nA simple, extensible IDE.\n\nCreated with Python and Tkinter.",
        )

    def _clear_active_output_view(self):
        try:
            if (
                self.output_notebook.tab(self.output_notebook.select(), "text")
                == "TERMINAL"
            ):
                if self.active_terminal and hasattr(self.active_terminal, "clear"):
                    self.active_terminal.clear()
                if self.active_terminal and not self.active_terminal.interactive_mode:
                    self.active_terminal.show_prompt()
            elif (
                self.output_notebook.tab(self.output_notebook.select(), "text")
                == "PROBLEMS"
            ):
                if hasattr(self.error_console, "clear"):
                    self.error_console.clear()
        except tk.TclError:
            pass

    def _open_external_terminal(self):
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    f'start cmd /K "cd /d {self.workspace_root_dir}"', shell=True
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal", self.workspace_root_dir])
            else:
                try:
                    subprocess.Popen(
                        [
                            "gnome-terminal",
                            "--working-directory",
                            self.workspace_root_dir,
                        ]
                    )
                except FileNotFoundError:
                    try:
                        subprocess.Popen(
                            ["konsole", "--workdir", self.workspace_root_dir]
                        )
                    except FileNotFoundError:
                        subprocess.Popen(
                            ["xterm", "-e", f'cd "{self.workspace_root_dir}"; bash']
                        )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open external terminal: {e}")

    def _process_output_queue(self):
        run_terminal = self._get_run_terminal()
        try:
            while not self.output_queue.empty():
                char, tag = self.output_queue.get_nowait()
                if char == PROCESS_END_SIGNAL:
                    if isinstance(tag, int):
                        full_traceback = self.stderr_buffer + self.stdout_buffer
                        # Improved check for runtime errors vs handled exceptions
                        if tag != 0 and (
                            "Error" in self.stderr_buffer
                            or "Exception" in self.stderr_buffer
                        ):
                            self._handle_error_output(
                                self.stderr_buffer, "Runtime Error", "runtime"
                            )
                        elif (
                            tag == 0
                            and "Traceback" in full_traceback
                            and self.highlight_handled_exceptions.get()
                        ):
                            self._handle_error_output(
                                full_traceback, "Handled Exception", "handled"
                            )
                        elif tag != 0 and self.stderr_buffer.strip():
                            self.error_console.display_errors(
                                [
                                    {
                                        "title": "Execution Error",
                                        "details": self.stderr_buffer.strip(),
                                        "file_path": "N/A",
                                        "line": 1,
                                        "col": 1,
                                    }
                                ]
                            )
                            self.output_notebook.select(1)
                    self._cleanup_after_run()
                    run_terminal.set_interactive_mode(False)
                    self.stderr_buffer, self.stdout_buffer = "", ""
                elif char == PROCESS_ERROR_SIGNAL:
                    self._cleanup_after_run()
                    run_terminal.set_interactive_mode(False)
                    self.error_console.display_errors(
                        [
                            {
                                "title": "Execution Error",
                                "details": str(tag),
                                "file_path": "N/A",
                                "line": 1,
                                "col": 1,
                            }
                        ]
                    )
                    self.output_notebook.select(1)
                else:
                    if run_terminal:
                        run_terminal.write(char, (str(tag),))
                    if tag == "stderr_tag":
                        self.stderr_buffer += char
                    elif tag == "stdout_tag":
                        self.stdout_buffer += char
        except queue.Empty:
            pass
        finally:
            self.after(50, self._process_output_queue)

    def _handle_error_output(self, error_text, default_title, highlight_type):
        full_error_text = re.sub(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", error_text
        ).strip()
        traceback_matches = list(
            re.finditer(r'File "(.*?)", line (\d+)', full_error_text)
        )

        if traceback_matches:
            file_path, line_num_str = traceback_matches[-1].groups()
            line_num = int(line_num_str)
            is_temp_file = self.temp_run_file and os.path.normcase(
                file_path
            ) == os.path.normcase(self.temp_run_file)
            last_line = full_error_text.strip().split("\n")[-1]
            error_title = last_line if ": " in last_line else default_title

            editor_to_highlight, error_file_path_for_panel = None, file_path

            if is_temp_file:
                error_file_path_for_panel = "sandbox.py"  # For display
                for i, open_path in enumerate(self.open_files):
                    if open_path == "sandbox.py":
                        editor_to_highlight = cast(
                            CodeEditor, self.editor_widgets[i].winfo_children()[0]
                        )
                        break
            else:
                norm_error_path = os.path.normcase(os.path.abspath(file_path))
                for i, open_path in enumerate(self.open_files):
                    if (
                        open_path
                        and os.path.normcase(os.path.abspath(open_path))
                        == norm_error_path
                    ):
                        editor_to_highlight = cast(
                            CodeEditor, self.editor_widgets[i].winfo_children()[0]
                        )
                        break

            if editor_to_highlight:
                method_name = (
                    "highlight_handled_exception"
                    if highlight_type == "handled"
                    else "highlight_runtime_error"
                )
                highlight_method = getattr(editor_to_highlight, method_name, None)
                if highlight_method:
                    self.after(0, highlight_method, line_num, full_error_text)

            error_info = [
                {
                    "title": error_title,
                    "details": full_error_text,
                    "file_path": error_file_path_for_panel,
                    "line": line_num,
                    "col": 1,
                }
            ]
            self.error_console.display_errors(error_info, runtime_only=True)
            self.output_notebook.select(1)
        else:
            self.error_console.display_errors(
                [
                    {
                        "title": default_title,
                        "details": full_error_text,
                        "file_path": "N/A",
                        "line": 1,
                        "col": 1,
                    }
                ]
            )
            self.output_notebook.select(1)

    def run(self):
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.mainloop()

    def run_file_from_explorer(self, path):
        self._open_file_from_path(path)
        self.after(100, self._run_code)

    def handle_file_rename(self, old_path, new_path):
        old_path_norm = os.path.normcase(old_path)
        if os.path.isdir(new_path):
            for i, open_file in enumerate(list(self.open_files)):
                if os.path.normcase(open_file).startswith(old_path_norm + os.sep):
                    self.handle_file_rename(
                        open_file, new_path + open_file[len(old_path) :]
                    )
            return
        if old_path in self.open_files:
            idx = self.open_files.index(old_path)
            self.open_files[idx] = new_path
            editor = cast(CodeEditor, self.editor_widgets[idx].winfo_children()[0])
            editor.set_file_path(new_path)
            cast(tk.Label, self.tab_widgets[idx].winfo_children()[1]).config(
                text=os.path.basename(new_path)
            )
            if idx == self.current_tab_index:
                self._update_file_header(new_path)

    def handle_file_delete(self, path: str):
        path_norm = os.path.normcase(path)
        for open_file in list(self.open_files):
            if os.path.normcase(open_file).startswith(path_norm):
                self._close_tab(self.open_files.index(open_file), force_close=True)

    def _move_active_file(self):
        if not self.current_open_file or not os.path.exists(self.current_open_file):
            messagebox.showinfo("Move File", "Open a saved file to move it.")
            return
        self.file_explorer.move_item(self.current_open_file)

    def _rename_active_file(self):
        if not self.current_open_file or not os.path.exists(self.current_open_file):
            messagebox.showinfo(
                "Rename File", "Open a saved file to rename it.", parent=self
            )
            return
        self.file_explorer._rename_item(self.current_open_file)

    def _duplicate_active_file(self):
        if (
            not self.active_editor
            or not self.current_open_file
            or not os.path.exists(self.current_open_file)
        ):
            messagebox.showinfo("Duplicate File", "An active, saved file must be open.")
            return
        base, ext = os.path.splitext(self.current_open_file)
        new_path_suggestion = f"{base}_copy{ext}"
        new_path = filedialog.asksaveasfilename(
            title="Duplicate As...",
            initialfile=os.path.basename(new_path_suggestion),
            initialdir=os.path.dirname(self.current_open_file),
            defaultextension=ext,
            filetypes=[("All files", "*.*")],
        )
        if not new_path:
            return
        try:
            shutil.copy(self.current_open_file, new_path)
            self.file_explorer.populate_tree()
            self._open_file_from_path(new_path)
        except Exception as e:
            messagebox.showerror("Duplicate Failed", f"Could not duplicate file: {e}")

    def _bind_shortcuts(self):
        self.bind_all("<Control-o>", self._open_file)
        self.bind_all("<Control-s>", self._save_file)
        self.bind_all("<Control-S>", self._save_file_as)
        self.bind_all("<Control-f>", self._open_find_replace_dialog)
        self.bind_all("<F5>", self._run_code)
        self.bind_all("<Control-F2>", self._stop_code)
        self.bind_all("<Control-z>", self._handle_undo)
        self.bind_all("<Control-y>", self._handle_redo)
        if sys.platform != "darwin":
            self.bind_all("<Control-Shift-Z>", self._handle_redo)
        self.bind_all("<F11>", lambda e: self._toggle_fullscreen_event())
        self.bind_all("<Escape>", lambda e: self._escape_fullscreen_event())
        self.bind_all("<Control-plus>", self._zoom_in)
        self.bind_all("<Control-equal>", self._zoom_in)
        self.bind_all("<Control-minus>", self._zoom_out)
        self.bind_all("<Control-0>", self._reset_zoom)
        self.bind_all("<Control-MouseWheel>", self._handle_zoom_scroll)

    def _handle_undo(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            try:
                widget.edit_undo()
            except tk.TclError:
                pass
        return "break"

    def _handle_redo(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            try:
                widget.edit_redo()
            except tk.TclError:
                pass
        return "break"

    def _on_closing(self):
        self._save_settings()
        if self.is_running:
            self._stop_code()
        while self.open_files:
            if not self._close_tab(0, force_ask=True):
                return
        self.destroy()

    def _open_new_window(self):
        subprocess.Popen([sys.executable, sys.argv[0]])

    def _toggle_fullscreen(self, event=None):
        self.attributes("-fullscreen", self.fullscreen_var.get())

    def _toggle_fullscreen_event(self, event=None):
        self.fullscreen_var.set(not self.fullscreen_var.get())
        self._toggle_fullscreen()

    def _escape_fullscreen_event(self, event=None):
        if self.fullscreen_var.get():
            self.fullscreen_var.set(False)
            self._toggle_fullscreen()

    def _reset_layout(self, event=None):
        self.update_idletasks()
        try:
            self.main_paned_window.sash_place(
                0, int(self.main_paned_window.winfo_width() * 0.2), 0
            )
            self.right_pane.sash_place(0, 0, int(self.right_pane.winfo_height() * 0.7))
        except tk.TclError:
            self.after(100, self._reset_layout)

    def _zoom_in(self, event=None):
        self.font_size.set(min(30, self.font_size.get() + 1))
        self._apply_font_size()
        return "break"

    def _zoom_out(self, event=None):
        self.font_size.set(max(6, self.font_size.get() - 1))
        self._apply_font_size()
        return "break"

    def _reset_zoom(self, event=None):
        self.font_size.set(10)
        self._apply_font_size()
        return "break"

    def _handle_zoom_scroll(self, event):
        if isinstance(self.focus_get(), tk.Text):
            if event.delta > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            return "break"

    def _apply_font_size(self):
        new_size = self.font_size.get()
        for editor_frame in self.editor_widgets:
            cast(CodeEditor, editor_frame.winfo_children()[0]).set_font_size(new_size)
        for term in self.terminals:
            term.text.config(font=("Consolas", new_size))
        # Update the treeview font size in the console
        self.style.configure("Treeview", rowheight=int(new_size * 2.2))
        self.style.configure("Treeview.Heading", font=("Segoe UI", new_size, "bold"))
        self.style.configure("Treeview", font=("Segoe UI", new_size))
        self._save_settings()


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
        tk.Label(self, text="Find:", bg="#3C3C3C", fg="white").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.find_entry = tk.Entry(
            self, bg="#2B2B2B", fg="white", insertbackground="white"
        )
        self.find_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(self, text="Replace:", bg="#3C3C3C", fg="white").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.replace_entry = tk.Entry(
            self, bg="#2B2B2B", fg="white", insertbackground="white"
        )
        self.replace_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        button_frame = tk.Frame(self, bg="#3C3C3C")
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        btn_kwargs = {
            "bg": "#555555",
            "fg": "white",
            "bd": 1,
            "relief": "solid",
            "padx": 5,
            "pady": 2,
        }
        tk.Button(
            button_frame, text="Find Next", command=self.find_next, **btn_kwargs
        ).pack(side="left", padx=5)
        tk.Button(
            button_frame, text="Replace", command=self.replace, **btn_kwargs
        ).pack(side="left", padx=5)
        tk.Button(
            button_frame, text="Replace All", command=self.replace_all, **btn_kwargs
        ).pack(side="left", padx=5)
        self.grid_columnconfigure(1, weight=1)
        self.find_entry.focus_set()

    def find_next(self):
        find_term = self.find_entry.get()
        if not find_term:
            return
        start_pos = self.text_area.index(tk.INSERT)
        match_pos = self.text_area.search(find_term, start_pos, stopindex=tk.END)
        if not match_pos:
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
        find_term, replace_term = self.find_entry.get(), self.replace_entry.get()
        if not find_term:
            return
        selection = self.text_area.tag_ranges("sel")
        if selection:
            start, end = selection
            if self.text_area.get(start, end) == find_term:
                self.text_area.delete(start, end)
                self.text_area.insert(start, replace_term)
        self.find_next()

    def replace_all(self):
        find_term, replace_term = self.find_entry.get(), self.replace_entry.get()
        if not find_term:
            return
        content = self.text_area.get("1.0", tk.END)
        new_content, replacements = content.replace(
            find_term, replace_term
        ), content.count(find_term)
        if content != new_content:
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", new_content)
            messagebox.showinfo(
                "Replace All", f"Replaced {replacements} occurrence(s).", parent=self
            )
        else:
            messagebox.showinfo("Replace All", "No occurrences found.", parent=self)

    def close_dialog(self):
        self.text_area.tag_remove("sel", "1.0", tk.END)
        self.destroy()