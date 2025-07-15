import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import os
import subprocess
import threading
from typing import List, Tuple, Dict, Callable, Optional, Any
import re
import shlex

# ======================================================================================
# 1. STYLING AND THEME
# ======================================================================================
class StyleManager:
    """Manages the visual theme and styling for the application."""
    def __init__(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # --- Color Palette ---
        self.COLOR_BG = "#2B2B2B"
        self.COLOR_BG_LIGHT = "#3C3F41"
        self.COLOR_BG_DARK = "#252526"
        self.COLOR_FG = "#D4D4D4"
        self.COLOR_ACCENT = "#007ACC"
        self.COLOR_ACCENT_LIGHT = "#094771"
        self.COLOR_GREEN = "#7BC672"
        self.COLOR_RED = "#F14C4C"
        self.COLOR_BLUE = "#6CB2F1"
        self.COLOR_BORDER = "#555555"
        self.COLOR_ORANGE = "#D18616"
        self.COLOR_CONFLICT = "#E06C75" # Color for conflict section

        # --- Fonts ---
        self.FONT_UI = ("Segoe UI", 10)
        self.FONT_CODE = ("Consolas", 10)

        self.configure_styles()

    def configure_styles(self):
        """Applies the theme to all ttk widgets."""
        self.style.configure('.',
                             background=self.COLOR_BG,
                             foreground=self.COLOR_FG,
                             font=self.FONT_UI,
                             borderwidth=0,
                             relief="flat")
        
        self.style.configure("Treeview",
                             background=self.COLOR_BG_DARK,
                             foreground=self.COLOR_FG,
                             fieldbackground=self.COLOR_BG_DARK,
                             rowheight=25)
        self.style.map("Treeview", background=[('selected', self.COLOR_ACCENT_LIGHT)])
        self.style.configure("Treeview.Heading",
                             background=self.COLOR_BG_LIGHT,
                             foreground=self.COLOR_FG,
                             relief="flat",
                             font=(self.FONT_UI[0], self.FONT_UI[1], 'bold'))
        self.style.map("Treeview.Heading",
                       background=[('active', self.COLOR_BORDER)])

        self.style.configure("TPanedwindow", background=self.COLOR_BG)
        self.style.configure("TPanedwindow.Sash", background=self.COLOR_BG_LIGHT, sashthickness=6)

        self.style.configure("TScrollbar",
                             gripcount=0,
                             background=self.COLOR_BG_LIGHT,
                             darkcolor=self.COLOR_BG_DARK,
                             lightcolor=self.COLOR_BG_LIGHT,
                             troughcolor=self.COLOR_BG,
                             bordercolor=self.COLOR_BG,
                             arrowcolor=self.COLOR_FG)
        self.style.map('TScrollbar', background=[('active', self.COLOR_BORDER)])

        self.style.configure("TFrame", background=self.COLOR_BG)
        self.style.configure("Header.TFrame", background=self.COLOR_BG_LIGHT)
        
        self.style.configure("TNotebook", background=self.COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab",
                             background=self.COLOR_BG_LIGHT,
                             foreground=self.COLOR_FG,
                             padding=[8, 4],
                             borderwidth=0)
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.COLOR_ACCENT_LIGHT),
                                   ("active", self.COLOR_BORDER)])

# ======================================================================================
# 2. HELPER DIALOGS AND WIDGETS
# ======================================================================================
class Tooltip:
    """Creates a tooltip for a given widget."""
    def __init__(self, widget, text, header=""):
        self.widget = widget
        self.text = text
        self.header = header
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        frame = tk.Frame(self.tooltip_window, background="#3C3F41", relief='solid', borderwidth=1)
        frame.pack()
        
        if self.header:
             header_label = tk.Label(frame, text=self.header, justify='left',
                             background="#45494B", relief='flat', borderwidth=0,
                             font=("Segoe UI", 10, "bold"), foreground="#D4D4D4")
             header_label.pack(fill='x', ipadx=5, ipady=2)

        label = tk.Label(frame, text=self.text, justify='left',
                         background="#3C3F41", relief='flat', borderwidth=0,
                         font=("Segoe UI", 9, "normal"), foreground="#D4D4D4", wraplength=400)
        label.pack(ipadx=5, ipady=5)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class DetailedErrorDialog(tk.Toplevel):
    """A dialog for showing detailed, scrollable error messages with modern styling."""
    def __init__(self, parent, title, details):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.geometry("600x400")
        
        sm = StyleManager()
        self.configure(bg=sm.COLOR_BG)

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        text_area = scrolledtext.ScrolledText(main_frame, wrap="word", bg=sm.COLOR_BG_DARK, fg=sm.COLOR_FG, font=sm.FONT_CODE, relief="flat", borderwidth=1)
        text_area.pack(fill="both", expand=True, padx=0, pady=(0, 10))
        text_area.insert("1.0", details)
        text_area.config(state="disabled")

        ok_button = ttk.Button(main_frame, text="OK", command=self.destroy, style="Accent.TButton")
        ok_button.pack()
        self.grab_set()

class RemoteDialog(simpledialog.Dialog):
    """A dialog to select a Git remote."""
    def __init__(self, parent, title, remotes):
        self.remotes = remotes
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        self.sm = StyleManager()
        master.configure(bg=self.sm.COLOR_BG)
        ttk.Label(master, text="Multiple remotes found. Please select one:", background=self.sm.COLOR_BG, foreground=self.sm.COLOR_FG).pack(pady=5)
        self.listbox = tk.Listbox(master, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, selectbackground=self.sm.COLOR_ACCENT_LIGHT, bd=0, highlightthickness=0)
        self.listbox.pack(padx=10, pady=10, fill="both", expand=True)
        for remote in self.remotes:
            self.listbox.insert(tk.END, remote)
        self.listbox.selection_set(0)
        return self.listbox

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def apply(self):
        selected_indices = self.listbox.curselection()
        if selected_indices:
            self.result = self.listbox.get(selected_indices[0])

# ======================================================================================
# 3. GIT BACKEND LOGIC
# ======================================================================================
class GitLogic:
    """Handles all backend Git command execution and parsing."""
    def __init__(self, project_root_callback: Callable[[], str]):
        self.get_project_root = project_root_callback

    def _run_command(self, command: List[str]) -> Tuple[int, str, str]:
        """Runs a Git command and returns its return code, stdout, and stderr."""
        project_root = self.get_project_root()
        if not project_root or not os.path.isdir(project_root):
            return -1, "", f"Invalid project root: {project_root}"
        try:
            process = subprocess.Popen(
                ["git"] + command,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8-sig',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout.strip(), stderr.strip()
        except FileNotFoundError:
            return -1, "", "Git not found. Please ensure Git is installed and in your system's PATH."
        except Exception as e:
            return -1, "", str(e)
        
    def get_file_bytes_for_stage(self, filepath: str, stage: int) -> Tuple[bool, bytes]:
        """Gets the raw byte content of a file from a specific index stage."""
        project_root = self.get_project_root()
        if not project_root or not os.path.isdir(project_root):
            return False, b""
        try:
            process = subprocess.Popen(
                ["git", "show", f":{stage}:{filepath}"],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout_bytes, _ = process.communicate()
            return process.returncode == 0, stdout_bytes
        except Exception:
            return False, b""

    def run_arbitrary_command(self, command_str: str) -> Tuple[bool, str]:
        """Runs a raw git command string."""
        try:
            command_parts = shlex.split(command_str)
        except ValueError as e:
            return False, f"Error parsing command: {e}"
            
        rc, stdout, stderr = self._run_command(command_parts)
        return rc == 0, (f"$ git {command_str}\n" + stdout + "\n" + stderr).strip()

    def is_git_repo(self) -> bool:
        project_root = self.get_project_root()
        return bool(project_root and os.path.isdir(os.path.join(project_root, '.git')))

    def get_status(self) -> Dict[str, str]:
        rc, stdout, _ = self._run_command(["status", "--porcelain=v1", "-u"])
        if rc != 0: return {}
        status_dict = {}
        for line in stdout.splitlines():
            if line:
                status, filepath = line[:2], line[3:]
                filepath = filepath.strip().replace('"', '')
                if '->' in filepath: # Handle renamed files
                    filepath = filepath.split(' -> ')[1]
                status_dict[filepath] = status
        return status_dict
    
    def get_file_content_for_stage(self, filepath: str, stage: int) -> Tuple[bool, str]:
        """Gets the content of a file from a specific index stage."""
        # Stages: 1=base, 2=ours, 3=theirs
        rc, stdout, stderr = self._run_command(["show", f":{stage}:{filepath}"])
        return rc == 0, stdout if rc == 0 else stderr

    def get_diff(self, filepath: str, is_staged: bool = False) -> Tuple[bool, str]:
        command = ["diff", "--patch-with-raw"]
        if is_staged: command.append("--staged")
        command.extend(["--", filepath])
        rc, stdout, stderr = self._run_command(command)
        return rc == 0, stdout if rc == 0 else stderr

    def get_commit_details(self, commit_hash: str) -> Tuple[bool, str]:
        """Gets the full details and diff for a single commit."""
        command = ["show", "--patch-with-raw", commit_hash]
        rc, stdout, stderr = self._run_command(command)
        return rc == 0, stdout if rc == 0 else stderr

    def get_log_for_graph(self) -> Tuple[bool, str]:
        log_format = "%H|%P|%an|%ar|%d|%s"
        rc, stdout, stderr = self._run_command(["log", "--all", f"--pretty=format:{log_format}", "-n", "500", "--date-order", "--color=never", "--decorate=full"])
        return rc == 0, stdout if rc == 0 else stderr

    def get_branches(self) -> Tuple[bool, List[str], Optional[str]]:
        rc, stdout, stderr = self._run_command(["branch", "-a"])
        if rc != 0: return False, [], None
        branches, current_branch = [], None
        for line in stdout.splitlines():
            branch_name = line.strip()
            if branch_name.startswith("* "):
                branch_name = branch_name[2:]
                current_branch = branch_name
            branches.append(branch_name)
        return True, branches, current_branch

    def switch_branch(self, branch_name: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["checkout", branch_name])
        return rc == 0, (stdout + "\n" + stderr).strip()
    
    def create_branch(self, branch_name: str, from_commit: Optional[str]=None) -> Tuple[bool, str]:
        command = ["checkout", "-b", branch_name]
        if from_commit: command.append(from_commit)
        rc, stdout, stderr = self._run_command(command)
        return rc == 0, (stdout + "\n" + stderr).strip()

    def delete_branch(self, branch_name: str, force: bool = False) -> Tuple[bool, str]:
        command = ["branch", "-d", branch_name]
        if force: command[1] = "-D"
        rc, stdout, stderr = self._run_command(command)
        return rc == 0, (stdout + "\n" + stderr).strip()

    def get_current_branch(self) -> str:
        rc, stdout, _ = self._run_command(["branch", "--show-current"])
        return stdout if rc == 0 else "Not on a branch"
        
    def get_remotes(self) -> List[str]:
        rc, stdout, _ = self._run_command(["remote"])
        return stdout.splitlines() if rc == 0 and stdout else []

    def get_upstream_branch(self) -> Optional[str]:
        rc, stdout, _ = self._run_command(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        return stdout if rc == 0 else None

    def stage_files(self, filepaths: List[str]): return self._run_command(["add"] + filepaths)
    def unstage_files(self, filepaths: List[str]): return self._run_command(["reset", "HEAD", "--"] + filepaths)
    def discard_changes(self, filepaths: List[str]): return self._run_command(["checkout", "--"] + filepaths)

    def commit(self, message: str) -> Tuple[bool, str]:
        rc_user, _, _ = self._run_command(["config", "user.name"])
        rc_email, _, _ = self._run_command(["config", "user.email"])
        if rc_user != 0 or rc_email != 0:
            return False, "Author identity unknown\n\nPlease run these commands in your terminal to set your identity:\ngit config --global user.name \"Your Name\"\ngit config --global user.email \"you@example.com\""
        
        rc_staged, _, _ = self._run_command(["diff", "--staged", "--quiet"])
        if rc_staged == 0:
            return False, "No changes added to commit. Stage files before committing."

        rc, stdout, stderr = self._run_command(["commit", "-m", message])
        return rc == 0, (stdout + "\n" + stderr).strip()
        
    def push(self, remote: str, branch: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["push", remote, branch])
        return rc == 0, (stdout + "\n" + stderr).strip()

    def pull(self, remote: str, branch: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["pull", remote, branch])
        return rc == 0, (stdout + "\n" + stderr).strip()
        
    def init_repo(self) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["init"])
        return rc == 0, (stdout + "\n" + stderr).strip()

    def stash(self) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["stash"])
        return rc == 0, (stdout + "\n" + stderr).strip()

    def revert_commit(self, commit_hash: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["revert", "--no-edit", commit_hash])
        return rc == 0, (stdout + "\n" + stderr).strip()

    def cherry_pick_commit(self, commit_hash: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["cherry-pick", commit_hash])
        return rc == 0, (stdout + "\n" + stderr).strip()

    def reset_to_commit(self, commit_hash: str, mode: str = "hard") -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["reset", f"--{mode}", commit_hash])
        return rc == 0, (stdout + "\n" + stderr).strip()


# ======================================================================================
# 4. UI COMPONENTS
# ======================================================================================
class TreeViewFrame(ttk.Frame):
    """A frame containing a Treeview and its scrollbar."""
    def __init__(self, parent, double_click_callback: Callable[[Any], None], workspace_root_dir: str):
        super().__init__(parent, style="TFrame")
        self.double_click_callback = double_click_callback
        self.workspace_root_dir = workspace_root_dir
        self.tree = ttk.Treeview(self, show="tree", selectmode="extended")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", self.double_click_callback)

class SourceControlUI(ttk.Frame):
    """The main user interface for Git source control."""
    def __init__(self, master, parent_app, open_file_callback: Callable[[str], None], workspace_root_dir: str):
        super().__init__(master)
        self.parent_app = parent_app
        self.open_file_callback = open_file_callback
        self.workspace_root_dir = workspace_root_dir
        self.sm = StyleManager()
        self.git_logic = GitLogic(lambda: self.workspace_root_dir)
        self.history_view = None
        self.conflicts_tree_frame: Optional[TreeViewFrame] = None # Will hold the TreeViewFrame for conflicts
        self.conflicts_label: Optional[ttk.Label] = None

        self._configure_styles()
        self._create_widgets()
        
        self.after_idle(self.refresh)

    def update_workspace(self, new_workspace_root: str):
        """Called by the parent app when the workspace/folder changes."""
        self.workspace_root_dir = new_workspace_root
        self.git_logic = GitLogic(lambda: self.workspace_root_dir)
        
        for widget in self.winfo_children():
            widget.destroy()
        self._create_widgets()
        self.refresh()

    def _configure_styles(self):
        self.sm.style.configure("Accent.TButton", font=(self.sm.FONT_UI[0], self.sm.FONT_UI[1], 'bold'), background=self.sm.COLOR_ACCENT, foreground="white")
        self.sm.style.map("Accent.TButton", background=[('active', self.sm.COLOR_ACCENT_LIGHT)])
        self.sm.style.configure("Toolbar.TButton", background=self.sm.COLOR_BG_LIGHT, foreground=self.sm.COLOR_FG, relief="flat", font=("Segoe UI", 10))
        self.sm.style.map("Toolbar.TButton", background=[('active', self.sm.COLOR_BORDER)])
        self.sm.style.configure("Prefix.TButton", font=(self.sm.FONT_UI[0], 8), background=self.sm.COLOR_BG_DARK, foreground=self.sm.COLOR_FG)
        self.sm.style.map("Prefix.TButton", background=[('active', self.sm.COLOR_BORDER)])
        
    def _create_widgets(self):
        """Creates the main widgets for the UI based on the new layout."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Container for the 'Initialize Repository' view ---
        self.init_view_frame = ttk.Frame(self)
        self.init_view_frame.grid_rowconfigure(1, weight=1)
        self.init_view_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(self.init_view_frame, text="This folder is not a Git repository.", anchor="center").grid(row=0, column=0, pady=20)
        init_button = ttk.Button(self.init_view_frame, text="Initialize Repository", style="Accent.TButton", command=self._init_repo)
        init_button.grid(row=1, column=0, sticky="")

        # --- Main View using PanedWindow for the new layout ---
        self.main_view_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        
        # Top Pane: Notebook for Changes/History
        self.notebook = ttk.Notebook(self.main_view_pane)
        self.main_view_pane.add(self.notebook, weight=1)

        # Bottom Pane: Commit Area
        commit_area_frame = ttk.Frame(self.main_view_pane, style="Header.TFrame", padding=(10,5,10,10))
        self.main_view_pane.add(commit_area_frame, weight=0)

        # --- Populate Notebook Tabs ---
        self._create_changes_tab()
        # History tab will be created on demand

        # --- Populate Commit Area ---
        self._create_commit_area(commit_area_frame)
    
    def _create_changes_tab(self):
        changes_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(changes_tab, text="Changes")
        
        changes_pane = ttk.PanedWindow(changes_tab, orient=tk.VERTICAL)
        changes_pane.pack(fill="both", expand=True)

        files_frame = ttk.Frame(changes_pane)
        changes_pane.add(files_frame, weight=3)
        # Configure grid with an extra section for conflicts
        files_frame.grid_rowconfigure(1, weight=1); files_frame.grid_rowconfigure(3, weight=1); files_frame.grid_rowconfigure(5, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        # --- Merge Conflicts Section (Initially hidden) ---
        self.conflicts_label = ttk.Label(files_frame, text="MERGE CONFLICTS", font=(self.sm.FONT_UI[0], 9, 'bold'), foreground=self.sm.COLOR_CONFLICT)
        self.conflicts_label.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.conflicts_tree_frame = TreeViewFrame(files_frame, self._on_conflict_double_click, self.workspace_root_dir)
        self.conflicts_tree_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.conflicts_tree = self.conflicts_tree_frame.tree
        # Initially hide the conflict section
        self.conflicts_label.grid_remove()
        self.conflicts_tree_frame.grid_remove()

        # --- Staged Changes Section ---
        self.staged_label = ttk.Label(files_frame, text="STAGED CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.staged_label.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        staged_frame_widget = TreeViewFrame(files_frame, self._on_file_double_click, self.workspace_root_dir)
        staged_frame_widget.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.staged_tree = staged_frame_widget.tree
        self.staged_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.staged_tree, is_staged=True))
        self.staged_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=True))

        # --- Unstaged Changes Section ---
        self.changes_label = ttk.Label(files_frame, text="CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.changes_label.grid(row=4, column=0, sticky="ew", pady=(0, 2))
        changes_frame_widget = TreeViewFrame(files_frame, self._on_file_double_click, self.workspace_root_dir)
        changes_frame_widget.grid(row=5, column=0, sticky="nsew")
        self.changes_tree = changes_frame_widget.tree
        self.changes_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.changes_tree, is_staged=False))
        self.changes_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=False))
        
        # --- Diff Viewer ---
        diff_pane = ttk.Frame(changes_pane)
        changes_pane.add(diff_pane, weight=2)
        diff_pane.grid_rowconfigure(0, weight=1); diff_pane.grid_columnconfigure(0, weight=1)
        self.diff_viewer = scrolledtext.ScrolledText(diff_pane, wrap="none", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.diff_viewer.grid(row=0, column=0, sticky="nsew")
        self.diff_viewer.tag_config("addition", foreground=self.sm.COLOR_GREEN)
        self.diff_viewer.tag_config("deletion", foreground=self.sm.COLOR_RED)
        self.diff_viewer.tag_config("header", foreground=self.sm.COLOR_BLUE, font=(self.sm.FONT_CODE[0], self.sm.FONT_CODE[1], "bold"))
        self.diff_viewer.config(state="disabled")

    def _on_file_double_click(self, event):
        """Callback for regular (non-conflict) files."""
        tree = event.widget
        item_id = tree.identify_row(event.y)
        if item_id:
            filepath = item_id
            full_path = os.path.join(self.workspace_root_dir, filepath)
            if os.path.isfile(full_path):
                self.open_file_callback(full_path)

    def _on_conflict_double_click(self, event):
        """Callback specifically for conflicted files."""
        try:
            from merge_editor import MergeEditor
        except ImportError:
            from src.merge_editor import MergeEditor

        tree = event.widget
        item_id = tree.identify_row(event.y)
        if not item_id: return
        
        filepath = item_id
        
        MergeEditor(self, self.git_logic, filepath, self.workspace_root_dir)

    def _create_commit_area(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        
        toolbar = ttk.Frame(parent_frame, style="Header.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        self._create_toolbar_button(toolbar, "Refresh ⟳", self.refresh, "Reload status")
        self._create_toolbar_button(toolbar, "History 🗎", self._show_history_tab, "View commit history")
        self._create_toolbar_button(toolbar, "Branches ⎇", self._show_branch_manager, "Manage branches")
        
        action_toolbar = ttk.Frame(toolbar, style="Header.TFrame")
        action_toolbar.pack(side="right")
        self.pull_button = self._create_toolbar_button(action_toolbar, "Pull ↓", self._pull_action, "Pull from remote")
        self.push_button = self._create_toolbar_button(action_toolbar, "Push ↑", self._push_action, "Push to remote")
        self._create_toolbar_button(action_toolbar, "Stash Σ", self._stash_action, "Stash changes")
        
        self.commit_message_text = scrolledtext.ScrolledText(parent_frame, wrap="word", height=4, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, insertbackground="white", font=self.sm.FONT_UI, relief="flat", bd=0)
        self.commit_message_text.grid(row=1, column=0, sticky="nsew", pady=(0,5))
        self.commit_message_text.insert("1.0", "Commit message...")
        self.commit_message_text.bind("<FocusIn>", self._clear_placeholder)
        self.commit_message_text.bind("<KeyRelease>", self._on_commit_message_change)
        self._configure_commit_message_tags()

        helpers_and_commit_frame = ttk.Frame(parent_frame, style="Header.TFrame")
        helpers_and_commit_frame.grid(row=2, column=0, sticky="ew")
        helpers_and_commit_frame.grid_columnconfigure(1, weight=1)
        
        commit_helpers = ttk.Frame(helpers_and_commit_frame, style="Header.TFrame")
        commit_helpers.grid(row=0, column=0, sticky="w")
        self._create_prefix_button(commit_helpers, "feat:")
        self._create_prefix_button(commit_helpers, "fix:")
        self._create_prefix_button(commit_helpers, "docs:")
        self._create_prefix_button(commit_helpers, "chore:")
        
        self.char_count_label = ttk.Label(commit_helpers, text="0/50", anchor='e', style="Header.TLabel")
        self.char_count_label.pack(side="left", padx=(10,0))
        self.sm.style.configure("Header.TLabel", background=self.sm.COLOR_BG_LIGHT)

        self.commit_button = ttk.Button(helpers_and_commit_frame, text="Commit", style="Accent.TButton", command=self._commit_action)
        self.commit_button.grid(row=0, column=2, sticky="e")
    
    def _create_toolbar_button(self, parent, text, command, tooltip_text):
        btn = ttk.Button(parent, text=text, command=command, style="Toolbar.TButton")
        btn.pack(side="left", padx=1, pady=1)
        Tooltip(btn, tooltip_text)
        return btn
    
    def _create_prefix_button(self, parent, prefix):
        btn = ttk.Button(parent, text=prefix, style="Prefix.TButton", command=lambda: self._add_commit_prefix(prefix))
        btn.pack(side="left", padx=1)
        return btn

    def refresh(self, event=None):
        is_repo = self.git_logic.is_git_repo()

        if not is_repo:
            self.main_view_pane.grid_remove()
            self.init_view_frame.grid(row=0, column=0, sticky="nsew")
            if hasattr(self.parent_app, 'update_git_status_bar'):
                self.parent_app.update_git_status_bar("Not a git repository")
            return

        self.init_view_frame.grid_remove()
        self.main_view_pane.grid(row=0, column=0, sticky="nsew")
        
        self.staged_label.config(text="STAGED CHANGES (loading...)")
        self.changes_label.config(text="CHANGES (loading...)")
        if hasattr(self.parent_app, 'update_git_status_bar'):
            self.parent_app.update_git_status_bar("Refreshing...")

        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        statuses = self.git_logic.get_status()
        branch_name = self.git_logic.get_current_branch()
        self.after(0, self._update_ui_after_refresh, statuses, branch_name)

    def _update_ui_after_refresh(self, statuses: Dict[str, str], branch_name: str):
        self.staged_tree.delete(*self.staged_tree.get_children())
        self.changes_tree.delete(*self.changes_tree.get_children())
        self.conflicts_tree.delete(*self.conflicts_tree.get_children())

        if hasattr(self.parent_app, 'file_explorer') and hasattr(self.parent_app.file_explorer, 'update_git_status'):
             self.parent_app.file_explorer.update_git_status(statuses)

        staged_count, unstaged_count, conflict_count = 0, 0, 0
        status_map = {'M': 'Ⓜ', 'A': 'Ⓐ', 'D': 'Ⓓ', 'R': 'Ⓡ', 'C': 'Ⓒ', 'U': '❗', '?': '❓'}
        conflict_statuses = ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU')

        for path, status in sorted(statuses.items()):
            normalized_path = path.replace('\\', '/')
            
            if status in conflict_statuses:
                conflict_count += 1
                symbol = status_map.get('U', '❗')
                self.conflicts_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")
                continue

            staged_char, unstaged_char = status[0], status[1]
            
            # A file can be in both staged and unstaged (e.g., status 'MM'), so we process them independently.
            if staged_char != ' ' and staged_char != '?':
                staged_count += 1
                symbol = status_map.get(staged_char, staged_char)
                self.staged_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")
            
            # FIX: This block handles all unstaged changes, including untracked ('??').
            # The previous extra `if` for '??' was redundant and caused the duplicate item error.
            if unstaged_char != ' ':
                unstaged_count += 1
                symbol = status_map.get(unstaged_char, unstaged_char)
                self.changes_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")

        # Update labels
        self.staged_label.config(text=f"STAGED CHANGES ({staged_count})")
        self.changes_label.config(text=f"CHANGES ({unstaged_count})")
        
        if self.conflicts_tree_frame and self.conflicts_label:
            if conflict_count > 0:
                self.conflicts_label.config(text=f"MERGE CONFLICTS ({conflict_count})")
                self.conflicts_label.grid()
                self.conflicts_tree_frame.grid()
            else:
                self.conflicts_label.grid_remove()
                self.conflicts_tree_frame.grid_remove()

        if hasattr(self.parent_app, 'update_git_status_bar'):
            status_text = f"Branch: {branch_name}"
            if conflict_count > 0:
                status_text += f" | Conflicts: {conflict_count}"
            self.parent_app.update_git_status_bar(status_text)


    def _show_context_menu(self, event, tree, is_staged):
        menu = tk.Menu(tree, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG, relief="flat")
        item_id = tree.identify_row(event.y)
        
        if item_id:
            tree.selection_set(item_id)
            if is_staged:
                menu.add_command(label="Unstage", command=lambda: self._unstage_files(tree.selection()))
            else:
                menu.add_command(label="Stage", command=lambda: self._stage_files(tree.selection()))
                menu.add_command(label="Discard Changes", command=lambda: self._discard_changes(tree.selection()))
        else:
            if is_staged:
                menu.add_command(label="Unstage All", command=lambda: self._unstage_files([tree.item(i, "id") for i in tree.get_children()]))
            else:
                menu.add_command(label="Stage All", command=lambda: self._stage_files([tree.item(i, "id") for i in tree.get_children()]))
                menu.add_command(label="Discard All Changes", command=lambda: self._discard_changes([tree.item(i, "id") for i in tree.get_children()]))
        
        if menu.index('end') is not None:
            menu.tk_popup(event.x_root, event.y_root)

    def _show_diff_for_selection(self, event, is_staged):
        tree = event.widget
        selection = tree.selection()
        if not selection:
            self.diff_viewer.config(state="normal"); self.diff_viewer.delete("1.0", tk.END); self.diff_viewer.config(state="disabled")
            return
        filepath = selection[0]
        success, diff_text = self.git_logic.get_diff(filepath, is_staged=is_staged)
        self.diff_viewer.config(state="normal")
        self.diff_viewer.delete("1.0", tk.END)
        if success or diff_text:
            self._display_colored_diff(diff_text)
        else:
            self.diff_viewer.insert("1.0", f"No changes to display for {filepath}")
        self.diff_viewer.config(state="disabled")

    def _display_colored_diff(self, diff_text, text_widget=None):
        target_widget = text_widget if text_widget else self.diff_viewer
        target_widget.config(state="normal")
        target_widget.delete("1.0", tk.END)
        for line in diff_text.splitlines():
            if line.startswith('+') and not line.startswith('+++'): target_widget.insert(tk.END, line + '\n', "addition")
            elif line.startswith('-') and not line.startswith('---'): target_widget.insert(tk.END, line + '\n', "deletion")
            elif line.startswith('diff') or line.startswith('index') or line.startswith('@@') or line.startswith('commit'): target_widget.insert(tk.END, line + '\n', "header")
            else: target_widget.insert(tk.END, line + '\n')
        target_widget.config(state="disabled")


    def _stage_files(self, filepaths): 
        if not filepaths: return
        self.git_logic.stage_files(filepaths); self.refresh()
    def _unstage_files(self, filepaths): 
        if not filepaths: return
        self.git_logic.unstage_files(filepaths); self.refresh()
    def _discard_changes(self, filepaths):
        if not filepaths: return
        if messagebox.askyesno("Discard Changes", f"Are you sure you want to discard changes to {len(filepaths)} file(s)? This cannot be undone.", icon='warning'):
            self.git_logic.discard_changes(filepaths); self.refresh()

    def _clear_placeholder(self, event=None):
        if self.commit_message_text.get("1.0", "end-1c") == "Commit message...":
            self.commit_message_text.delete("1.0", "end")
            self._on_commit_message_change()

    def _configure_commit_message_tags(self):
        self.commit_message_text.tag_configure("prefix", foreground=self.sm.COLOR_ORANGE, font=(self.sm.FONT_UI[0], self.sm.FONT_UI[1], 'bold'))
        self.commit_message_text.tag_configure("error", background="#5A1D1D")

    def _on_commit_message_change(self, event=None):
        content = self.commit_message_text.get("1.0", "end-1c")
        first_line = content.split('\n')[0]
        count = len(first_line)
        self.char_count_label.config(text=f"{count}/50")
        if count > 50:
            self.char_count_label.config(foreground=self.sm.COLOR_RED)
        else:
            self.char_count_label.config(foreground=self.sm.COLOR_FG)

        self.commit_message_text.tag_remove("prefix", "1.0", "end")
        for match in re.finditer(r"^(feat|fix|docs|chore|style|refactor|test|build)(!?)(\(.*\))?:", content):
            start, end = match.span(0)
            self.commit_message_text.tag_add("prefix", f"1.{start}", f"1.{end}")

    def _add_commit_prefix(self, prefix):
        self._clear_placeholder()
        self.commit_message_text.insert("1.0", prefix + " ")
        self.commit_message_text.focus_set()
        self._on_commit_message_change()

    def _commit_action(self):
        message = self.commit_message_text.get("1.0", "end-1c").strip()
        if not message or message == "Commit message...":
            self.show_detailed_error("Commit Error", "Please enter a commit message.")
            return
        success, output = self.git_logic.commit(message)
        if success:
            messagebox.showinfo("Commit Successful", output)
            self.commit_message_text.delete("1.0", "end"); self.commit_message_text.insert("1.0", "Commit message...")
            self._on_commit_message_change()
            self.refresh()
            if self.history_view and self.history_view.winfo_exists():
                self.history_view.populate_log()
        else:
            self.show_detailed_error("Commit Failed", output)

    def _pull_action(self): self._run_remote_action("pull")
    def _push_action(self): self._run_remote_action("push")

    def _stash_action(self):
        success, output = self.git_logic.stash()
        if success:
            messagebox.showinfo("Stash Successful", output if output else "No local changes to save")
            self.refresh()
        else:
            self.show_detailed_error("Stash Failed", output)

    def _run_remote_action(self, action: str):
        upstream = self.git_logic.get_upstream_branch()
        if upstream:
            remote, branch = upstream.split('/', 1)
        else:
            remotes = self.git_logic.get_remotes()
            if not remotes:
                self.show_detailed_error("No Remotes", "No remote repositories configured."); return
            elif len(remotes) == 1:
                remote = remotes[0]
            else:
                dialog = RemoteDialog(self, f"Select Remote for Git {action.capitalize()}", remotes)
                remote = dialog.result
                if not remote: return
            branch = self.git_logic.get_current_branch()

        self.parent_app.update_git_status_bar(f"Running git {action} from '{remote}/{branch}'...")
        self.push_button.config(state="disabled"); self.pull_button.config(state="disabled")
        threading.Thread(target=self._run_remote_action_thread, args=(action, remote, branch), daemon=True).start()

    def _run_remote_action_thread(self, action, remote, branch):
        logic_func = self.git_logic.pull if action == "pull" else self.git_logic.push
        success, output = logic_func(remote, branch)
        self.after(0, self._on_remote_action_done, action, success, output)

    def _on_remote_action_done(self, action, success, output):
        self.push_button.config(state="normal"); self.pull_button.config(state="normal")
        if hasattr(self.parent_app, 'update_git_status_bar'):
            self.parent_app.update_git_status_bar(f"Branch: {self.git_logic.get_current_branch()}")
        if success:
            messagebox.showinfo(f"{action.capitalize()} Successful", output); self.refresh()
            if self.history_view and self.history_view.winfo_exists():
                self.history_view.populate_log()
        else:
            self.show_detailed_error(f"{action.capitalize()} Failed", output)

    def _init_repo(self):
        if messagebox.askyesno("Initialize Repository", "Are you sure you want to initialize a new Git repository?"):
            success, output = self.git_logic.init_repo()
            if success: messagebox.showinfo("Success", "Git repository initialized."); self.refresh()
            else: self.show_detailed_error("Initialization Failed", output)

    def _show_history_tab(self):
        """Creates and focuses the history tab if it doesn't exist."""
        if self.history_view and self.history_view.winfo_exists():
             for i, tab_text in enumerate(self.notebook.tabs()):
                if self.notebook.tab(i, "text") == "History":
                    self.notebook.select(i)
                    return
        
        self.history_view = ModernGitLogViewer(self.notebook, self)
        self.notebook.add(self.history_view, text="History")
        self.notebook.select(self.notebook.tabs()[-1])

    def _show_branch_manager(self):
        BranchManager(self, self.git_logic)
        
    def show_detailed_error(self, title, details):
        DetailedErrorDialog(self, title, details)


class ModernGitLogViewer(ttk.Frame):
    """A modern, graphical Git log/history viewer, designed to be a tab."""
    def __init__(self, parent, source_control_ui_instance: 'SourceControlUI'):
        super().__init__(parent)
        self.parent_ui = source_control_ui_instance
        self.git_logic = self.parent_ui.git_logic
        self.sm = self.parent_ui.sm
        
        self.commits_data = []
        self.commit_map = {}
        self.lane_colors = [self.sm.COLOR_ACCENT, "#3399CC", "#9933CC", "#CC9933", "#33CC99", "#CC3399"]
        self.dot_id_to_commit = {}
        self.tooltip = None
        self.hovered_dot_id = None
        
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_pane)
        main_pane.add(top_frame, weight=3)
        top_frame.grid_rowconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=1)

        self.graph_canvas = tk.Canvas(top_frame, bg=self.sm.COLOR_BG_DARK, highlightthickness=0, width=200)
        self.graph_canvas.grid(row=0, column=0, sticky="ns")

        self.commit_text = tk.Text(top_frame, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_UI, wrap="none", bd=0, highlightthickness=0, spacing2=8)
        self.commit_text.grid(row=0, column=1, sticky="nsew")

        self.scrollbar = ttk.Scrollbar(top_frame, orient="vertical", command=self._on_scroll)
        self.scrollbar.grid(row=0, column=2, sticky="ns")
        self.graph_canvas.config(yscrollcommand=self.scrollbar.set)
        self.commit_text.config(yscrollcommand=self.scrollbar.set)

        bottom_frame = ttk.Frame(main_pane)
        main_pane.add(bottom_frame, weight=2)
        bottom_frame.grid_rowconfigure(0, weight=1); bottom_frame.grid_columnconfigure(0, weight=1)

        self.commit_detail_viewer = scrolledtext.ScrolledText(bottom_frame, wrap="none", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.commit_detail_viewer.grid(row=0, column=0, sticky="nsew")
        self.commit_detail_viewer.tag_config("addition", foreground=self.sm.COLOR_GREEN); self.commit_detail_viewer.tag_config("deletion", foreground=self.sm.COLOR_RED); self.commit_detail_viewer.tag_config("header", foreground=self.sm.COLOR_BLUE, font=(self.sm.FONT_CODE[0], self.sm.FONT_CODE[1], "bold"))
        self.commit_detail_viewer.config(state="disabled")

        self.commit_text.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<Motion>", self._on_canvas_hover)
        self.graph_canvas.bind("<Leave>", self._hide_tooltip)
        self.commit_text.bind("<Button-1>", self._on_commit_click)
        self.commit_text.bind("<Button-3>", self._show_commit_context_menu)
        
        self.populate_log()

    def populate_log(self):
        """Starts the process of fetching and displaying the git log."""
        self.commit_text.config(state="normal")
        self.commit_text.delete("1.0", tk.END)
        self.commit_text.insert("1.0", "Loading history...")
        self.commit_text.config(state="disabled")
        
        self.commit_detail_viewer.config(state="normal")
        self.commit_detail_viewer.delete("1.0", tk.END)
        self.commit_detail_viewer.config(state="disabled")

        threading.Thread(target=self._populate_log_worker, daemon=True).start()

    def _populate_log_worker(self):
        success, log_data = self.git_logic.get_log_for_graph()
        self.after(0, self._update_ui_after_log, success, log_data)

    def _update_ui_after_log(self, success: bool, log_data: str):
        self.commits_data = []
        self.commit_map = {}
        
        if not success:
            self.commit_text.config(state="normal")
            self.commit_text.delete("1.0", tk.END)
            self.commit_text.insert(tk.END, f"Error loading log:\n{log_data}")
            self.commit_text.config(state="disabled")
            return
        
        lines = log_data.splitlines()
        for i, line in enumerate(lines):
            parts = line.split("|")
            if len(parts) == 6:
                chash, phash_str, author, date, refs, message = parts
                parents = phash_str.split()
                commit_info = {"hash": chash, "parents": parents, "author": author, "date": date, "refs": refs.strip(), "message": message, "line_num": i}
                self.commits_data.append(commit_info)
                self.commit_map[chash] = i
        
        self.draw_graph()
        self.display_commits()

    def _on_scroll(self, *args):
        self.graph_canvas.yview(*args)
        self.commit_text.yview(*args)

    def _on_mousewheel(self, event):
        self.graph_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.commit_text.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break"

    def draw_graph(self):
        self.graph_canvas.delete("all")
        self.dot_id_to_commit.clear()
        row_height = 40
        dot_radius = 4
        
        commit_lanes = self._assign_lanes()
        
        for i, commit in enumerate(self.commits_data):
            y = i * row_height + (row_height / 2)
            lane_index = commit_lanes.get(commit["hash"], 0)
            x = 30 + lane_index * 20
            
            for p_hash in commit["parents"]:
                if p_hash in self.commit_map:
                    p_index = self.commit_map[p_hash]
                    p_lane_index = commit_lanes.get(p_hash, 0)
                    p_y = p_index * row_height + (row_height / 2)
                    p_x = 30 + p_lane_index * 20
                    color = self.lane_colors[lane_index % len(self.lane_colors)]
                    if p_lane_index == lane_index:
                        self.graph_canvas.create_line(x, y, p_x, p_y, fill=color, width=2)
                    else:
                        self.graph_canvas.create_line(x, y, x, y + row_height/2, p_x, p_y - row_height/2, p_x, p_y, fill=color, width=2, smooth=True) #type: ignore

            color = self.lane_colors[lane_index % len(self.lane_colors)]
            dot_id = self.graph_canvas.create_oval(x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius, fill=color, outline=self.sm.COLOR_BORDER, tags="commit_dot")
            self.dot_id_to_commit[dot_id] = commit

        total_height = len(self.commits_data) * row_height
        self.graph_canvas.config(scrollregion=(0, 0, self.graph_canvas.winfo_width(), total_height))

    def _assign_lanes(self):
        commit_lanes, lanes = {}, []
        for commit in self.commits_data:
            chash, my_lane = commit["hash"], -1
            try: my_lane = lanes.index(chash)
            except (ValueError, IndexError):
                try: my_lane = lanes.index(None)
                except ValueError: my_lane = len(lanes); lanes.append(None)
            commit_lanes[chash] = my_lane
            lanes[my_lane] = commit["parents"][0] if commit["parents"] else None
            for p_hash in commit["parents"][1:]:
                try: p_lane = lanes.index(None)
                except ValueError: p_lane = len(lanes); lanes.append(None)
                lanes[p_lane] = p_hash
        return commit_lanes

    def display_commits(self):
        self.commit_text.config(state="normal")
        self.commit_text.delete("1.0", tk.END)

        self.commit_text.tag_configure("msg", font=self.sm.FONT_UI)
        self.commit_text.tag_configure("info", font=(self.sm.FONT_UI[0], 9), foreground="#999999")
        self.commit_text.tag_configure("hash", font=self.sm.FONT_CODE, foreground="#777777")
        self.commit_text.tag_configure("commit_block", spacing1=10, spacing3=10)

        for commit in self.commits_data:
            start_index = self.commit_text.index(tk.END)
            self.commit_text.insert(tk.END, f"{commit['message']}  ", "msg")
            if commit['refs']:
                refs_parts = [r.strip() for r in commit['refs'].strip('() ').split(',') if r.strip()]
                for ref in refs_parts:
                    ref_text = ref.replace('HEAD -> ', '')
                    is_head = 'HEAD ->' in ref
                    is_remote = '/' in ref_text and not is_head
                    color = self.sm.COLOR_ACCENT if is_head else self.sm.COLOR_GREEN if is_remote else self.sm.COLOR_ORANGE
                    ref_label = tk.Label(self.commit_text, text=f" {ref_text} ", bg=color, fg="white", font=(self.sm.FONT_UI[0], 8, 'bold'))
                    self.commit_text.window_create(tk.END, window=ref_label, padx=2)
            self.commit_text.insert(tk.END, f"\n{commit['author']}  •  {commit['date']}  ", "info")
            self.commit_text.insert(tk.END, f"{commit['hash'][:7]}\n", "hash")
            self.commit_text.tag_add("commit_block", start_index, tk.END)

        self.commit_text.config(state="disabled")

    def _on_commit_click(self, event):
        line_num = int(self.commit_text.index(f"@{event.x},{event.y}").split('.')[0]) - 1
        commit_index = line_num // 2
        
        if 0 <= commit_index < len(self.commits_data):
            commit = self.commits_data[commit_index]
            self._fetch_and_display_commit_details(commit['hash'])
        return "break"
        
    def _fetch_and_display_commit_details(self, commit_hash: str):
        self.commit_detail_viewer.config(state="normal")
        self.commit_detail_viewer.delete("1.0", tk.END)
        self.commit_detail_viewer.insert("1.0", f"Loading details for {commit_hash[:7]}...")
        self.commit_detail_viewer.config(state="disabled")

        def worker():
            success, details = self.git_logic.get_commit_details(commit_hash)
            self.after(0, self.parent_ui._display_colored_diff, details, self.commit_detail_viewer)
        threading.Thread(target=worker, daemon=True).start()

    def _show_commit_context_menu(self, event):
        line_num_str = self.commit_text.index(f"@{event.x},{event.y}").split('.')[0]
        if not line_num_str: return
        line_num = int(line_num_str) -1
        commit_index = line_num // 2
        
        if not (0 <= commit_index < len(self.commits_data)): return
        
        commit = self.commits_data[commit_index]
        commit_hash = commit['hash']
        
        menu = tk.Menu(self, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG)
        menu.add_command(label=f"Create branch from '{commit_hash[:7]}'...", command=lambda: self._create_branch_from_commit(commit_hash))
        menu.add_command(label=f"Checkout '{commit_hash[:7]}'", command=lambda: self._checkout_commit(commit_hash))
        menu.add_separator()
        menu.add_command(label=f"Cherry-pick '{commit_hash[:7]}'", command=lambda: self._cherry_pick_commit(commit_hash))
        menu.add_command(label=f"Revert commit '{commit_hash[:7]}'", command=lambda: self._revert_commit(commit_hash))
        menu.add_separator()
        reset_menu = tk.Menu(menu, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG)
        menu.add_cascade(label=f"Reset current branch to '{commit_hash[:7]}'", menu=reset_menu)
        reset_menu.add_command(label="Soft - Keep all changes", command=lambda: self._reset_to_commit(commit_hash, "soft"))
        reset_menu.add_command(label="Mixed - Keep working dir, unstage changes", command=lambda: self._reset_to_commit(commit_hash, "mixed"))
        reset_menu.add_command(label="Hard - Discard all changes (DANGEROUS)", command=lambda: self._reset_to_commit(commit_hash, "hard"))
        menu.add_separator()
        menu.add_command(label="Copy full commit hash", command=lambda: self._copy_to_clipboard(commit_hash))
        menu.tk_popup(event.x_root, event.y_root)

    def _create_branch_from_commit(self, commit_hash):
        branch_name = simpledialog.askstring("Create Branch", "Enter new branch name:", parent=self)
        if not branch_name: return
        success, output = self.git_logic.create_branch(branch_name, from_commit=commit_hash)
        if success:
            messagebox.showinfo("Success", f"Created and switched to branch '{branch_name}' from commit {commit_hash[:7]}.", parent=self)
            self.parent_ui.refresh()
        else:
            self.parent_ui.show_detailed_error(f"Failed to create branch '{branch_name}'", output)
            
    def _checkout_commit(self, commit_hash):
        if not messagebox.askyesno("Checkout Commit", f"This will put you in a 'detached HEAD' state. Are you sure you want to checkout commit {commit_hash[:7]}?", parent=self):
            return
        success, output = self.git_logic.switch_branch(commit_hash)
        if success:
            messagebox.showinfo("Success", f"Checked out commit {commit_hash[:7]}.\nYou are in a detached HEAD state.", parent=self)
            self.parent_ui.refresh()
        else:
            self.parent_ui.show_detailed_error(f"Failed to checkout commit", output)

    def _revert_commit(self, commit_hash):
        msg = f"This will create a new commit that reverts the changes from {commit_hash[:7]}. Continue?"
        if not messagebox.askyesno("Revert Commit", msg, parent=self): return
        success, output = self.git_logic.revert_commit(commit_hash)
        if success:
            messagebox.showinfo("Success", f"Reverted commit {commit_hash[:7]}.", parent=self)
            self.parent_ui.refresh(); self.populate_log()
        else:
            self.parent_ui.show_detailed_error(f"Failed to revert commit", output)

    def _cherry_pick_commit(self, commit_hash):
        msg = f"This will apply the changes from {commit_hash[:7]} on top of your current branch. Continue?"
        if not messagebox.askyesno("Cherry-pick Commit", msg, parent=self): return
        success, output = self.git_logic.cherry_pick_commit(commit_hash)
        if success:
            messagebox.showinfo("Success", f"Cherry-picked commit {commit_hash[:7]}.", parent=self)
            self.parent_ui.refresh(); self.populate_log()
        else:
            self.parent_ui.show_detailed_error(f"Failed to cherry-pick commit", output)

    def _reset_to_commit(self, commit_hash, mode):
        if mode == 'hard':
            msg1 = f"DANGER: You are about to perform a 'git reset --hard' to {commit_hash[:7]}.\n\nTHIS WILL PERMANENTLY DELETE ALL UNCOMMITTED CHANGES in your working directory and staging area.\n\nAre you absolutely sure?"
            if not messagebox.askyesno("Confirm Hard Reset", msg1, icon='error', parent=self): return
            
            prompt = f"To confirm this destructive action, please type the first 7 characters of the commit hash: {commit_hash[:7]}"
            confirmation = simpledialog.askstring("Final Confirmation", prompt, parent=self)
            if confirmation != commit_hash[:7]:
                messagebox.showerror("Confirmation Failed", "The entered hash did not match. Reset cancelled.", parent=self)
                return
        else:
            msg = f"Are you sure you want to perform a 'git reset --{mode}' to {commit_hash[:7]}?\nYour working directory changes will be kept."
            if not messagebox.askyesno(f"Confirm {mode.capitalize()} Reset", msg, icon='warning', parent=self): return
        
        success, output = self.git_logic.reset_to_commit(commit_hash, mode)
        if success:
            messagebox.showinfo("Success", f"Successfully reset to {commit_hash[:7]}.", parent=self)
            self.parent_ui.refresh(); self.populate_log()
        else:
            self.parent_ui.show_detailed_error(f"Failed to reset", output)

    def _copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "Commit hash copied to clipboard.", parent=self)

    def _on_canvas_hover(self, event):
        canvas = event.widget
        item_ids = canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        
        dot_id = next((item_id for item_id in reversed(item_ids) if "commit_dot" in canvas.gettags(item_id)), None)

        if dot_id is not None:
            if dot_id != self.hovered_dot_id:
                self.hovered_dot_id = dot_id
                self._show_tooltip(event, self.dot_id_to_commit[dot_id])
        else:
            self._hide_tooltip()

    def _show_tooltip(self, event, commit_data):
        self._hide_tooltip()
        
        x, y = event.x_root + 15, event.y_root - 10
        
        self.tooltip = tk.Toplevel(self.graph_canvas)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        tooltip_text = f"{commit_data['message']}\n\n" \
                       f"Author: {commit_data['author']}\n" \
                       f"Date: {commit_data['date']}\n" \
                       f"Hash: {commit_data['hash'][:12]}"
        if commit_data['refs']: tooltip_text += f"\nRefs: {commit_data['refs']}"

        label = tk.Label(self.tooltip, text=tooltip_text, justify='left', bg="#252526", relief='solid', borderwidth=1, font=("Segoe UI", 9), foreground="#D4D4D4", wraplength=400, anchor='w', padx=5, pady=5)
        label.pack(ipadx=1)
        
        self.tooltip.update_idletasks()
        self.tooltip.wm_geometry(f"+{x}+{event.y_root - self.tooltip.winfo_height() - 5}")

    def _hide_tooltip(self, event=None):
        self.hovered_dot_id = None
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class BranchManager(tk.Toplevel):
    """Dialog for viewing and switching branches."""
    def __init__(self, parent, git_logic: GitLogic):
        super().__init__(parent)
        self.parent_ui = parent
        self.git_logic = git_logic
        self.sm = StyleManager()
        self.title("Branch Management")
        self.geometry("450x400")
        self.configure(bg=self.sm.COLOR_BG)

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        self.branch_listbox = tk.Listbox(list_frame, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, selectbackground=self.sm.COLOR_ACCENT_LIGHT, bd=0, highlightthickness=0, font=self.sm.FONT_UI)
        self.branch_listbox.grid(row=0, column=0, sticky="nsew")
        self.branch_listbox.bind("<Button-3>", self._show_context_menu)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.branch_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.branch_listbox.config(yscrollcommand=scrollbar.set)
        
        self.populate_branches()

        new_branch_frame = ttk.Frame(main_frame)
        new_branch_frame.grid(row=1, column=0, sticky="ew", pady=5)
        new_branch_frame.grid_columnconfigure(0, weight=1)
        self.new_branch_entry = ttk.Entry(new_branch_frame, font=self.sm.FONT_UI)
        self.new_branch_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
        ttk.Button(new_branch_frame, text="Create Branch", command=self.create_branch).grid(row=0, column=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(10,0))
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        ttk.Button(button_frame, text="Switch to Selected", command=self.switch_branch, style="Accent.TButton").grid(row=0, column=0, sticky="ew", padx=(0,5))
        ttk.Button(button_frame, text="Close", command=self.destroy).grid(row=0, column=1, sticky="ew", padx=(5,0))
        self.grab_set()

    def populate_branches(self):
        self.branch_listbox.delete(0, tk.END)
        success, branches, current_branch = self.git_logic.get_branches()
        if success:
            local_branches = sorted([b for b in branches if not b.startswith("remotes/")])
            remote_branches = sorted([b for b in branches if b.startswith("remotes/")])

            if local_branches:
                self.branch_listbox.insert(tk.END, "--- Local Branches ---")
                self.branch_listbox.itemconfig(tk.END, {'bg': self.sm.COLOR_BG_LIGHT, 'fg': self.sm.COLOR_ACCENT})
                for branch in local_branches:
                    display_name = branch[2:] if branch.startswith("* ") else branch
                    idx = self.branch_listbox.size()
                    self.branch_listbox.insert(tk.END, f"  {display_name}")
                    if branch.startswith("* "):
                        self.branch_listbox.itemconfig(idx, {'bg': self.sm.COLOR_ACCENT_LIGHT})
                        self.branch_listbox.selection_set(idx)

            if remote_branches:
                self.branch_listbox.insert(tk.END, "--- Remote Branches ---")
                self.branch_listbox.itemconfig(tk.END, {'bg': self.sm.COLOR_BG_LIGHT, 'fg': self.sm.COLOR_GREEN})
                for branch in remote_branches:
                    display_name = branch.replace("remotes/", "")
                    self.branch_listbox.insert(tk.END, f"  {display_name}")


    def switch_branch(self):
        selection_indices = self.branch_listbox.curselection()
        if not selection_indices: messagebox.showwarning("No Selection", "Please select a branch.", parent=self); return
        
        branch_name_full = self.branch_listbox.get(selection_indices[0]).strip()
        if branch_name_full.startswith("---"):
            messagebox.showwarning("Invalid Selection", "Please select an actual branch, not a category header.", parent=self)
            return

        branch_name_to_checkout = branch_name_full
        
        if '/' in branch_name_to_checkout and messagebox.askyesno(
            "Checkout Remote Branch",
            f"This looks like a remote branch. Do you want to create a new local branch tracking '{branch_name_to_checkout}'?",
            parent=self
        ) is False:
            return

        success, output = self.git_logic.switch_branch(branch_name_to_checkout)
        if success:
            messagebox.showinfo("Success", f"Switched to branch '{branch_name_to_checkout}'.", parent=self)
            self.parent_ui.refresh(); self.destroy()
        else:
            self.parent_ui.show_detailed_error(f"Failed to switch to '{branch_name_to_checkout}'", output)
    
    def create_branch(self):
        new_branch_name = self.new_branch_entry.get().strip()
        if not new_branch_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new branch.", parent=self)
            return
        success, output = self.git_logic.create_branch(new_branch_name)
        if success:
            messagebox.showinfo("Success", f"Created and switched to new branch '{new_branch_name}'.", parent=self)
            self.parent_ui.refresh(); self.destroy()
        else:
            self.parent_ui.show_detailed_error(f"Failed to create branch '{new_branch_name}'", output)
    
    def _show_context_menu(self, event):
        selection_indices = self.branch_listbox.nearest(event.y)
        self.branch_listbox.selection_clear(0, tk.END)
        self.branch_listbox.selection_set(selection_indices)
        
        branch_name_full = self.branch_listbox.get(selection_indices).strip()
        if branch_name_full.startswith("---") or '/' in branch_name_full:
             return

        branch_name = branch_name_full

        if branch_name == self.git_logic.get_current_branch(): return

        menu = tk.Menu(self, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG)
        menu.add_command(label=f"Delete '{branch_name}'", command=lambda: self.delete_branch(branch_name, False))
        menu.add_command(label=f"Force Delete '{branch_name}'", command=lambda: self.delete_branch(branch_name, True))
        menu.tk_popup(event.x_root, event.y_root)

    def delete_branch(self, branch_name, force):
        confirm_msg = f"Are you sure you want to {'force ' if force else ''}delete branch '{branch_name}'?"
        if not messagebox.askyesno("Confirm Deletion", confirm_msg, parent=self): return
        
        success, output = self.git_logic.delete_branch(branch_name, force)
        if success:
            messagebox.showinfo("Success", f"Deleted branch '{branch_name}'.", parent=self)
            self.populate_branches()
        else:
            self.parent_ui.show_detailed_error(f"Failed to delete branch '{branch_name}'", output)

class GitCommandAutocompleteManager:
    # This class definition is now a placeholder until we implement the Git Console tab
    def __init__(self, *args, **kwargs):
        pass