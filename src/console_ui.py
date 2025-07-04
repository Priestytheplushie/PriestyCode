import tkinter as tk
from tkinter import scrolledtext
import re

class ConsoleUi(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.output_console = scrolledtext.ScrolledText(self, wrap="word",
                                                        bg="#1E1E1E", fg="#CCCCCC",
                                                        insertbackground="white",
                                                        selectbackground="#4E4E4E",
                                                        font=("Consolas", 10),
                                                        state="disabled",
                                                        borderwidth=0, highlightthickness=0)
        self.output_console.pack(fill="both", expand=True)
        self._configure_console_tags()

    def _configure_console_tags(self):
        """Configures tags for different output types in the console."""
        self.output_console.tag_config("info_tag", foreground="#88CCEE")
        self.output_console.tag_config("stdout_tag", foreground="#E0E0E0")
        self.output_console.tag_config("stderr_tag", foreground="#FFB8B8")
        self.output_console.tag_config("error_title_tag", foreground="#FF6666", font=("Consolas", 10, "bold"))
        self.output_console.tag_config("warning_tag", foreground="#FFD700")
        self.output_console.tag_config("success_tag", foreground="#66FF66")

    def insert_text(self, text, tags=None):
        if tags is None:
            tags = ()
        self.output_console.config(state="normal")
        self.output_console.insert(tk.END, text, tags)
        self.output_console.config(state="disabled")
        self.output_console.see(tk.END)

    def display_error(self, title, details):
        """Clears the console and displays a formatted error message."""
        self.clear()
        self.output_console.config(state="normal")
        self.output_console.insert(tk.END, f"{title}\n", ("error_title_tag",))
        self.output_console.insert(tk.END, "-" * (len(title) + 5) + "\n\n")
        self.output_console.insert(tk.END, details, ("stderr_tag",))
        self.output_console.config(state="disabled")
        self.output_console.see(tk.END)

    def clear(self):
        self.output_console.config(state="normal")
        self.output_console.delete(1.0, tk.END)
        self.output_console.config(state="disabled")