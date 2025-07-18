import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import os
import subprocess
import threading
from typing import List, Tuple, Dict, Callable, Optional, Any
import re
import shlex
import math
import time

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
        self.COLOR_YELLOW = "#E6A23C"  # For search highlights
        self.COLOR_SEARCH_BG = "#4a422a" # Background for search result text
        self.COLOR_PLACEHOLDER = "#888888"
        self.COLOR_CURRENT_BRANCH_HIGHLIGHT = "#FFD700" # Gold color for current branch

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
        
        self.style.configure("Console.TEntry",
                             fieldbackground=self.COLOR_BG_DARK,
                             foreground=self.COLOR_FG,
                             insertcolor=self.COLOR_FG,
                             borderwidth=0, relief="flat")


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

class CompletionWindow(tk.Toplevel):
    """A popup window for command completions."""
    def __init__(self, parent, entry_widget):
        super().__init__(parent)
        self.entry_widget = entry_widget
        self.sm = StyleManager()
        self.overrideredirect(True)
        
        self.listbox = tk.Listbox(self, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG,
                                 selectbackground=self.sm.COLOR_ACCENT_LIGHT,
                                 selectforeground=self.sm.COLOR_FG,
                                 bd=1, relief="solid", highlightthickness=0,
                                 exportselection=False, font=self.sm.FONT_CODE)
        self.listbox.pack(fill="both", expand=True)
        self.withdraw()

    def show(self, completions: List[str]):
        if not completions:
            self.withdraw()
            return

        self.listbox.delete(0, tk.END)
        for item in completions:
            self.listbox.insert(tk.END, item)
        
        x = self.entry_widget.winfo_rootx()
        y = self.entry_widget.winfo_rooty() + self.entry_widget.winfo_height()
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(0)

    def hide(self):
        self.withdraw()

    def move_selection(self, direction: int):
        if not self.winfo_viewable(): return
        current_selection = self.listbox.curselection()
        if not current_selection:
            self.listbox.selection_set(0)
            return
        
        next_idx = current_selection[0] + direction
        if 0 <= next_idx < self.listbox.size():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(next_idx)
            self.listbox.see(next_idx)

    def get_selected(self) -> Optional[str]:
        if not self.winfo_viewable() or not self.listbox.curselection():
            return None
        return self.listbox.get(self.listbox.curselection()[0])

class GitCommandAutocompleteManager:
    """Manages context-aware autocompletion for Git commands."""
    COMMANDS = [
        "add", "am", "archive", "bisect", "branch", "bundle", "checkout", "cherry-pick",
        "citool", "clean", "clone", "commit", "describe", "diff", "fetch", "format-patch",
        "gc", "grep", "gui", "init", "log", "merge", "mv", "notes", "pull", "push", "range-diff",
        "rebase", "reset", "revert", "rm", "shortlog", "show", "stash", "status", "submodule",
        "switch", "tag", "worktree"
    ]
    FLAGS: Dict[str, List[str]] = {
        "add": ["-A", "--all", "-u", "--update", "-n", "--dry-run", "-v", "--verbose", "--force", "-f", "--interactive", "-i", "--patch", "-p", "--no-edit", "--sparse", "--intent-to-add", "-N", "--refresh", "--ignore-errors", "--chmod", "--pathspec-from-file", "--pathspec-file-nul"],
        "commit": ["-m", "-a", "--amend", "--no-edit", "-v", "--verbose", "-q", "--quiet", "--dry-run", "--allow-empty", "--allow-empty-message", "--author", "--date", "--cleanup", "--file", "-F", "--signoff", "-s", "--no-verify", "-n", "--only", "-o", "--pathspec-from-file", "--pathspec-file-nul", "--template", "-t", "--edit", "-e", "--status", "--no-status", "--untracked-files", "-u", "--no-untracked-files", "--post-rewrite", "--fixup", "--squash", "--reset-author", "--short", "--branch", "--porcelain", "--long", "--null", "--date-order", "--reverse", "--walk-reflogs", "--pretty", "--abbrev-commit", "--no-abbrev-commit", "--relative-date", "--date", "--max-count", "-n", "--skip", "--since", "--after", "--until", "--before", "--committer", "--author", "--grep-reflog", "--grep", "-E", "-F", "--all-match", "--invert-grep", "-v", "--basic-regexp", "-G", "--all-match", "--regexp-ignore-case", "-i", "--remove-empty", "--merges", "--no-merges", "--min-parents", "--max-parents", "--no-walk", "--do-walk", "--parents", "--children", "--left-right", "--cherry-mark", "--cherry-pick", "--left-only", "--right-only", "--graph", "--decorate", "--source", "--use-bitmap-index", "--no-use-bitmap-index", "--progress", "--no-walk-reflogs", "--bisect", "--simplify-by-decoration", "--full-history", "--not", "--all", "--branches", "--tags", "--remotes", "--glob", "--exclude", "--exclude-standard", "--sparse-tree", "--filter-branch-by-commit-filter", "--show-pulls", "--show-merges", "--show-rebasess", "--show-cherry-picks", "--show-reverts", "--show-squashes", "--show-fast-forwards", "--show-linear-history", "--show-boundary"],
        "log": ["--oneline", "--graph", "--decorate", "--all", "-n", "-p", "--stat", "--author", "--grep", "--since", "--until", "--pretty", "--abbrev-commit", "--name-only", "--name-status", "--full-diff", "--follow", "--date-order", "--branches", "--tags", "--remotes"],
        "reset": ["--soft", "--mixed", "--hard", "--merge", "--keep", "HEAD"],
        "rebase": ["-i", "--continue", "--abort", "--skip", "--onto", "--keep-empty", "--fork-point", "--autosquash", "--autostash", "--committer-date-is-author-date", "--ignore-date", "--ignore-space-change", "--ignore-all-space", "--no-verify", "-n", "--quiet", "-q", "--verbose", "-v", "--stat", "--no-stat", "--apply", "--no-ff", "--ff-only", "--squash", "--fixup", "--reword", "--edit", "--drop", "--exec", "--root", "--merge", "--strategy", "--strategy-option", "--preserve-merges", "-p", "--rerere-autoupdate", "--no-rerere-autoupdate"],
        "push": ["--force", "--force-with-lease", "--tags", "-u", "--all", "--mirror", "--delete", "--dry-run", "-n", "--porcelain", "--follow-tags", "--no-verify", "-n", "--recurse-submodules", "--no-recurse-submodules", "--atomic", "--push-option", "-o", "--set-upstream", "--receive-pack", "--exec", "--progress", "--no-progress", "--verbose", "-v", "--quiet", "-q", "--signed"],
        "status": ["-s", "-b", "--long", "--porcelain", "--branch", "--show-stash"],
        "checkout": ["-b", "--track", "--orphan", "--force", "-f", "--ours", "--theirs", "--conflict", "--patch", "-p", "--merge", "--no-overlay", "--quiet", "-q", "--progress", "--no-progress", "--ignore-skip-worktree-bits", "--pathspec-from-file", "--pathspec-file-nul", "--sparse", "--recurse-submodules", "--no-recurse-submodules", "--dry-run", "-n", "--guess", "--no-guess", "--overlay", "--no-overlay", "--detach", "--", "--no-track", "--set-upstream", "-u"],
        "branch": ["-a", "-r", "-l", "--list", "-d", "-D", "-m", "-M", "-c", "-C", "--copy", "--move", "--force", "-f", "--create-reflog", "--no-create-reflog", "--color", "--no-color", "--column", "--no-column", "--contains", "--no-contains", "--merged", "--no-merged", "--remotes", "--all", "--ignore-case", "--sort", "--points-at", "--format", "--show-current", "--set-upstream-to", "-u", "--unset-upstream", "--edit-description", "--get-description", "--set-description", "--show-trackin", "--track", "--no-track", "--recurse-submodules", "--no-recurse-submodules", "--bare", "--mirror", "--single-branch", "--depth", "--shallow-since", "--shallow-exclude", "--dissociate", "--reference", "--separate-git-dir", "--template", "--upload-pack", "--recurse-submodules-default", "--jobs", "--tags", "--no-tags", "--no-checkout", "--no-hardlinks", "--local", "--no-local", "--shared", "--origin", "--reference-if-able", "--dissociate-refs", "--sparse", "--filter", "--initial-branch"],
        "merge": ["--no-ff", "--ff-only", "--squash", "--no-squash", "--commit", "--no-commit", "--edit", "--no-edit", "--no-verify", "-n", "--abort", "--continue", "--allow-unrelated-histories", "--strategy", "-s", "--strategy-option", "-X", "--rerere-autoupdate", "--no-rerere-autoupdate", "--signoff", "-s", "--log", "--no-log", "--stat", "--no-stat", "--fast-forward", "--no-fast-forward", "--ff", "--no-ff", "--into-name", "--autostash", "--no-autostash", "--gpg-sign", "-S", "--quit", "--cleanup"],
        "diff": ["--staged", "--cached", "--name-only", "--name-status", "--check", "--color", "--no-color", "--word-diff", "--unified", "-U", "--raw", "--patch", "-p", "--stat", "--summary", "--dirstat", "--numstat", "--shortstat", "--find-copies", "-C", "--find-renames", "-M", "--find-copies-harder", "--irreversible-delete", "--diff-filter", "--binary", "--text", "--exit-code", "--quiet", "--ext-diff", "--no-ext-diff", "--textconv", "--no-textconv", "--ignore-submodules", "--submodule", "--src-prefix", "--dst-prefix", "--no-prefix", "--line-prefix", "--ita-invisible-in-index", "--pickaxe-all", "-S", "--pickaxe-regex", "-G", "--diff-algorithm", "--indent-heuristic", "--minimal", "--patience", "--histogram", "--diff-merges", "--no-renames", "--relative", "-R", "--no-relative", "--patch-with-raw", "--full-index", "--cached", "--merge-base", "--dir-diff", "--no-dir-diff", "--compaction-heuristic", "--no-compaction-heuristic", "--color-words", "--no-color-words", "--color-moved", "--no-color-moved", "--abbrev", "--no-abbrev", "--break-rewrites", "--no-break-rewrites", "--dense-combined-diff", "--no-dense-combined-diff", "--ignore-cr-at-eol", "--ignore-space-at-eol", "--ignore-space-change", "--ignore-all-space", "--ignore-blank-lines", "--ignore-matching-lines", "--ignore-trailing-space", "--no-indent-heuristic", "--no-textconv", "--no-word-diff", "--output", "--output-indicator-new", "--output-indicator-old", "--output-indicator-context", "--patch-with-stat", "--patch-with-summary", "--no-patch-with-raw", "--no-patch-with-stat", "--no-patch-with-summary", "--recursive", "--no-recursive", "--submodule-diff", "--no-submodule-diff", "--unified-diff", "--no-unified-diff", "--ws-error-highlight", "--no-ws-error-highlight", "--ws-error-highlight=all", "--ws-error-highlight=none", "--ws-error-highlight=new", "--ws-error-highlight=old", "--ws-error-highlight=context", "--ws-error-highlight=lines", "--ws-error-highlight=trailing-whitespace", "--ws-error-highlight=indent-with-tabs", "--ws-error-highlight=tab-in-indent", "--ws-error-highlight=cr-at-eol", "--ws-error-highlight=blank-at-eol", "--ws-error-highlight=space-before-tab"],
        "fetch": ["--all", "--append", "--atomic", "--deepen", "--depth", "--dry-run", "-n", "--force", "--keep", "--multiple", "--no-tags", "--prune", "-p", "--recurse-submodules", "--no-recurse-submodules", "--set-upstream", "-u", "--tags", "--update-head-ok", "--upload-pack", "--verbose", "-v", "--quiet", "-q", "--progress", "--no-progress", "--jobs"],
        "pull": ["--all", "--append", "--autostash", "--no-autostash", "--commit", "--no-commit", "--edit", "--no-edit", "--ff", "--no-ff", "--ff-only", "--gpg-sign", "-S", "--log", "--no-log", "--no-rebase", "--no-recurse-submodules", "--no-stat", "--no-tags", "--no-verify", "-n", "--progress", "--no-progress", "--prune", "-p", "--quiet", "-q", "--rebase", "--recurse-submodules", "--set-upstream", "-u", "--stat", "--tags", "--verbose", "-v", "--verify-signatures", "--strategy", "-s", "--strategy-option", "-X", "--allow-unrelated-histories", "--ff-only", "--no-ff-only", "--rebase-merges", "--no-rebase-merges", "--rebase-skip", "--rebase-continue", "--rebase-abort", "--rebase-update-refs", "--rebase-preserve-merges", "--rebase-fork-point", "--rebase-autosquash", "--rebase-autostash", "--rebase-committer-date-is-author-date", "--rebase-ignore-date", "--rebase-ignore-space-change", "--rebase-ignore-all-space", "--rebase-no-verify", "--rebase-quiet", "--rebase-verbose", "--rebase-stat", "--rebase-no-stat", "--rebase-apply", "--rebase-no-apply", "--rebase-force-rebase", "--rebase-no-force-rebase", "--rebase-strategy", "--rebase-strategy-option", "--rebase-preserve-merges", "--rebase-rerere-autoupdate", "--rebase-no-rerere-autoupdate", "--rebase-gpg-sign", "--rebase-cleanup"],
        "clone": ["--bare", "--branch", "-b", "--depth", "--dissociate", "--filter", "--jobs", "--local", "-l", "--mirror", "--no-checkout", "--no-hardlinks", "--origin", "-o", "--progress", "--no-progress", "--recurse-submodules", "--no-recurse-submodules", "--reference", "--separate-git-dir", "--shared", "--single-branch", "--shallow-exclude", "--shallow-since", "--sparse", "--template", "--upload-pack", "--verbose", "-v", "--quiet", "-q", "--config", "-c", "--bundle-uri", "--no-remote-submodules", "--server-option", "--reject-shallow", "--sparse-checkout", "--no-sparse-checkout", "--filter=blob:none", "--filter=tree:0", "--filter=commit:0", "--filter=combined:0", "--filter=submodule:none", "--filter=sparse:oid", "--filter=sparse:path", "--filter=sparse:rev", "--filter=sparse:tree", "--filter=sparse:object"],
        "init": ["--bare", "--template", "--separate-git-dir", "--shared", "--initial-branch", "-b", "--object-format"],
        "rm": ["-f", "--force", "-n", "--dry-run", "-r", "--recursive", "--cached", "--ignore-unmatch", "--pathspec-from-file", "--pathspec-file-nul", "--"],
        "mv": ["-f", "--force", "-n", "--dry-run", "--pathspec-from-file", "--pathspec-file-nul", "--"],
        "stash": ["push", "save", "list", "show", "pop", "apply", "branch", "clear", "drop", "create", "store", "describ", "on", "--keep-index", "-k", "--include-untracked", "-u", "--all", "-a", "--patch", "-p", "--message", "-m", "--quiet", "-q", "--pathspec-from-file", "--pathspec-file-nul", "--"],
        "show": ["--pretty", "--format", "--abbrev-commit", "--no-abbrev-commit", "--oneline", "--encoding", "--notes", "--no-notes", "--show-signature", "--no-show-signature", "--raw", "-s", "--patch", "-p", "--stat", "--numstat", "--shortstat", "--name-only", "--name-status", "--check", "--full-index", "--binary", "--text", "--diff-filter", "--find-copies", "-C", "--find-renames", "-M", "--find-copies-harder", "--irreversible-delete", "--diff-algorithm", "--indent-heuristic", "--minimal", "--patience", "--histogram", "--diff-merges", "--no-renames", "--relative", "-R", "--no-relative", "--patch-with-raw", "--full-index", "--cached", "--merge-base", "--dir-diff", "--no-dir-diff", "--compaction-heuristic", "--no-compaction-heuristic", "--color-words", "--no-color-words", "--color-moved", "--no-color-moved", "--abbrev", "--no-abbrev", "--break-rewrites", "--no-break-rewrites", "--dense-combined-diff", "--no-dense-combined-diff", "--ignore-cr-at-eol", "--ignore-space-at-eol", "--ignore-space-change", "--ignore-all-space", "--ignore-blank-lines", "--ignore-matching-lines", "--ignore-trailing-space", "--no-indent-heuristic", "--no-textconv", "--no-word-diff", "--output", "--output-indicator-new", "--output-indicator-old", "--output-indicator-context", "--patch-with-stat", "--patch-with-summary", "--no-patch-with-raw", "--no-patch-with-stat", "--no-patch-with-summary", "--recursive", "--no-recursive", "--submodule-diff", "--no-submodule-diff", "--unified-diff", "--no-unified-diff", "--ws-error-highlight", "--no-ws-error-highlight", "--ws-error-highlight=all", "--ws-error-highlight=none", "--ws-error-highlight=new", "--ws-error-highlight=old", "--ws-error-highlight=context", "--ws-error-highlight=lines", "--ws-error-highlight=trailing-whitespace", "--ws-error-highlight=indent-with-tabs", "--ws-error-highlight=tab-in-indent", "--ws-error-highlight=cr-at-eol", "--ws-error-highlight=blank-at-eol", "--ws-error-highlight=space-before-tab", "--decorate", "--source", "--use-bitmap-index", "--no-use-bitmap-index", "--progress", "--no-walk-reflogs", "--bisect", "--simplify-by-decoration", "--full-history", "--not", "--all", "--branches", "--tags", "--remotes", "--glob", "--exclude", "--exclude-standard", "--sparse-tree", "--filter-branch-by-commit-filter", "--show-pulls", "--show-merges", "--show-rebasess", "--show-cherry-picks", "--show-reverts", "--show-squashes", "--show-fast-forwards", "--show-linear-history", "--show-boundary"]
    }
    
    def __init__(self, git_logic: 'GitLogic'):
        self.git_logic = git_logic
        self.cached_files: List[str] = []
        self.last_status_check_time = 0
        self.status_cache_duration = 5 # seconds

    def _get_tracked_files(self) -> List[str]:
        """Fetches tracked files for autocompletion, with a simple cache."""
        current_time = time.time()
        if current_time - self.last_status_check_time < self.status_cache_duration and self.cached_files:
            return self.cached_files
        
        rc, stdout, _ = self.git_logic._run_command(["ls-files"])
        if rc == 0:
            self.cached_files = stdout.splitlines()
            self.last_status_check_time = current_time
            return self.cached_files
        return []

    def get_completions(self, text_before_cursor: str) -> List[str]:
        """Returns a list of potential completions based on the input text."""
        parts = shlex.split(text_before_cursor) # Use shlex to handle quoted paths
        
        if not parts: return self.COMMANDS # Suggest commands if input is empty

        command = parts[0]
        current_word = parts[-1] if not text_before_cursor.endswith(' ') else ""

        # Autocomplete for main commands
        if len(parts) == 1 and not text_before_cursor.endswith(' '):
            return [cmd for cmd in self.COMMANDS if cmd.startswith(current_word)]

        # Autocomplete for flags
        if command in self.FLAGS:
            if current_word.startswith("-"):
                return [f for f in self.FLAGS[command] if f.startswith(current_word)]
            
            # Autocomplete for branches/commits for specific commands
            if command in ["checkout", "switch", "branch", "merge", "rebase", "reset"]:
                _, branches, _ = self.git_logic.get_branches()
                all_branch_names = [b.replace("* ", "").replace("remotes/", "") for b in branches]
                # Also include commit hashes for rebase/reset/checkout
                # For simplicity, we can fetch a few recent commit hashes
                _, log_output, _ = self.git_logic._run_command(["log", "--oneline", "-n", "20"])
                recent_hashes = [line.split(' ')[0] for line in log_output.splitlines() if line]
                
                all_suggestions = sorted(list(set(all_branch_names + recent_hashes)))
                return [s for s in all_suggestions if s.startswith(current_word)]
            
            # Autocomplete for files for specific commands
            if command in ["add", "rm", "diff", "checkout", "restore"]: # Add other file-related commands
                all_files = self._get_tracked_files()
                return [f for f in all_files if f.startswith(current_word)]

        return []

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
        # For arbitrary commands, combine stdout and stderr for a complete picture
        output = (stdout + "\n" + stderr).strip()
        return rc == 0, output


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
        # Using a rare delimiter (\x01) to safely parse subject and body
        log_format = "%H\x01%P\x01%an\x01%ar\x01%d\x01%s\x01%b"
        # Removed commit limit for full log.
        rc, stdout, stderr = self._run_command(["log", "--all", f"--pretty=format:{log_format}%n\x02", "--date-order", "--color=never", "--decorate=full"])
        if rc == 0:
            return True, stdout.strip('\n\x02').replace('\x02', '')
        return False, stderr


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

    def stage_files(self, filepaths: List[str]): return self._run_command(["add", "--"] + filepaths)
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
        self.conflicts_tree_frame: Optional[TreeViewFrame] = None
        self.conflicts_label: Optional[ttk.Label] = None
        self.command_history: List[str] = []
        self.command_history_index = -1
        self.autocomplete_manager = GitCommandAutocompleteManager(self.git_logic)
        self.git_prefix_warning_shown = False
        self.completion_window: Optional[CompletionWindow] = None

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

        # --- Main View is now a Notebook ---
        self.main_notebook = ttk.Notebook(self)
        
        self._create_changes_tab()
        self._create_console_tab()
    
    def _create_changes_tab(self):
        changes_tab_frame = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(changes_tab_frame, text="Changes")

        changes_tab_pane = ttk.PanedWindow(changes_tab_frame, orient=tk.VERTICAL)
        changes_tab_pane.pack(fill="both", expand=True)
        
        files_frame_container = ttk.Frame(changes_tab_pane)
        changes_tab_pane.add(files_frame_container, weight=3)
        files_frame_container.grid_rowconfigure(0, weight=1)
        files_frame_container.grid_columnconfigure(0, weight=1)

        files_and_diff_pane = ttk.PanedWindow(files_frame_container, orient=tk.VERTICAL)
        files_and_diff_pane.grid(row=0, column=0, sticky="nsew")

        files_frame = ttk.Frame(files_and_diff_pane)
        files_and_diff_pane.add(files_frame, weight=3)
        files_frame.grid_rowconfigure(1, weight=1); files_frame.grid_rowconfigure(3, weight=1); files_frame.grid_rowconfigure(5, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        # --- Merge Conflicts Section (Initially hidden) ---
        self.conflicts_label = ttk.Label(files_frame, text="MERGE CONFLICTS", font=(self.sm.FONT_UI[0], 9, 'bold'), foreground=self.sm.COLOR_CONFLICT)
        self.conflicts_label.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        self.conflicts_tree_frame = TreeViewFrame(files_frame, self._on_conflict_double_click, self.workspace_root_dir)
        self.conflicts_tree_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.conflicts_tree = self.conflicts_tree_frame.tree
        self.conflicts_label.grid_remove()
        self.conflicts_tree_frame.grid_remove()

        # --- Staged Changes Section ---
        self.staged_label = ttk.Label(files_frame, text="STAGED CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.staged_label.grid(row=2, column=0, sticky="ew", pady=(0, 2))
        staged_frame_widget = TreeViewFrame(files_frame, self._on_file_double_click, self.workspace_root_dir)
        staged_frame_widget.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        self.staged_tree = staged_frame_widget.tree
        self.staged_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.staged_tree, is_staged=True))
        self.staged_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=False))

        # --- Unstaged Changes Section ---
        self.changes_label = ttk.Label(files_frame, text="CHANGES", font=(self.sm.FONT_UI[0], 9, 'bold'))
        self.changes_label.grid(row=4, column=0, sticky="ew", pady=(0, 2))
        changes_frame_widget = TreeViewFrame(files_frame, self._on_file_double_click, self.workspace_root_dir)
        changes_frame_widget.grid(row=5, column=0, sticky="nsew")
        self.changes_tree = changes_frame_widget.tree
        self.changes_tree.bind("<Button-3>", lambda e: self._show_context_menu(e, self.changes_tree, is_staged=False))
        self.changes_tree.bind("<<TreeviewSelect>>", lambda e: self._show_diff_for_selection(e, is_staged=False))
        
        # --- Diff Viewer ---
        diff_pane = ttk.Frame(files_and_diff_pane)
        files_and_diff_pane.add(diff_pane, weight=2)
        diff_pane.grid_rowconfigure(0, weight=1); diff_pane.grid_columnconfigure(0, weight=1)
        self.diff_viewer = scrolledtext.ScrolledText(diff_pane, wrap="none", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.diff_viewer.grid(row=0, column=0, sticky="nsew")
        self.diff_viewer.tag_config("addition", foreground=self.sm.COLOR_GREEN)
        self.diff_viewer.tag_config("deletion", foreground=self.sm.COLOR_RED)
        self.diff_viewer.tag_config("header", foreground=self.sm.COLOR_BLUE, font=(self.sm.FONT_CODE[0], self.sm.FONT_CODE[1], "bold"))
        self.diff_viewer.config(state="disabled")

        # --- Commit Area ---
        commit_area_frame = ttk.Frame(changes_tab_pane, style="Header.TFrame", padding=(10,5,10,10))
        changes_tab_pane.add(commit_area_frame, weight=0)
        self._create_commit_area(commit_area_frame)
        
    def _create_console_tab(self):
        console_frame = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(console_frame, text="Console")

        console_frame.grid_rowconfigure(0, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        self.console_output = scrolledtext.ScrolledText(console_frame, wrap="word", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.console_output.grid(row=0, column=0, sticky="nsew")
        self.console_output.tag_config("command", foreground=self.sm.COLOR_ACCENT)
        self.console_output.tag_config("error", foreground=self.sm.COLOR_RED)
        self.console_output.tag_config("info", foreground=self.sm.COLOR_ORANGE)
        self.console_output.config(state="disabled")

        self.console_input = ttk.Entry(console_frame, font=self.sm.FONT_CODE, style="Console.TEntry")
        self.console_input.grid(row=1, column=0, sticky="ew", pady=(5,0))
        
        # Ensure completion_window is initialized here
        self.completion_window = CompletionWindow(self, self.console_input)

        # --- Bindings for Console ---
        self.console_input.bind("<Return>", self._execute_console_command)
        self.console_input.bind("<Up>", self._cycle_history_up)
        self.console_input.bind("<Down>", self._cycle_history_down)
        self.console_input.bind("<KeyRelease>", self._on_key_release)
        self.console_input.bind("<Tab>", self._accept_completion)
        if self.completion_window:
            self.console_input.bind("<Escape>", lambda e: self.completion_window.hide()) #type: ignore

        # Placeholder logic
        self.placeholder = "Enter git command (e.g., status -s)"
        self.console_input.insert(0, self.placeholder)
        self.console_input.config(foreground=self.sm.COLOR_PLACEHOLDER)
        self.console_input.bind("<FocusIn>", self._on_console_focus_in)
        self.console_input.bind("<FocusOut>", self._on_console_focus_out)

    def _on_console_focus_in(self, event=None):
        if self.console_input.get() == self.placeholder:
            self.console_input.delete(0, tk.END)
            self.console_input.config(foreground=self.sm.COLOR_FG)

    def _on_console_focus_out(self, event=None):
        if not self.console_input.get():
            self.console_input.insert(0, self.placeholder)
            self.console_input.config(foreground=self.sm.COLOR_PLACEHOLDER)
            if self.completion_window:
                self.completion_window.hide()

    def _execute_console_command(self, event=None):
        if self.completion_window and self.completion_window.winfo_viewable():
            return self._accept_completion(event)

        command = self.console_input.get().strip()
        if not command or command == self.placeholder: return
        
        original_command = command
        if command.lower().strip() == 'git':
            self._update_console_output("Please enter a git command after 'git'. (e.g., 'status', not 'git status')", is_error=True)
            return

        if command.lower().startswith("git "):
            command = command[4:].strip()
            if not self.git_prefix_warning_shown:
                 self._update_console_output("(Note: The 'git' prefix is not needed and was automatically removed.)", is_info=True)
                 self.git_prefix_warning_shown = True

        if command:
            self.command_history.append(original_command)
            self.command_history_index = len(self.command_history)

        self.console_output.config(state="normal")
        self.console_output.insert(tk.END, f"$ git {command}\n", "command")
        self.console_output.config(state="disabled")

        self.console_input.delete(0, tk.END)
        
        threading.Thread(target=self._run_console_command_thread, args=(command,), daemon=True).start()
        return "break"

    def _run_console_command_thread(self, command):
        success, output = self.git_logic.run_arbitrary_command(command)
        self.after(0, self._update_console_output, output, not success)

    def _update_console_output(self, output, is_error=False, is_info=False):
        self.console_output.config(state="normal")
        if is_error: tag = "error"
        elif is_info: tag = "info"
        else: tag = "output"
        
        self.console_output.insert(tk.END, output + "\n\n", tag)
        self.console_output.see(tk.END)
        self.console_output.config(state="disabled")
        
        if not is_info:
            self.refresh()
            if self.history_view and self.history_view.winfo_exists():
                self.history_view.populate_log()

    def _cycle_history_up(self, event=None):
        if self.completion_window and self.completion_window.winfo_viewable():
            self.completion_window.move_selection(-1)
        elif self.command_history:
            self.command_history_index = max(0, self.command_history_index - 1)
            self._on_console_focus_in(None)
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, self.command_history[self.command_history_index])
        return "break"

    def _cycle_history_down(self, event=None):
        if self.completion_window and self.completion_window.winfo_viewable():
            self.completion_window.move_selection(1)
        elif self.command_history:
            self.command_history_index += 1
            if self.command_history_index < len(self.command_history):
                self._on_console_focus_in(None)
                self.console_input.delete(0, tk.END)
                self.console_input.insert(0, self.command_history[self.command_history_index])
            else:
                self.command_history_index = len(self.command_history)
                self.console_input.delete(0, tk.END)
        return "break"

    def _on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return

        text = self.console_input.get()
        completions = self.autocomplete_manager.get_completions(text)
        if completions:
            if self.completion_window:
                self.completion_window.show(completions)
        else:
            if self.completion_window:
                self.completion_window.hide()

    def _accept_completion(self, event=None):
        if self.completion_window:
            selected = self.completion_window.get_selected()
            if selected:
                text = self.console_input.get()
                parts = shlex.split(text)
                
                # If the current word is a partial flag or filename, replace it
                if text.endswith(' ') or not parts: # If ends with space or no parts, just append
                    new_text = text + selected + " "
                else: # Replace the last part
                    base = " ".join(parts[:-1])
                    new_text = (base + " " if base else "") + selected + " "
                
                self.console_input.delete(0, tk.END)
                self.console_input.insert(0, new_text)
                self.console_input.icursor(tk.END)
                self.completion_window.hide()
        return "break"

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
            self.main_notebook.grid_remove()
            self.init_view_frame.grid(row=0, column=0, sticky="nsew")
            if hasattr(self.parent_app, 'update_git_status_bar'):
                self.parent_app.update_git_status_bar("Not a git repository")
            return

        self.init_view_frame.grid_remove()
        self.main_notebook.grid(row=0, column=0, sticky="nsew")
        
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
                # TODO: "INCOMING bug" - Displaying the specific incoming branch name for merge conflicts
                # requires more advanced Git plumbing commands (e.g., git merge-tree, git ls-files -u)
                # to determine the conflicting branches. The current `git status --porcelain` output
                # does not directly provide this information. This is a complex enhancement for future phases.
                continue

            staged_char, unstaged_char = status[0], status[1]
            
            if staged_char != ' ' and staged_char != '?':
                staged_count += 1
                symbol = status_map.get(staged_char, staged_char)
                self.staged_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")
            
            if unstaged_char != ' ':
                unstaged_count += 1
                symbol = status_map.get(unstaged_char, unstaged_char)
                self.changes_tree.insert("", "end", iid=normalized_path, text=f" {symbol}  {normalized_path}")

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
        # Focus the 'Changes' tab before committing
        self.main_notebook.select(0)
        self.update_idletasks()

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
        # Check if the tab already exists by its text
        for i, tab_id in enumerate(self.main_notebook.tabs()):
            if self.main_notebook.tab(tab_id, "text") == "History":
                self.main_notebook.select(i)
                return
        
        self.history_view = ModernGitLogViewer(self.main_notebook, self)
        self.main_notebook.add(self.history_view, text="History")
        self.main_notebook.select(self.main_notebook.tabs()[-1])


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
        self.hovered_dot_id = None
        self.hovered_lane_index = -1 # New: Track the hovered lane for highlighting
        self.row_height = 40 
        self.lane_spacing = 30 
        self.tooltip_window: Optional[tk.Toplevel] = None # Renamed to avoid conflict with Tooltip class

        # New: Toggle for cleaner view
        self.cleaner_view_enabled = tk.BooleanVar(value=False)
        self.cleaner_view_enabled.trace_add("write", self._toggle_cleaner_view)
        
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_pane)
        main_pane.add(top_frame, weight=3)
        top_frame.grid_rowconfigure(0, weight=1)
        top_frame.grid_columnconfigure(1, weight=1)

        # Canvas for the graph
        self.graph_canvas = tk.Canvas(top_frame, bg=self.sm.COLOR_BG_DARK, highlightthickness=0, width=200)
        self.graph_canvas.grid(row=0, column=0, sticky="ns")

        # Text area for commit messages
        self.commit_text = tk.Text(top_frame, bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_UI, wrap="none", bd=0, highlightthickness=0, spacing2=8)
        self.commit_text.grid(row=0, column=1, sticky="nsew")

        # Vertical Scrollbar for both canvas and text
        self.vscrollbar = ttk.Scrollbar(top_frame, orient="vertical", command=self._on_vertical_scroll)
        self.vscrollbar.grid(row=0, column=2, sticky="ns")
        self.graph_canvas.config(yscrollcommand=self.vscrollbar.set)
        self.commit_text.config(yscrollcommand=self.vscrollbar.set)

        # Horizontal Scrollbar for the canvas
        self.hscrollbar = ttk.Scrollbar(top_frame, orient="horizontal", command=self.graph_canvas.xview)
        self.hscrollbar.grid(row=1, column=0, columnspan=2, sticky="ew") # Position below canvas and text
        self.graph_canvas.config(xscrollcommand=self.hscrollbar.set)

        bottom_frame = ttk.Frame(main_pane)
        main_pane.add(bottom_frame, weight=2)
        bottom_frame.grid_rowconfigure(0, weight=1); bottom_frame.grid_columnconfigure(0, weight=1)

        self.commit_detail_viewer = scrolledtext.ScrolledText(bottom_frame, wrap="none", bg=self.sm.COLOR_BG_DARK, fg=self.sm.COLOR_FG, font=self.sm.FONT_CODE, relief="flat", bd=0)
        self.commit_detail_viewer.grid(row=0, column=0, sticky="nsew")
        self.commit_detail_viewer.tag_config("addition", foreground=self.sm.COLOR_GREEN); self.commit_detail_viewer.tag_config("deletion", foreground=self.sm.COLOR_RED); self.commit_detail_viewer.tag_config("header", foreground=self.sm.COLOR_BLUE, font=(self.sm.FONT_CODE[0], self.sm.FONT_CODE[1], "bold"))
        self.commit_detail_viewer.config(state="disabled")

        # Bindings for scrolling and interaction
        self.commit_text.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.graph_canvas.bind("<Motion>", self._on_canvas_hover)
        self.graph_canvas.bind("<Leave>", self._hide_tooltip)
        self.graph_canvas.bind("<Button-1>", self._on_canvas_click) 
        self.commit_text.bind("<Button-3>", self._show_commit_context_menu)
        
        # New: Add the "Clean History" checkbox
        self._create_toolbar(top_frame)

        self.populate_log()

    def _create_toolbar(self, parent_frame):
        toolbar = ttk.Frame(parent_frame, style="Header.TFrame")
        # Position in top-right of the commit_text area, spanning across columns 0 and 1
        toolbar.grid(row=0, column=1, sticky="ne", padx=5, pady=5) 

        # Ensure the checkbox style is configured.
        self.sm.style.configure("TCheckbutton", background=self.sm.COLOR_BG_DARK, foreground=self.sm.COLOR_FG)
        self.sm.style.map("TCheckbutton", background=[('active', self.sm.COLOR_BG_LIGHT)])

        clean_history_checkbox = ttk.Checkbutton(
            toolbar,
            text="Clean History",
            variable=self.cleaner_view_enabled,
            onvalue=True,
            offvalue=False,
            style="TCheckbutton"
        )
        clean_history_checkbox.pack(side="right", padx=5, pady=2)
        Tooltip(clean_history_checkbox, "Toggle to simplify the graph by hiding merge commits and special entries.")

    def _toggle_cleaner_view(self, *args):
        """Callback for the cleaner view toggle."""
        self.populate_log() # Re-populate and redraw the graph with new filtering rules

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
        current_branch = self.git_logic.get_current_branch()
        self.after(0, self._update_ui_after_log, success, log_data, current_branch)

    def _update_ui_after_log(self, success: bool, log_data: str, current_branch: str):
        self.commits_data = []
        self.commit_map = {}
        self.current_branch_name = current_branch # Store current branch name

        if not success:
            self.commit_text.config(state="normal")
            self.commit_text.delete("1.0", tk.END)
            self.commit_text.insert(tk.END, f"Error loading log:\n{log_data}")
            self.commit_text.config(state="disabled")
            return
        
        lines = log_data.splitlines()
        for i, line in enumerate(lines):
            parts = line.split("\x01") 
            if len(parts) == 7:
                chash, phash_str, author, date, refs, message_subject, message_body = parts
                parents = phash_str.split()
                
                # Always filter out stash-related entries from the main history graph
                stash_message_patterns = [
                    r"^\s*WIP on ",
                    r"^\s*index on ",
                    r"^\s*untracked files on ",
                    r"^\s*On " # Catches "On branch_name: commit_message"
                ]
                if "(refs/stash)" in refs or \
                   any(re.search(pattern, message_subject) for pattern in stash_message_patterns):
                    continue
                
                # Apply "Clean History" toggle for merge commits
                if self.cleaner_view_enabled.get() and len(parents) > 1:
                    continue

                commit_info = {"hash": chash, "parents": parents, "author": author, "date": date, "refs": refs.strip(), "message": message_subject, "body": message_body, "log_line_num": i}
                self.commits_data.append(commit_info)
                self.commit_map[chash] = len(self.commits_data) - 1 # Map hash to its index in the *filtered* list
        
        self.draw_graph()
        self.display_commits()

    def _on_vertical_scroll(self, *args):
        self.graph_canvas.yview(*args)
        self.commit_text.yview(*args)

    def _on_mousewheel(self, event):
        # Vertical scrolling
        if event.state & 0x1: # Shift key for horizontal scrolling (Windows/Linux)
            self.graph_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        else:
            self.graph_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            self.commit_text.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break"

    def draw_graph(self):
        self.graph_canvas.delete("all")
        self.dot_id_to_commit.clear()
        dot_radius = 4
        
        commit_lanes = self._assign_lanes()
        
        # Keep track of line IDs for highlighting
        self.lane_lines = {lane_idx: [] for lane_idx in set(commit_lanes.values())} # {lane_index: [list of line IDs]}
        self.dot_objects = {} # {commit_hash: dot_id}
        self.commit_lane_map = commit_lanes # Store for easy lookup

        for i, commit in enumerate(self.commits_data):
            y = i * self.row_height + (self.row_height / 2)
            lane_index = commit_lanes.get(commit["hash"], 0)
            x = 30 + lane_index * self.lane_spacing 
            
            for p_hash in commit["parents"]:
                # Only draw lines to parents that are also in the *filtered* commits_data
                if p_hash in self.commit_map:
                    p_index = self.commit_map[p_hash] 
                    p_lane_index = commit_lanes.get(p_hash, 0)
                    p_y = p_index * self.row_height + (self.row_height / 2)
                    p_x = 30 + p_lane_index * self.lane_spacing 
                    color = self.lane_colors[lane_index % len(self.lane_colors)]
                    
                    if p_lane_index == lane_index:
                        line_id = self.graph_canvas.create_line(x, y, p_x, p_y, fill=color, width=2, tags=(f"lane_{lane_index}_line"))
                    else:
                        # Curved line for merges/divergences
                        cp1_x = x
                        cp1_y = y + self.row_height / 2
                        cp2_x = p_x
                        cp2_y = p_y - self.row_height / 2
                        line_id = self.graph_canvas.create_line(x, y, cp1_x, cp1_y, cp2_x, cp2_y, p_x, p_y, fill=color, width=2, smooth=True, splinesteps=12, tags=(f"lane_{lane_index}_line")) #type: ignore
                    self.lane_lines[lane_index].append(line_id)

            color = self.lane_colors[lane_index % len(self.lane_colors)]
            dot_id = self.graph_canvas.create_oval(x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius, fill=color, outline=self.sm.COLOR_BORDER, tags=(f"commit_dot_{commit['hash']}", f"lane_dot_{lane_index}"))
            self.dot_id_to_commit[dot_id] = commit
            self.dot_objects[commit['hash']] = dot_id # Store dot ID by hash for easy lookup

        total_height = len(self.commits_data) * self.row_height 
        max_lane = max(commit_lanes.values()) if commit_lanes else 0
        total_width = 30 + (max_lane + 1) * self.lane_spacing + 20 
        self.graph_canvas.config(scrollregion=(0, 0, total_width, total_height))


    def _assign_lanes(self):
        """
        Assigns a horizontal 'lane' to each commit for graph visualization.
        This is a basic greedy algorithm. It tries to reuse lanes that are
        no longer active.
        """
        commit_lanes = {}  
        active_lanes: List[Optional[str]] = [] 

        for commit in self.commits_data:
            chash = commit["hash"]
            parents = commit["parents"]

            assigned_lane = -1

            # 1. Check if this commit is a direct continuation of an existing branch line.
            for i, active_commit_in_lane in enumerate(active_lanes):
                if active_commit_in_lane == chash:
                    assigned_lane = i
                    break
            
            # 2. If not a direct continuation, try to find an empty lane to reuse.
            if assigned_lane == -1:
                try:
                    assigned_lane = active_lanes.index(None) 
                except ValueError:
                    assigned_lane = len(active_lanes)
                    active_lanes.append(None) 

            commit_lanes[chash] = assigned_lane

            # Update the active_lanes for the current commit's parents.
            # Only consider parents that are in the *filtered* commits_data
            valid_parents = [p for p in parents if p in self.commit_map]

            if valid_parents:
                active_lanes[assigned_lane] = valid_parents[0]
            else:
                active_lanes[assigned_lane] = None

            # For merge parents (beyond the first one), assign them to new or existing free lanes.
            for p_hash in valid_parents[1:]:
                found_merge_lane = False
                for i, active_commit_in_in_lane in enumerate(active_lanes):
                    if active_commit_in_in_lane == p_hash:
                        found_merge_lane = True
                        break
                
                if not found_merge_lane:
                    try:
                        free_lane_idx = active_lanes.index(None)
                        active_lanes[free_lane_idx] = p_hash
                        found_merge_lane = True
                    except ValueError:
                        active_lanes.append(p_hash)
                        found_merge_lane = True 

        while active_lanes and active_lanes[-1] is None:
            active_lanes.pop()

        return commit_lanes


    def display_commits(self):
        self.commit_text.config(state="normal")
        self.commit_text.delete("1.0", tk.END)

        self.commit_text.tag_configure("msg", font=self.sm.FONT_UI)
        self.commit_text.tag_configure("info", font=(self.sm.FONT_UI[0], 9), foreground="#999999")
        self.commit_text.tag_configure("hash", font=self.sm.FONT_CODE, foreground="#777777")
        self.commit_text.tag_configure("commit_block", spacing1=10, spacing3=10)
        self.commit_text.tag_configure("current_branch_text", background=self.sm.COLOR_CURRENT_BRANCH_HIGHLIGHT, foreground=self.sm.COLOR_BG_DARK, font=(self.sm.FONT_UI[0], 8, 'bold'))


        for commit in self.commits_data:
            start_index = self.commit_text.index(tk.END)
            self.commit_text.insert(tk.END, f"{commit['message']}  ", "msg")
            
            # Check for current branch and apply highlight
            is_current_branch_head = False
            if self.current_branch_name and f"HEAD -> {self.current_branch_name}" in commit['refs']:
                is_current_branch_head = True

            if commit['refs']:
                refs_parts = [r.strip() for r in commit['refs'].strip('() ').split(',') if r.strip()]
                for ref in refs_parts:
                    ref_text = ref.replace('HEAD -> ', '')
                    is_head = 'HEAD ->' in ref
                    is_remote = '/' in ref_text and not is_head
                    
                    if is_current_branch_head and ref_text == self.current_branch_name:
                        # Apply specific tag for current branch
                        ref_label = tk.Label(self.commit_text, text=f" {ref_text} ", bg=self.sm.COLOR_CURRENT_BRANCH_HIGHLIGHT, fg=self.sm.COLOR_BG_DARK, font=(self.sm.FONT_UI[0], 8, 'bold'))
                    else:
                        color = self.sm.COLOR_ACCENT if is_head else self.sm.COLOR_GREEN if is_remote else self.sm.COLOR_ORANGE
                        ref_label = tk.Label(self.commit_text, text=f" {ref_text} ", bg=color, fg="white", font=(self.sm.FONT_UI[0], 8, 'bold'))
                    
                    self.commit_text.window_create(tk.END, window=ref_label, padx=2)
            
            self.commit_text.insert(tk.END, f"\n{commit['author']}  •  {commit['date']}  ", "info")
            self.commit_text.insert(tk.END, f"{commit['hash'][:7]}\n", "hash")
            self.commit_text.tag_add("commit_block", start_index, tk.END)

        self.commit_text.config(state="disabled")

    def _on_canvas_click(self, event):
        """Handles left-click events on the graph canvas."""
        canvas = event.widget
        # Get the canvas coordinates relative to the scrollregion
        canvas_x = canvas.canvasx(event.x)
        canvas_y = canvas.canvasy(event.y)

        # Find the closest item that is a 'commit_dot'
        items = canvas.find_closest(canvas_x, canvas_y)
        clicked_dot_id = None
        for item_id in items:
            if "commit_dot_" in canvas.gettags(item_id)[0]:
                clicked_dot_id = item_id
                break

        if clicked_dot_id:
            commit_data = self.dot_id_to_commit.get(clicked_dot_id)
            if commit_data:
                self._fetch_and_display_commit_details(commit_data['hash'])
        return "break"

    def _show_commit_context_menu(self, event):
        """Handles right-click events on the commit text area to show a context menu."""
        # Get the line number from the text widget where the right-click occurred
        line_num = int(self.commit_text.index(f"@{event.x},{event.y}").split('.')[0])
        
        # Map the line number back to the commit data
        # We need to find which commit corresponds to this line in the displayed text.
        # This is tricky because of the variable height of commit entries.
        # A more robust solution would involve storing the start/end line for each commit
        # when `display_commits` is called.
        
        # For now, let's try to find the commit based on approximate line number
        # This assumes a direct mapping, which might not be perfect with multi-line messages
        commit_index = -1
        current_line_count = 1
        for i, commit in enumerate(self.commits_data):
            # Estimate lines per commit (message + info line + padding)
            estimated_lines = commit['message'].count('\n') + 2 
            if line_num >= current_line_count and line_num < current_line_count + estimated_lines:
                commit_index = i
                break
            current_line_count += estimated_lines

        if not (0 <= commit_index < len(self.commits_data)): return
        
        commit = self.commits_data[commit_index]
        commit_hash = commit['hash']
        
        menu = tk.Menu(self, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG)
        menu.add_command(label=f"Create branch from '{commit_hash[:7]}'...", command=lambda: self._create_branch_from_commit(commit_hash))
        menu.add_command(label=f"Checkout '{commit_hash[:7]}'", command=lambda: self._checkout_commit(commit_hash))
        menu.add_separator()
        # These actions will be moved to a dedicated "Rewrite History" tab in Phase 3
        # For now, they are commented out/disabled as per the plan's intent.
        # menu.add_command(label=f"Cherry-pick '{commit_hash[:7]}'", command=lambda: self._cherry_pick_commit(commit_hash))
        # menu.add_command(label=f"Revert commit '{commit_hash[:7]}'", command=lambda: self._revert_commit(commit_hash))
        # menu.add_separator()
        # reset_menu = tk.Menu(menu, tearoff=0, bg=self.sm.COLOR_BG_LIGHT, fg=self.sm.COLOR_FG)
        # menu.add_cascade(label=f"Reset current branch to '{commit_hash[:7]}'", menu=reset_menu)
        # reset_menu.add_command(label="Soft - Keep all changes", command=lambda: self._reset_to_commit(commit_hash, "soft"))
        # reset_menu.add_command(label="Mixed - Keep working dir, unstage changes", command=lambda: self._reset_to_commit(commit_hash, "mixed"))
        # reset_menu.add_command(label="Hard - Discard all changes (DANGEROUS)", command=lambda: self._reset_to_commit(commit_hash, "hard"))
        # menu.add_separator()
        menu.add_command(label="Copy full commit hash", command=lambda: self._copy_to_clipboard(commit_hash))
        menu.tk_popup(event.x_root, event.y_root)


    def _fetch_and_display_commit_details(self, commit_hash: str):
        self.commit_detail_viewer.config(state="normal")
        self.commit_detail_viewer.delete("1.0", tk.END)
        self.commit_detail_viewer.insert("1.0", f"Loading details for {commit_hash[:7]}...")
        self.commit_detail_viewer.config(state="disabled")

        def worker():
            success, details = self.git_logic.get_commit_details(commit_hash)
            self.after(0, self.parent_ui._display_colored_diff, details, self.commit_detail_viewer)
        threading.Thread(target=worker, daemon=True).start()

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
        # Get the canvas coordinates relative to the scrollregion
        canvas_x = canvas.canvasx(event.x)
        canvas_y = canvas.canvasy(event.y)

        # Find the closest item that is a 'commit_dot'
        items = canvas.find_closest(canvas_x, canvas_y)
        current_hovered_dot_id = None
        for item_id in items:
            if "commit_dot_" in canvas.gettags(item_id)[0]:
                current_hovered_dot_id = item_id
                break

        if current_hovered_dot_id and current_hovered_dot_id != self.hovered_dot_id:
            self._unhighlight_previous_dot() # Unhighlight previous if different dot is hovered
            self._unhighlight_lane(self.hovered_lane_index) # Unhighlight previous lane
            self.hovered_dot_id = current_hovered_dot_id
            commit_data = self.dot_id_to_commit.get(self.hovered_dot_id)
            if commit_data:
                lane_index = self.commit_lane_map.get(commit_data['hash'], -1)
                self.hovered_lane_index = lane_index
                self._highlight_lane(lane_index)
                self._show_tooltip(event, commit_data)
        elif not current_hovered_dot_id and self.hovered_dot_id:
            self._hide_tooltip()
            self._unhighlight_previous_dot()
            self._unhighlight_lane(self.hovered_lane_index)
            self.hovered_lane_index = -1

    def _highlight_lane(self, lane_index):
        if lane_index == -1: return
        # Highlight lines in the lane
        for line_id in self.lane_lines.get(lane_index, []):
            self.graph_canvas.itemconfig(line_id, width=4) # Thicker line
        
        # Highlight dots in the lane
        for commit_hash, dot_id in self.dot_objects.items():
            if self.commit_lane_map.get(commit_hash) == lane_index:
                self.graph_canvas.itemconfig(dot_id, width=2, outline=self.sm.COLOR_YELLOW) # Thicker outline for dots

    def _unhighlight_lane(self, lane_index):
        if lane_index == -1: return
        # Unhighlight lines in the lane
        for line_id in self.lane_lines.get(lane_index, []):
            self.graph_canvas.itemconfig(line_id, width=2) # Original thickness
        
        # Unhighlight dots in the lane
        for commit_hash, dot_id in self.dot_objects.items():
            if self.commit_lane_map.get(commit_hash) == lane_index:
                self.graph_canvas.itemconfig(dot_id, width=1, outline=self.sm.COLOR_BORDER) # Original thickness and color

    def _unhighlight_previous_dot(self):
        if self.hovered_dot_id and self.graph_canvas.find_withtag(self.hovered_dot_id):
            self.graph_canvas.itemconfig(self.hovered_dot_id, outline=self.sm.COLOR_BORDER, width=1)
        self.hovered_dot_id = None

    def _show_tooltip(self, event, commit_data):
        if self.tooltip_window:
            self._hide_tooltip()
        
        x, y = event.x_root + 15, event.y_root - 10
        
        self.tooltip_window = tk.Toplevel(self.graph_canvas)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        tooltip_text = f"{commit_data['message']}\n\n" \
                       f"Author: {commit_data['author']}\n" \
                       f"Date: {commit_data['date']}\n" \
                       f"Hash: {commit_data['hash'][:12]}"
        if commit_data['refs']: tooltip_text += f"\nRefs: {commit_data['refs']}"

        label = tk.Label(self.tooltip_window, text=tooltip_text, justify='left', bg="#252526", relief='solid', borderwidth=1, font=("Segoe UI", 9), foreground="#D4D4D4", wraplength=400, anchor='w', padx=5, pady=5)
        label.pack(ipadx=1)
        
        self.tooltip_window.update_idletasks()
        self.tooltip_window.wm_geometry(f"+{x}+{event.y_root - self.tooltip_window.winfo_height() - 5}")

    def _hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None
        self._unhighlight_previous_dot() # Ensure dot is unhighlighted when tooltip hides
        self._unhighlight_lane(self.hovered_lane_index)
        self.hovered_lane_index = -1

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
    
    def create_branch(self, new_branch_name=None):
        if new_branch_name is None:
            new_branch_name = self.new_branch_entry.get().strip()
        if not new_branch_name:
            messagebox.showwarning("Input Error", "Please enter a name for the new branch.", parent=self)
            return
        success, output = self.git_logic.create_branch(new_branch_name)
        if success:
            messagebox.showinfo("Success", f"Created and switched to new branch '{new_branch_name}'.", parent=self)
            self.parent_ui.refresh(); self.populate_branches()
            if self.parent_ui.history_view:
                self.parent_ui.history_view.populate_log()
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
