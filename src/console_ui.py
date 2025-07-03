import tkinter as tk
from tkinter import scrolledtext

class ConsoleUi(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.output_console = scrolledtext.ScrolledText(self, wrap="word",
                                                        bg="#1E1E1E", fg="#CCCCCC",
                                                        insertbackground="white",
                                                        selectbackground="#4E4E4E",
                                                        font=("Consolas", 10),
                                                        state="disabled")
        self.output_console.pack(fill="both", expand=True)
        self._configure_console_tags()

        self.tooltip_text = tk.StringVar()
        self.tooltip = tk.Label(self.output_console, textvariable=self.tooltip_text, background="#3C3C3C", foreground="white", relief="solid", borderwidth=1, font=("Consolas", 9), wraplength=400)
        self.tooltip.place_forget() # Hide initially

    def _configure_console_tags(self):
        """Configures tags for different output types in the console."""
        self.output_console.tag_config("info_tag", foreground="#88CCEE")
        self.output_console.tag_config("stdout_tag", foreground="#E0E0E0")
        self.output_console.tag_config("stderr_tag", foreground="#FF6666")
        self.output_console.tag_config("error_tag", foreground="#FF3333", font=("Consolas", 10, "bold"))
        self.output_console.tag_config("warning_tag", foreground="#FFD700")
        self.output_console.tag_config("success_tag", foreground="#66FF66")
        self.output_console.tag_config("timestamp_tag", foreground="#888888", font=("Consolas", 9, "italic"))

    def insert_text(self, text, tags=None):
        if tags is None:
            tags = ()
        self.output_console.config(state="normal")
        self.output_console.insert(tk.END, text, tags)
        self.output_console.config(state="disabled")
        self.output_console.see(tk.END)

    def format_error_output(self, concise_error_text, full_error_text):
        self.output_console.config(state="normal")
        self.output_console.delete(1.0, tk.END) # Clear previous errors
        self.output_console.insert(tk.END, concise_error_text, "error_tag")
        self.output_console.config(state="disabled")
        self.output_console.see(tk.END)

        # Set up hover for the entire error output
        self.output_console.bind("<Enter>", lambda e: self._show_tooltip(full_error_text, e))
        self.output_console.bind("<Leave>", lambda e: self._hide_tooltip())

    def _show_tooltip(self, text, event):
        self.tooltip_text.set(text)
        x = event.x_root + 10 # Offset from mouse cursor
        y = event.y_root + 10
        self.tooltip.place(x=x, y=y)
        self.tooltip.lift()

    def _hide_tooltip(self):
        self.tooltip.place_forget()

    def clear(self):
        self.output_console.config(state="normal")
        self.output_console.delete(1.0, tk.END)
        self.output_console.config(state="disabled")
        self.insert_text("No errors to display.\n", "info_tag")
