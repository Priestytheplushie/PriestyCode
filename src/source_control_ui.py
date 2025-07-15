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
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
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

        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#3C3F41", relief='solid', borderwidth=1,
                         font=("Segoe UI", 9, "normal"), foreground="#D4D4D4", wraplength=400)
        label.pack(ipadx=2, ipady=2)

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
        try:
            process = subprocess.Popen(
                ["git"] + command,
                cwd=self.get_project_root(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            stdout, stderr = process.communicate()
            return process.returncode, stdout.strip(), stderr.strip()
        except FileNotFoundError:
            return -1, "", "Git not found. Please ensure Git is installed and in your system's PATH."
        except Exception as e:
            return -1, "", str(e)

    def run_arbitrary_command(self, command_str: str) -> Tuple[bool, str]:
        """Runs a raw git command string."""
        try:
            command_parts = shlex.split(command_str)
        except ValueError as e:
            return False, f"Error parsing command: {e}"
            
        rc, stdout, stderr = self._run_command(command_parts)
        return rc == 0, (stdout + "\n" + stderr).strip()

    def is_git_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.get_project_root(), '.git'))

    def get_status(self) -> Dict[str, str]:
        rc, stdout, _ = self._run_command(["status", "--porcelain=v1", "-u"])
        if rc != 0: return {}
        status_dict = {}
        for line in stdout.splitlines():
            if line:
                status, filepath = line[:2], line[3:]
                filepath = filepath.strip().replace('"', '')
                status_dict[filepath] = status
        return status_dict
    
    def get_diff(self, filepath: str, is_staged: bool = False) -> Tuple[bool, str]:
        command = ["diff", "--patch-with-raw"]
        if is_staged: command.append("--staged")
        command.extend(["--", filepath])
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
    
    def create_branch(self, branch_name: str) -> Tuple[bool, str]:
        rc, stdout, stderr = self._run_command(["checkout", "-b", branch_name])
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

# ======================================================================================
# 4. UI COMPONENTS
# ======================================================================================
class TreeViewFrame(ttk.Frame):
    """A frame containing a Treeview and its scrollbar."""
    def __init__(self, parent, open_file_callback: Callable[[str], None], workspace_root_dir: str):
        super().__init__(parent, style="TFrame")
        self.open_file_callback = open_file_callback
        self.workspace_root_dir = workspace_root_dir
        self.tree = ttk.Treeview(self, show="tree", selectmode="extended")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", self._on_double_click_proxy)

    def _on_double_click_proxy(self, event):
        tree = event.widget
        item_id = tree.identify_row(event.y)
        if item_id:
            filepath = tree.item(item_id, 'id')
            full_path = os.path.join(self.workspace_root_dir, filepath)
            if os.path.isfile(full_path):
                self.open_file_callback(full_path)


class SourceControlUI(ttk.Frame):
    """The main user interface for Git source control."""
    def __init__(self, master, parent_app, open_file_callback: Callable[[str], None], workspace_root_dir: str):
        super().__init__(master)
        self.parent_app = parent_app
        self.open_file_callback = open_file_callback
        self.workspace_root_dir = workspace_root_dir
        self.sm = StyleManager()
        self.git_logic = GitLogic(lambda: self.workspace_root_dir)

        self._configure_styles()
        self._create_widgets()
        
        if self.master:
            self.master.after_idle(self.refresh)
        else:
            print("Warning: SourceControlUI master is None, cannot schedule refresh.")

    def _configure_styles(self):
        self.sm.style.configure("Accent.TButton", font=(self.sm.FONT_UI[0], self.sm.FONT_UI[1], 'bold'), background=self.sm.COLOR_ACCENT, foreground="white")
        self.sm.style.map("Accent.TButton", background=[('active', self.sm.COLOR_ACCENT_LIGHT)])
        self.sm.style.configure("Toolbar.TButton", background=self.sm.COLOR_BG_LIGHT, foreground=self.sm.COLOR_FG, relief="flat")
        self.sm.style.map("Toolbar.TButton", background=[('active', self.sm.COLOR_BORDER)])
        self.sm.style.configure("Prefix.TButton", font=(self.sm.FONT_UI[0], 8), background=self.sm.COLOR_BG_DARK, foreground=self.sm.COLOR_FG)
        self.sm.style.map("Prefix.TButton", background=[('active', self.sm.COLOR_BORDER)])

    def _create_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Container for the 'Initialize Repository' view ---
        self.init_view_frame = ttk.Frame(self)
        self.init_view_frame.grid_rowconfigure(0, weight=1)
        self.init_view_frame.grid_columnconfigure(0, weight=1)
        init_button = ttk.Button(self.init_view_frame, text="Initialize Repository", style="Accent.TButton", command=self._init_repo)
        init_button.grid(row=0, column=0, sticky="")

        # --- Container for the main Git UI view ---
        self.main_view_frame = ttk.Frame(self)
        self.main_view_frame.grid_rowconfigure(0, weight=1)
        self.main_view_frame.grid_columnconfigure(0, weight=1)

        # --- Top resizable pane for Changes and Diff (inside main_view_frame) ---
        top_pane = ttk.PanedWindow(self.main_view_frame, orient=tk.VERTICAL)
        top_pane.grid(row=0, column=0, sticky="nsew")

        changes_pane = ttk.Frame(top_pane, padding=5)
        top_pane.add(changes_pane, weight=3)
        changes_pane.grid_rowconfigure(1, weight=1); changes_pane.grid_rowconfigure(3, weight=1); changes_pane.grid_columnconfigure(0, weight=1)

        self.staged_label = ttk.Label(changes_pane, text="STAGED CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.staged_label.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        staged_frame = TreeViewFrame(changes_pane, self.open_file_callback, self.workspace_root_dir)
        staged_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.staged_tree = staged_frame.tree
        self.staged_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.staged_tree, is_staged=True))
        self.staged_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=True))

        self.changes_label = ttk.Label(changes_pane, text="CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.changes_label.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        changes_frame_widget = TreeViewFrame(changes_pane, self.open_file_callback, self.workspace_root_dir)
        changes_frame_widget.grid(row=3, column=0, sticky="nsew")
        self.changes_tree = changes_frame_widget.tree
        self.changes_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.changes_tree, is_staged=False))
        self.changes_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=False))

        diff_pane = ttk.Frame(top_pane)
        top_pane.add(diff_pane, weight=2)
        diff_pane.grid_rowconfigure(0, weight=1); diff_pane.grid_columnconfigure(0, weight=1)
        self.diff_viewer = scrolledtext.ScrolledText(diff_pane, wrap="none", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.diff_viewer.grid(row=0, column=0, sticky="nsew")
        self.diff_viewer.tag_config("addition", foreground=self.sm.COLOR_GREEN); self.diff_viewer.tag_config("deletion", foreground=self.sm.COLOR_RED); self.diff_viewer.tag_config("header", foreground=self.sm.COLOR_BLUE, font=(self.sm.FONT_CODE[0], self.sm.FONT_CODE[1], "bold"))
        self.diff_viewer.config(state="disabled")

        # --- Bottom fixed-size pane for Commit and Actions (inside main_view_frame) ---
        commit_pane = ttk.Frame(self.main_view_frame, padding=10)
        commit_pane.grid(row=1, column=0, sticky="ew")
        commit_pane.grid_columnconfigure(0, weight=1)

        toolbar = ttk.Frame(commit_pane, style="Header.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self._create_toolbar_button(toolbar, "Refresh", self.refresh, "Reload status")
        self._create_toolbar_button(toolbar, "Branch", self._show_branch_manager, "Manage branches")
        self._create_toolbar_button(toolbar, "History", self._show_log_viewer, "View commit history")
        self.pull_button = self._create_toolbar_button(toolbar, "Pull", self._pull_action, "Pull from remote")
        self.push_button = self._create_toolbar_button(toolbar, "Push", self._push_action, "Push to remote")
        self._create_toolbar_button(toolbar, "Stash", self._stash_action, "Stash changes")

        self.commit_message_text = scrolledtext.ScrolledText(commit_pane, wrap="word", height=4, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, insertbackground="white", font=self.sm.FONT_UI, relief="flat", bd=0)
        self.commit_message_text.grid(row=1, column=0, sticky="nsew")
        self.commit_message_text.insert("1.0", "Commit message...")
        self.commit_message_text.bind("<FocusIn>", self._clear_placeholder)
        self.commit_message_text.bind("<KeyRelease>", self._on_commit_message_change)
        self._configure_commit_message_tags()

        commit_helpers = ttk.Frame(commit_pane)
        commit_helpers.grid(row=2, column=0, sticky="ew", pady=(3, 5))
        self._create_prefix_button(commit_helpers, "feat:")
        self._create_prefix_button(commit_helpers, "fix:")
        self._create_prefix_button(commit_helpers, "docs:")
        self._create_prefix_button(commit_helpers, "chore:")
        self.char_count_label = ttk.Label(commit_helpers, text="0/50", anchor='e')
        self.char_count_label.pack(side="right")

        self.commit_button = ttk.Button(commit_pane, text="Commit", style="Accent.TButton", command=self._commit_action)
        self.commit_button.grid(row=3, column=0, sticky="ew", pady=(0,10))
        
        command_palette_frame = ttk.Frame(commit_pane)
        command_palette_frame.grid(row=4, column=0, sticky="ew")
        command_palette_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(command_palette_frame, text="git", font=self.sm.FONT_CODE).grid(row=0, column=0, padx=(0,5))
        self.command_entry = ttk.Entry(command_palette_frame, font=self.sm.FONT_CODE, style="TEntry")
        self.command_entry.grid(row=0, column=1, sticky="ew")
        self.command_entry.bind("<Return>", self._run_command_from_palette)
        self.autocomplete_manager = GitCommandAutocompleteManager(self.command_entry, self)


    def _create_toolbar_button(self, parent, text, command, tooltip_text):
        btn = ttk.Button(parent, text=text, command=command, style="Toolbar.TButton")
        btn.pack(side="left", fill="y", padx=1, pady=1)
        Tooltip(btn, tooltip_text)
        return btn
    
    def _create_prefix_button(self, parent, prefix):
        btn = ttk.Button(parent, text=prefix, style="Prefix.TButton", command=lambda: self._add_commit_prefix(prefix))
        btn.pack(side="left", padx=1)
        return btn

    def refresh(self, event=None):
        """Asynchronously refreshes the Git status to keep the UI responsive."""
        is_repo = self.git_logic.is_git_repo()

        if not is_repo:
            self.main_view_frame.grid_remove()
            self.init_view_frame.grid(row=0, column=0, sticky="nsew")
            if hasattr(self.parent_app, 'update_git_status_bar'):
                self.parent_app.update_git_status_bar("Not a git repository")
            return

        self.init_view_frame.grid_remove()
        self.main_view_frame.grid(row=0, column=0, sticky="nsew")
        
        self.staged_label.config(text="STAGED CHANGES (loading...)")
        self.changes_label.config(text="CHANGES (loading...)")
        if hasattr(self.parent_app, 'update_git_status_bar'):
            self.parent_app.update_git_status_bar("Refreshing...")

        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        """[Worker Thread] Fetches git status without blocking the UI."""
        statuses = self.git_logic.get_status()
        branch_name = self.git_logic.get_current_branch()
        self.after(0, self._update_ui_after_refresh, statuses, branch_name)

    def _update_ui_after_refresh(self, statuses: Dict[str, str], branch_name: str):
        """[Main Thread] Updates the UI with data from the worker thread."""
        self.staged_tree.delete(*self.staged_tree.get_children())
        self.changes_tree.delete(*self.changes_tree.get_children())

        if hasattr(self.parent_app, 'file_explorer') and hasattr(self.parent_app.file_explorer, 'update_git_status'):
             self.parent_app.file_explorer.update_git_status(statuses)

        staged_count, unstaged_count = 0, 0
        status_map = {'M': 'Ⓜ', 'A': 'Ⓐ', 'D': 'Ⓓ', 'R': 'Ⓡ', 'C': 'Ⓒ', 'U': 'Ⓤ', '?': '❓'}

        for path, status in sorted(statuses.items()):
            staged_char, unstaged_char = status[0], status[1]
            normalized_path = path.replace('\\', '/') 
            
            if staged_char != ' ' and staged_char != '?':
                staged_count += 1
                symbol = status_map.get(staged_char, staged_char)
                self.staged_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")
            if unstaged_char != ' ':
                unstaged_count += 1
                symbol = status_map.get(unstaged_char, unstaged_char)
                self.changes_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")
            if staged_char == '?' and unstaged_char == '?':
                unstaged_count += 1
                symbol = status_map.get('?', '?')
                self.changes_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")

        self.staged_label.config(text=f"STAGED CHANGES ({staged_count})")
        self.changes_label.config(text=f"CHANGES ({unstaged_count})")
        
        if hasattr(self.parent_app, 'update_git_status_bar'):
            self.parent_app.update_git_status_bar(f"Branch: {branch_name}")


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

    def _display_colored_diff(self, diff_text):
        for line in diff_text.splitlines():
            if line.startswith('+') and not line.startswith('+++'): self.diff_viewer.insert(tk.END, line + '\n', "addition")
            elif line.startswith('-') and not line.startswith('---'): self.diff_viewer.insert(tk.END, line + '\n', "deletion")
            elif line.startswith('diff') or line.startswith('index') or line.startswith('@@'): self.diff_viewer.insert(tk.END, line + '\n', "header")
            else: self.diff_viewer.insert(tk.END, line + '\n')

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
        else:
            self.show_detailed_error(f"{action.capitalize()} Failed", output)

    def _init_repo(self):
        if messagebox.askyesno("Initialize Repository", "Are you sure you want to initialize a new Git repository?"):
            success, output = self.git_logic.init_repo()
            if success: messagebox.showinfo("Success", "Git repository initialized."); self.refresh()
            else: self.show_detailed_error("Initialization Failed", output)

    def _run_command_from_palette(self, event=None):
        command_str = self.command_entry.get()
        if not command_str: return
        if hasattr(self.parent_app, 'update_git_status_bar'):
            self.parent_app.update_git_status_bar(f"Running: git {command_str}...")
        
        threading.Thread(target=lambda: self.after(0, self._on_palette_command_done, *self.git_logic.run_arbitrary_command(command_str)), daemon=True).start()


    def _on_palette_command_done(self, success, output):
        self.show_detailed_error("Command Output", output)
        self.command_entry.delete(0, tk.END)
        self.refresh()

    def _show_log_viewer(self): ModernGitLogViewer(self, self.git_logic)
    def _show_branch_manager(self): BranchManager(self, self.git_logic)
    def show_detailed_error(self, title, details): DetailedErrorDialog(self, title, details)

class ModernGitLogViewer(tk.Toplevel):
    """A modern, graphical Git log/history viewer."""
    def __init__(self, parent, git_logic: GitLogic):
        super().__init__(parent)
        self.git_logic = git_logic
        self.sm = StyleManager()
        self.title("Git History")
        self.geometry("900x700")
        self.configure(bg=self.sm.COLOR_BG)

        self.commits_data = []
        self.commit_map = {}
        self.children_map = {}
        self.lane_colors = [self.sm.COLOR_ACCENT, "#3399CC", "#9933CC", "#CC9933", "#33CC99", "#CC3399"]
        
        self.dot_id_to_commit = {}
        self.tooltip = None
        self.hovered_dot_id = None

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        self.graph_canvas = tk.Canvas(self.main_frame, bg=self.sm.COLOR_BG_DARK, highlightthickness=0, width=200)
        self.graph_canvas.grid(row=0, column=0, sticky="ns")

        self.commit_text = tk.Text(self.main_frame, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_UI, wrap="none", bd=0, highlightthickness=0)
        self.commit_text.grid(row=0, column=1, sticky="nsew")

        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self._on_scroll)
        self.scrollbar.grid(row=0, column=2, sticky="ns")
        self.graph_canvas.config(yscrollcommand=self.scrollbar.set)
        self.commit_text.config(yscrollcommand=self.scrollbar.set)
        
        self.commit_text.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<Motion>", self._on_canvas_hover)
        self.graph_canvas.bind("<Leave>", self._hide_tooltip)
        
        self.commit_text.config(state="normal")
        self.commit_text.insert("1.0", "Loading history...")
        self.commit_text.config(state="disabled")
        threading.Thread(target=self._populate_log_worker, daemon=True).start()

        self.grab_set()

    def _populate_log_worker(self):
        success, log_data = self.git_logic.get_log_for_graph()
        self.after(0, self._update_ui_after_log, success, log_data)

    def _update_ui_after_log(self, success: bool, log_data: str):
        self.commit_text.config(state="normal")
        self.commit_text.delete("1.0", tk.END)
        self.commit_text.config(state="disabled")

        if not success:
            self.commit_text.config(state="normal")
            self.commit_text.insert(tk.END, f"Error loading log:\n{log_data}")
            self.commit_text.config(state="disabled")
            return
        
        lines = log_data.splitlines()
        for i, line in enumerate(lines):
            parts = line.split("|")
            if len(parts) == 6:
                chash, phash_str, author, date, refs, message = parts
                parents = phash_str.split()
                commit_info = {"hash": chash, "parents": parents, "author": author, "date": date, "refs": refs.strip(), "message": message}
                self.commits_data.append(commit_info)
                self.commit_map[chash] = i
                for p_hash in parents:
                    if p_hash not in self.children_map: self.children_map[p_hash] = []
                    self.children_map[p_hash].append(chash)
        
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
        
        commit_lanes = self.assign_lanes()
        
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
                        self.graph_canvas.create_line(x, y, x, y + row_height/2, p_x, p_y - row_height/2, p_x, p_y, fill=color, width=2, smooth=tk.TRUE)

            color = self.lane_colors[lane_index % len(self.lane_colors)]
            dot_id = self.graph_canvas.create_oval(x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius, fill=color, outline=self.sm.COLOR_BORDER, tags="commit_dot")
            self.dot_id_to_commit[dot_id] = commit

        total_height = len(self.commits_data) * row_height
        self.graph_canvas.config(scrollregion=(0, 0, self.graph_canvas.winfo_width(), total_height))

    def assign_lanes(self):
        commit_lanes = {}
        lanes = [] 
        for i, commit in enumerate(self.commits_data):
            chash = commit["hash"]
            my_lane = -1
            for lane_idx, lane_hash in enumerate(lanes):
                if lane_hash == chash:
                    my_lane = lane_idx
                    break
            if my_lane == -1:
                try: my_lane = lanes.index(None)
                except ValueError: my_lane = len(lanes); lanes.append(None)
            commit_lanes[chash] = my_lane
            lanes[my_lane] = commit["parents"][0] if commit["parents"] else None
            for p_hash in commit["parents"][1:]:
                p_lane = -1
                try: p_lane = lanes.index(None)
                except ValueError: p_lane = len(lanes); lanes.append(None)
                lanes[p_lane] = p_hash
        return commit_lanes

    def display_commits(self):
        self.commit_text.config(state="normal")
        self.commit_text.delete("1.0", tk.END)
        for commit in self.commits_data:
            container = ttk.Frame(self.commit_text, height=40, style="TFrame")
            msg_label = ttk.Label(container, text=commit["message"], anchor="w", font=self.sm.FONT_UI)
            msg_label.place(x=10, y=2)
            info_text = f"{commit['author']}  •  {commit['date']}"
            info_label = ttk.Label(container, text=info_text, anchor="w", font=(self.sm.FONT_UI[0], 9), foreground="#888888")
            info_label.place(x=10, y=20)
            
            if commit['refs']:
                refs_str = commit['refs'].strip('() ')
                refs_parts = [r.strip() for r in refs_str.split(',')] if refs_str else []

                current_x = info_label.winfo_reqwidth() + 20
                for ref in refs_parts:
                    ref_text = ref.replace('HEAD -> ', '')
                    is_remote_tracking = ref.startswith('origin/') or ref.startswith('upstream/') or '/' in ref_text
                    is_head = 'HEAD ->' in ref
                    
                    if is_head: color = self.sm.COLOR_ACCENT
                    elif is_remote_tracking: color = self.sm.COLOR_GREEN
                    else: color = self.sm.COLOR_ORANGE

                    ref_label = tk.Label(container, text=f" {ref_text} ", bg=color, fg="white", font=(self.sm.FONT_UI[0], 8, 'bold'))
                    ref_label.place(x=current_x, y=20)
                    current_x += ref_label.winfo_reqwidth() + 5
            self.commit_text.window_create(tk.END, window=container, stretch=1)
            self.commit_text.insert(tk.END, '\n')
        self.commit_text.config(state="disabled")

    def _on_canvas_hover(self, event):
        canvas = event.widget
        item_ids = canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        
        dot_id = None
        for item_id in reversed(item_ids):
            if "commit_dot" in canvas.gettags(item_id):
                dot_id = item_id
                break

        if dot_id is not None:
            if dot_id != self.hovered_dot_id:
                self.hovered_dot_id = dot_id
                self._show_tooltip(event, self.dot_id_to_commit[dot_id])
        else:
            self._hide_tooltip()

    def _show_tooltip(self, event, commit_data):
        self._hide_tooltip()
        
        x = event.x_root + 15
        y = event.y_root - 10
        
        self.tooltip = tk.Toplevel(self.graph_canvas)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        tooltip_text = f"{commit_data['message']}\n\n" \
                       f"Author: {commit_data['author']}\n" \
                       f"Date: {commit_data['date']}\n" \
                       f"Hash: {commit_data['hash'][:12]}"
        
        if commit_data['refs']:
            tooltip_text += f"\nRefs: {commit_data['refs']}"

        label = tk.Label(self.tooltip, text=tooltip_text, justify='left',
                         background="#252526", relief='solid', borderwidth=1,
                         font=("Segoe UI", 9, "normal"), foreground="#D4D4D4",
                         wraplength=400, anchor='w', padx=5, pady=5)
        label.pack(ipadx=1)
        
        self.tooltip.update_idletasks()
        tooltip_height = self.tooltip.winfo_height()
        self.tooltip.wm_geometry(f"+{x}+{event.y_root - tooltip_height - 5}")

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
    """Manages the autocomplete popup for the Git command entry."""
    COMMANDS = [
        ("commit", "Record changes to the repository"), ("add", "Add file contents to the index"),
        ("push", "Update remote refs along with associated objects"), ("pull", "Fetch from and integrate with another repository"),
        ("fetch", "Download objects and refs from another repository"), ("branch", "List, create, or delete branches"),
        ("checkout", "Switch branches or restore working tree files"), ("merge", "Join two or more development histories together"),
        ("rebase", "Reapply commits on top of another base tip"), ("status", "Show the working tree status"),
        ("log", "Show commit logs"), ("diff", "Show changes between commits, commit and working tree, etc"),
        ("remote", "Manage set of tracked repositories"), ("reset", "Reset current HEAD to the specified state"),
        ("stash", "Stash the changes in a dirty working directory away"),
    ]

    def __init__(self, entry_widget, parent_ui: SourceControlUI):
        self.entry = entry_widget
        self.parent_ui = parent_ui
        self.sm = StyleManager()
        self.window = tk.Toplevel(self.entry)
        self.window.wm_overrideredirect(True)
        self.window.withdraw()
        
        self.tree = ttk.Treeview(self.window, show="headings", columns=("Command", "Description"), selectmode="browse", height=5)
        self.tree.pack(fill="both", expand=True)
        self.tree.heading("Command", text="Command"); self.tree.heading("Description", text="Description")
        self.tree.column("Command", width=120, stretch=False); self.tree.column("Description", width=380)
        
        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<FocusOut>", self.on_focus_out)
        self.tree.bind("<Return>", self.on_select)
        self.tree.bind("<Button-1>", self.on_select)
        self.entry.bind("<Down>", self.focus_tree)
        self.entry.bind("<Up>", self.focus_tree)
    
    def on_focus_out(self, event):
        if str(event.widget) != str(self.tree):
            self.hide()

    def focus_tree(self, event):
        if self.tree.winfo_viewable() and self.tree.get_children():
            self.tree.focus_set()
            if not self.tree.selection():
                self.tree.selection_set(self.tree.get_children()[0])
            return "break"

    def on_key_release(self, event):
        if event.keysym in ("Return", "Escape", "FocusOut"): return
        if event.keysym in ("Up", "Down") and self.tree.winfo_viewable() and self.tree.get_children():
            self.focus_tree(event)
            return

        current_text = self.entry.get().split(" ")[0]
        if not current_text: self.hide(); return
        suggestions = [cmd for cmd in self.COMMANDS if cmd[0].startswith(current_text.lower())]
        if suggestions: self.show(suggestions)
        else: self.hide()

    def show(self, suggestions):
        self.tree.delete(*self.tree.get_children())
        for cmd, desc in suggestions:
            self.tree.insert("", "end", values=(cmd, desc))
        
        self.window.update_idletasks()
        
        entry_x = self.entry.winfo_rootx()
        entry_y = self.entry.winfo_rooty()
        
        max_visible_items = 5
        row_height = int(self.sm.style.lookup("Treeview", "rowheight") or 25)
        bbox_coords = self.tree.bbox("#0")
        bbox_y_coord = int(bbox_coords[3]) if bbox_coords and len(bbox_coords) > 3 else 0
        tree_height = min(len(suggestions), max_visible_items) * row_height + self.tree.winfo_reqheight() - bbox_y_coord
        tree_height = max(tree_height, 20)

        y = entry_y - int(tree_height) - 2
        
        self.window.geometry(f"500x{int(tree_height)}+{entry_x}+{y}")
        if not self.window.winfo_viewable(): self.window.deiconify()
        
        if self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])

    def hide(self):
        self.window.withdraw()

    def on_select(self, event):
        selection = self.tree.selection()
        if not selection: return
        item = self.tree.item(selection[0])
        command = item['values'][0]
        self.entry.delete(0, tk.END)
        self.entry.insert(0, f"{command} ")
        self.hide()
        self.entry.focus_set()
        return "break"