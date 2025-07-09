# console_ui.py

import tkinter as tk
from tkinter import ttk
import os


class ConsoleUi(ttk.Frame):
    def __init__(self, parent, jump_callback):
        super().__init__(parent)
        self.jump_callback = jump_callback
        self.error_map = {}  # Maps treeview item ID to full error details
        self.tooltip_window = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            self, columns=("Description", "File", "Location"), show="headings"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.tree.heading("Description", text="Description")
        self.tree.heading("File", text="File")
        self.tree.heading("Location", text="Location")

        # Allow the description column to expand
        self.tree.column("Description", width=400, anchor="w")
        self.tree.column("File", width=150, anchor="w", stretch=False)
        self.tree.column("Location", width=80, anchor="w", stretch=False)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Motion>", self._on_hover)
        self.tree.bind("<Leave>", self._on_leave)

    def _on_hover(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id and item_id in self.error_map:
            details = self.error_map[item_id].get("details", "No details available.")
            self._show_tooltip(event, details)
        else:
            self._hide_tooltip()

    def _on_leave(self, event):
        self._hide_tooltip()

    def _show_tooltip(self, event, text):
        if self.tooltip_window:
            self.tooltip_window.destroy()

        x = self.winfo_pointerx() + 20
        y = self.winfo_pointery() + 10

        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tooltip_window,
            text=text,
            justify="left",
            background="#3C3C3C",
            foreground="white",
            relief="solid",
            borderwidth=1,
            wraplength=500,
            font=("Consolas", 9),
            padx=4,
            pady=4,
        )
        label.pack(ipadx=1)

    def _hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _on_double_click(self, event):
        item_id = self.tree.focus()
        if item_id and item_id in self.error_map:
            error_details = self.error_map[item_id]
            file_path = error_details.get("file_path")
            line = error_details.get("line")
            if file_path and line:
                self.jump_callback(file_path, line)

    def display_errors(self, errors_list, proactive_only=False, runtime_only=False):
        """Displays a list of structured errors in the treeview."""
        if proactive_only:
            self.clear(proactive_only=True)
        elif runtime_only:
            self.clear(runtime_only=True)

        for error in errors_list:
            file_path = error.get("file_path", "N/A")
            file_name = os.path.basename(file_path) if file_path != "N/A" else "N/A"
            line = error.get("line", 1)
            col = error.get("col", 1)
            location_str = f"{line}:{col}"

            item_id = self.tree.insert(
                "", "end", values=(error["title"], file_name, location_str)
            )

            error_type = "proactive" if proactive_only else "runtime"
            self.error_map[item_id] = {"type": error_type, **error}

    def display_error(self, title, details):
        """Legacy method to display a single, non-structured error."""
        error_item = {
            "title": title,
            "details": details,
            "file_path": "N/A",
            "line": 1,
            "col": 1,
        }
        self.clear()
        self.display_errors([error_item])

    def clear(self, proactive_only=False, runtime_only=False):
        """Clears errors. Can selectively clear proactive or runtime errors."""
        items_to_delete = []
        if proactive_only:
            items_to_delete = [
                item_id
                for item_id, details in self.error_map.items()
                if details.get("type") == "proactive"
            ]
        elif runtime_only:
            items_to_delete = [
                item_id
                for item_id, details in self.error_map.items()
                if details.get("type") == "runtime"
            ]
        else:  # Clear all
            items_to_delete = list(self.error_map.keys())

        for item_id in items_to_delete:
            if self.tree.exists(item_id):
                self.tree.delete(item_id)
            if item_id in self.error_map:
                del self.error_map[item_id]
