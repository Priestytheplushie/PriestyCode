import tkinter as tk
from tkinter import ttk, messagebox
import os
import difflib
import platform
import re
from typing import TYPE_CHECKING, Optional, Tuple, List

from source_control_ui import StyleManager

if TYPE_CHECKING:
    from source_control_ui import GitLogic, SourceControlUI

def sanitize_content(content_bytes: bytes) -> str:
    if content_bytes.startswith(b'\xff\xfe') or content_bytes.startswith(b'\xfe\xff'):
        return content_bytes.decode('utf-16', errors='replace')
    else:
        return content_bytes.decode('utf-8-sig', errors='replace')

class MergeEditor(tk.Toplevel):
    """
    A three-way merge editor with professional-grade UI/UX features like
    inline actions and conflict navigation.
    """
    def __init__(self, parent: "SourceControlUI", git_logic: "GitLogic", filepath: str, workspace_root: str):
        super().__init__(parent)
        self.parent_ui = parent
        self.git_logic = git_logic
        self.filepath = filepath
        self.full_filepath = os.path.join(workspace_root, filepath)
        self.sm = StyleManager()
        self.is_shutting_down = False
        self.tooltip_window: Optional[tk.Toplevel] = None
        self.conflict_locations: List[str] = []
        self.current_conflict_index = -1

        self.monospace_font = ("Consolas", 10)
        if platform.system() == "Darwin": self.monospace_font = ("Menlo", 11)
        elif platform.system() == "Linux": self.monospace_font = ("DejaVu Sans Mono", 10)

        self.title(f"Merge Conflict: {os.path.basename(filepath)}")
        self.geometry("1400x800")
        self.configure(bg=self.sm.COLOR_BG)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._create_widgets()
        self.after(50, self._load_and_style_views)
        self._setup_sync_scrolling()

    def on_close(self):
        self.is_shutting_down = True
        self._hide_tooltip()
        self.destroy()

    def _create_text_widget(self, parent) -> tk.Text:
        text_widget = tk.Text(
            parent,
            wrap="none", bg="#2B2B2B", fg="#D4D4D4",
            insertbackground="white", selectbackground="#4E4E4E",
            font=self.monospace_font, undo=True, borderwidth=0,
            highlightthickness=0, padx=5, pady=5
        )
        text_widget.tag_configure("diff_bg", background="#3e4451")
        text_widget.tag_configure("ours_bg", background="#294429")
        text_widget.tag_configure("theirs_bg", background="#223b54")
        text_widget.tag_configure("marker_ours", foreground="#c678dd")
        text_widget.tag_configure("marker_theirs", foreground="#c678dd")
        text_widget.tag_configure("marker_sep", foreground="#c678dd")
        return text_widget
        
    def _create_info_bar(self):
        info_frame = ttk.Frame(self, style="Header.TFrame", padding=(10, 5))
        info_frame.pack(side="top", fill="x")
        self.conflict_info_label = ttk.Label(info_frame, text=f"File: {self.filepath}", style="Header.TLabel", font=(self.sm.FONT_UI[0], 9))
        self.conflict_info_label.pack(side="left")
        self.conflict_type_label = ttk.Label(info_frame, text="Conflict: ...", style="Header.TLabel", font=(self.sm.FONT_UI[0], 9))
        self.conflict_type_label.pack(side="right")

    def _create_widgets(self):
        toolbar = ttk.Frame(self, style="Header.TFrame", padding=5)
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="↑ Prev", command=self.navigate_to_previous_conflict).pack(side="left", padx=(0, 2))
        ttk.Button(toolbar, text="↓ Next", command=self.navigate_to_next_conflict).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=10, fill="y")
        ttk.Button(toolbar, text="Accept All Current", command=self._accept_current).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Accept All Incoming", command=self._accept_incoming).pack(side="left", padx=5)
        button_frame_right = ttk.Frame(toolbar, style="Header.TFrame"); button_frame_right.pack(side="right")
        ttk.Button(button_frame_right, text="Save & Mark Resolved", style="Accent.TButton", command=self._save_and_resolve).pack(side="left", padx=5)
        ttk.Button(button_frame_right, text="Close", command=self.on_close).pack(side="left", padx=5)

        self._create_info_bar()
        main_pane = ttk.Frame(self, padding=(10, 5, 10, 10)); main_pane.pack(side="top", fill="both", expand=True)
        main_pane.grid_columnconfigure(0, weight=1); main_pane.grid_columnconfigure(2, weight=1); main_pane.grid_columnconfigure(4, weight=1)
        main_pane.grid_rowconfigure(1, weight=1)
        ttk.Label(main_pane, text="Current Changes (Ours)", anchor="center").grid(row=0, column=0, pady=(0, 5))
        ttk.Label(main_pane, text="Result (Editable)", anchor="center", font=(self.sm.FONT_UI[0], 10, 'bold')).grid(row=0, column=2, pady=(0, 5))
        ttk.Label(main_pane, text="Incoming Changes (Theirs)", anchor="center").grid(row=0, column=4, pady=(0, 5))
        self.ours_editor = self._create_text_widget(main_pane); self.ours_editor.grid(row=1, column=0, sticky="nsew"); self.ours_editor.config(state="disabled")
        ttk.Separator(main_pane, orient="vertical").grid(row=1, column=1, sticky="ns", padx=5)
        self.result_editor = self._create_text_widget(main_pane); self.result_editor.grid(row=1, column=2, sticky="nsew")
        ttk.Separator(main_pane, orient="vertical").grid(row=1, column=3, sticky="ns", padx=5)
        self.theirs_editor = self._create_text_widget(main_pane); self.theirs_editor.grid(row=1, column=4, sticky="nsew"); self.theirs_editor.config(state="disabled")
        self.result_editor.bind("<<Modified>>", self._on_result_modified, add="+")
        self.scrollbar = ttk.Scrollbar(main_pane, orient="vertical"); self.scrollbar.grid(row=1, column=5, sticky="ns")

    def _get_conflict_headers_from_disk(self) -> Tuple[str, str]:
        try:
            with open(self.full_filepath, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
            ours_match = re.search(r"^(<<<<<<< .*)$", content, re.MULTILINE)
            theirs_match = re.search(r"^(>>>>>>> .*)$", content, re.MULTILINE)
            if ours_match and theirs_match: return (ours_match.group(1), theirs_match.group(1))
        except Exception: pass
        current_branch = self.git_logic.get_current_branch()
        upstream_info = self.git_logic.get_upstream_branch()
        theirs_name = upstream_info.split('/')[1] if upstream_info else "INCOMING"
        return (f"<<<<<<< {current_branch}", f">>>>>>> {theirs_name}")

    def _load_and_style_views(self):
        # Load 'ours' (stage 2) and 'theirs' (stage 3) for the read-only side panes
        ok_ours, bytes_ours = self.git_logic.get_file_bytes_for_stage(self.filepath, 2)
        ok_theirs, bytes_theirs = self.git_logic.get_file_bytes_for_stage(self.filepath, 3)
        if not (ok_ours and ok_theirs):
            messagebox.showerror("Load Error", "Could not load conflict versions from Git index.", parent=self)
            self.on_close()
            return

        content_ours = sanitize_content(bytes_ours)
        content_theirs = sanitize_content(bytes_theirs)

        # For the editable "Result" pane, load the actual file from the working directory.
        # This file contains the conflict markers with the correct branch names.
        result_content = ""
        try:
            with open(self.full_filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
                result_content = f.read()
        except Exception as e:
            messagebox.showerror("File Read Error", f"Could not read the conflicted file from disk:\n{e}", parent=self)
            # Fallback to reconstructing the conflict if reading from disk fails
            ours_header, theirs_header = self._get_conflict_headers_from_disk()
            result_content = f"{ours_header}\n{content_ours}\n=======\n{content_theirs}\n{theirs_header}\n"

        # Populate reference panes
        for editor, content in [(self.ours_editor, content_ours), (self.theirs_editor, content_theirs)]:
            editor.config(state="normal")
            editor.delete("1.0", "end")
            editor.insert("1.0", content)
            editor.config(state="disabled")

        # Populate the result editor
        self.result_editor.delete("1.0", "end")
        self.result_editor.insert("1.0", result_content)
        
        self._highlight_all_things()
        self.result_editor.edit_modified(False)

    def _on_result_modified(self, event=None):
        if self.result_editor.edit_modified() and not self.is_shutting_down:
            self.after_idle(self._highlight_all_things)
            self.result_editor.edit_modified(False)

    def _create_inline_action(self, parent, text, fg_color, command):
        action_label = tk.Label(parent, text=text, fg=fg_color, bg=self.sm.COLOR_BG_DARK, cursor="hand2", font=(self.sm.FONT_UI[0], 9))
        action_label.bind("<Button-1>", lambda e: command()); action_label.bind("<Enter>", lambda e: e.widget.config(bg=self.sm.COLOR_ACCENT_LIGHT))
        action_label.bind("<Leave>", lambda e: e.widget.config(bg=self.sm.COLOR_BG_DARK)); return action_label

    def _process_and_highlight_conflicts(self):
        for window in self.result_editor.window_names(): self.result_editor.delete(window)
        self.conflict_locations.clear()
        content = self.result_editor.get("1.0", "end-1c")
        conflict_regex = re.compile(r"(^(<<<<<<< .*?)\n(.*?)^(=======)\n(.*?)^(>>>>>>> .*?)$)", re.DOTALL | re.MULTILINE)
        
        ours_marker_text, theirs_marker_text = "HEAD", "INCOMING"
        match_found = False
        
        for match in conflict_regex.finditer(content):
            match_found = True
            full_match, ours_header, ours_content, _, theirs_content, theirs_header = match.groups()
            
            if not self.conflict_locations:
                ours_marker_text = ours_header.split(maxsplit=1)[-1].strip()
                theirs_marker_text = theirs_header.split(maxsplit=1)[-1].strip()

            start_index = self.result_editor.search(full_match, "1.0", "end")
            if not start_index: continue
            self.conflict_locations.append(start_index)

            action_bar = tk.Frame(self.result_editor, bg=self.sm.COLOR_BG_DARK)
            resolve_func = lambda content: (lambda: self.resolve_conflict(start_index, content))
            self._create_inline_action(action_bar, "Accept Current", self.sm.COLOR_GREEN, resolve_func(ours_content)).pack(side="left", padx=4)
            self._create_inline_action(action_bar, "Accept Incoming", self.sm.COLOR_BLUE, resolve_func(theirs_content)).pack(side="left", padx=4)
            self._create_inline_action(action_bar, "Accept Both", self.sm.COLOR_ORANGE, resolve_func(ours_content + "\n" + theirs_content)).pack(side="left", padx=4)
            
            self.result_editor.insert(start_index, '\n')
            self.result_editor.window_create(start_index, window=action_bar)
            
            ours_header_start = self.result_editor.search(ours_header, start_index, "end")
            ours_content_start = f"{ours_header_start} lineend+1c"
            sep_start = self.result_editor.search("=======", ours_content_start, "end")
            theirs_content_start = f"{sep_start} lineend+1c"
            theirs_header_start = self.result_editor.search(theirs_header, theirs_content_start, "end")
            
            self.result_editor.tag_add("ours_bg", ours_content_start, sep_start)
            self.result_editor.tag_add("theirs_bg", theirs_content_start, theirs_header_start)
            self.result_editor.tag_add("marker_ours", ours_header_start, f"{ours_header_start} lineend")
            self.result_editor.tag_add("marker_sep", sep_start, f"{sep_start} lineend")
            self.result_editor.tag_add("marker_theirs", theirs_header_start, f"{theirs_header_start} lineend")

        if match_found:
            conflict_type = "modify/modify" if self.ours_editor.get("1.0", "end-1c") and self.theirs_editor.get("1.0", "end-1c") else "add/add or delete/delete"
            self.conflict_type_label.config(text=f"Conflicts ({len(self.conflict_locations)}): {conflict_type} between '{ours_marker_text}' and '{theirs_marker_text}'")
            self.result_editor.tag_bind("marker_ours", "<Enter>", lambda e, b=ours_marker_text: self._show_marker_tooltip(e, "Start of changes from Current", b))
            self.result_editor.tag_bind("marker_theirs", "<Enter>", lambda e, b=theirs_marker_text: self._show_marker_tooltip(e, "End of changes from Incoming", b))
        else: self.conflict_type_label.config(text="No conflicts detected in result.")
        
        self.result_editor.tag_bind("marker_ours", "<Leave>", self._hide_tooltip)
        self.result_editor.tag_bind("marker_sep", "<Enter>", lambda e: self._show_marker_tooltip(e, "Separator"))
        self.result_editor.tag_bind("marker_sep", "<Leave>", self._hide_tooltip)
        self.result_editor.tag_bind("marker_theirs", "<Leave>", self._hide_tooltip)
    
    def resolve_conflict(self, block_start_index, replacement_text):
        """Replaces a complete conflict block, including its action bar, with the chosen text."""
        # The block to delete starts at the action bar line
        # and ends at the end of the >>>>>>> line.
        start_del = block_start_index
        end_del = self.result_editor.search(">>>>>>>", start_del, "end")
        if not end_del: return # Safety
        
        # Delete the entire block, from the action bar to the end of the conflict
        self.result_editor.delete(start_del, f"{end_del} lineend+1c")
        
        # Insert the chosen, clean text
        self.result_editor.insert(start_del, replacement_text)
        
        # Manually trigger a refresh of the highlights
        self.result_editor.edit_modified()

    def navigate_to_next_conflict(self):
        if not self.conflict_locations: return
        self.current_conflict_index = (self.current_conflict_index + 1) % len(self.conflict_locations)
        self.result_editor.see(self.conflict_locations[self.current_conflict_index])

    def navigate_to_previous_conflict(self):
        if not self.conflict_locations: return
        self.current_conflict_index = (self.current_conflict_index - 1 + len(self.conflict_locations)) % len(self.conflict_locations)
        self.result_editor.see(self.conflict_locations[self.current_conflict_index])

    def _show_marker_tooltip(self, event, text, branch_name=""):
        self._hide_tooltip()
        x, y = event.x_root + 15, event.y_root + 10
        self.tooltip_window = tk.Toplevel(self.result_editor); self.tooltip_window.wm_overrideredirect(True); self.tooltip_window.wm_geometry(f"+{x}+{y}")
        full_text = f"{text}\nSource: {branch_name}" if branch_name else text
        label = tk.Label(self.tooltip_window, text=full_text, justify='left', bg="#252526", relief='solid', borderwidth=1, font=("Segoe UI", 9), fg="#D4D4D4", padx=5, pady=5)
        label.pack()

    def _hide_tooltip(self, event=None):
        if self.tooltip_window: self.tooltip_window.destroy(); self.tooltip_window = None

    def _highlight_all_things(self):
        self._process_and_highlight_conflicts()
        content_ours = self.ours_editor.get("1.0", "end-1c").splitlines()
        content_theirs = self.theirs_editor.get("1.0", "end-1c").splitlines()
        content_result = self.result_editor.get("1.0", "end-1c").splitlines()
        self._apply_diff_highlight(content_result, content_ours, self.ours_editor)
        self._apply_diff_highlight(content_result, content_theirs, self.theirs_editor)

    def _apply_diff_highlight(self, text1_lines, text2_lines, text_widget: tk.Text):
        text_widget.config(state="normal"); text_widget.tag_remove("diff_bg", "1.0", "end")
        matcher = difflib.SequenceMatcher(None, text1_lines, text2_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal': text_widget.tag_add("diff_bg", f"{j1 + 1}.0", f"{j2}.end+1c")
        text_widget.config(state="disabled")
    
    def _setup_sync_scrolling(self):
        editors = [self.ours_editor, self.result_editor, self.theirs_editor]
        def _on_scroll(*args):
            if self.is_shutting_down: return
            for editor in editors: editor.yview_moveto(args[0])
        def _on_mousewheel(event):
            if self.is_shutting_down: return
            for editor in editors: editor.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        self.scrollbar.config(command=_on_scroll)
        for editor in editors:
            editor.config(yscrollcommand=self.scrollbar.set); editor.bind("<MouseWheel>", _on_mousewheel, add="+")

    def _accept_current(self):
        self.ours_editor.config(state="normal"); content = self.ours_editor.get("1.0", "end-1c"); self.ours_editor.config(state="disabled")
        self.result_editor.delete("1.0", "end"); self.result_editor.insert("1.0", content)

    def _accept_incoming(self):
        self.theirs_editor.config(state="normal"); content = self.theirs_editor.get("1.0", "end-1c"); self.theirs_editor.config(state="disabled")
        self.result_editor.delete("1.0", "end"); self.result_editor.insert("1.0", content)

    def _save_and_resolve(self):
        result_content = self.result_editor.get("1.0", "end-1c")
        if "<<<<<<<" in result_content or "=======" in result_content or ">>>>>>>" in result_content:
            if not messagebox.askyesno("Unresolved Conflicts", "There may still be unresolved conflicts.\nAre you sure you want to resolve?", icon='warning', parent=self): return
        try:
            with open(self.full_filepath, 'w', encoding='utf-8') as f: f.write(result_content)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save the resolved file:\n{e}", parent=self); return
        rc, _, stderr = self.git_logic.stage_files([self.filepath])
        if rc != 0:
            messagebox.showerror("Git Error", f"Failed to stage the resolved file:\n{stderr}", parent=self); return
        messagebox.showinfo("Success", f"'{os.path.basename(self.filepath)}' has been marked as resolved.", parent=self)
        self.parent_ui.refresh(); self.on_close()