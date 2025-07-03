import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import subprocess
import sys
import tempfile
from PIL import Image, ImageTk
import datetime
import threading
import queue
import re

from code_editor import CodeEditor
from console_ui import ConsoleUi
from terminal import Terminal
from file_explorer import FileExplorer

current_dir = os.path.dirname(__file__)
project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))
ICON_PATH = os.path.join(project_root_dir, 'assets', 'icons')

class PriestyCode(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("PriestyCode v0.1.0")
        self.geometry("1200x800")
        self.config(bg="#2B2B2B")

        self.icon_size = 24
        self.process = None
        self.output_queue = queue.Queue()
        self.open_files = []

        try:
            pil_image = Image.open(os.path.join(ICON_PATH, 'priesty.png'))
            self.window_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'priesty.png'))
            self.iconphoto(True, self.window_icon)

            width, height = pil_image.size
            new_width = int(width * (self.icon_size / height))
            resized_image = pil_image.resize((new_width, self.icon_size), Image.Resampling.LANCZOS)
            self.priesty_icon = ImageTk.PhotoImage(resized_image)

            self.folder_icon = self._load_and_resize_icon('folder_icon.png')
            self.git_icon = self._load_and_resize_icon('git_icon.png')
            self.run_icon = self._load_and_resize_icon('run.png')
            self.unknown_file_icon = self._load_and_resize_icon('unknwon.png')
            self.clear_icon = self._load_and_resize_icon('clear_icon.png')
            self.python_logo_icon = self._load_and_resize_icon('python_logo.png', size=16)

        except FileNotFoundError as e:
            print(f"Error: One or more icon files not found. {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
            self.clear_icon = None
            self.python_logo_icon = None
        except Exception as e:
            print(f"Unexpected error loading icons: {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
            self.clear_icon = None
            self.python_logo_icon = None

        try:
            self.iconbitmap(os.path.join(ICON_PATH, 'Priesty.ico'))
        except Exception as e:
            print(f"Error setting window icon: {e}")

        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("DarkMenu.TMenu", background="#3C3C3C", foreground="white")
        self.style.map("DarkMenu.TMenu", background=[('active', '#555555')])

        self.style.configure("TPanedwindow", background="#2B2B2B")
        self.style.configure("TScrollbar", gripcount=0,
                             background="#555555", darkcolor="#3C3C3C",
                             lightcolor="#3C3C3C", troughcolor="#2B2B2B",
                             bordercolor="#2B2B2B", arrowcolor="white")
        self.style.map("TScrollbar", background=[('active', '#6A6A6A')])
        self.style.configure("Treeview.Heading", background="#3C3C3C", foreground="white", relief="flat")
        self.style.map("Treeview.Heading", background=[('active', '#555555')])
        self.style.theme_create("modern_notebook", parent="alt", settings={
            "TNotebook": {"configure": {"background": "#2B2B2B", "tabmargins": [2, 5, 2, 0]}},
            "TNotebook.Tab": {
                "configure": {"padding": [10, 5], "background": "#3C3C3C", "foreground": "white", "font": ("Segoe UI", 10, "bold")},
                "map": {"background": [("selected", "#2B2B2B"), ("active", "#555555")],
                        "foreground": [("selected", "white"), ("active", "white")]}
            }
        })
        self.style.theme_use("modern_notebook")

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        
        self._create_top_toolbar()
        self._create_menu_bar()
        self._create_main_content_area()
        self.after(100, self._process_output_queue)

    def _create_top_toolbar(self):
        self.top_toolbar_frame = tk.Frame(self, bg="#3C3C3C", height=30)
        self.top_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.top_toolbar_frame.grid_propagate(False)

        self.top_toolbar_frame.grid_columnconfigure(0, weight=0)
        self.top_toolbar_frame.grid_columnconfigure(1, weight=1)
        self.top_toolbar_frame.grid_columnconfigure(2, weight=0)
        self.top_toolbar_frame.grid_columnconfigure(3, weight=0)
        self.top_toolbar_frame.grid_columnconfigure(4, weight=0)

        if self.priesty_icon:
            self.priesty_icon_label = tk.Label(self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C")
            self.priesty_icon_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        if self.run_icon:
            self.run_button = tk.Button(self.top_toolbar_frame, image=self.run_icon, bg="#3C3C3C",
                                         bd=0, highlightthickness=0, command=self._run_code)
            self.run_button.grid(row=0, column=2, padx=5, pady=2, sticky="e")
            self.run_button.bind("<Enter>", lambda e: self.run_button.config(bg="#555555"))
            self.run_button.bind("<Leave>", lambda e: self.run_button.config(bg="#3C3C3C"))

        if self.clear_icon:
            self.clear_button = tk.Button(self.top_toolbar_frame, image=self.clear_icon, bg="#3C3C3C",
                                            bd=0, highlightthickness=0, command=self._clear_console)
            self.clear_button.grid(row=0, column=3, padx=5, pady=2, sticky="e")
            self.clear_button.bind("<Enter>", lambda e: self.clear_button.config(bg="#555555"))
            self.clear_button.bind("<Leave>", lambda e: self.clear_button.config(bg="#3C3C3C"))

        self.working_dir_path = os.path.abspath(project_root_dir)
        self.path_label = tk.Label(self.top_toolbar_frame, text=self.working_dir_path, bg="#3C3C3C", fg="#A0A0A0", font=("Segoe UI", 9))
        self.path_label.grid(row=0, column=4, padx=10, pady=2, sticky="e")

    def _load_and_resize_icon(self, icon_filename, size=None):
        try:
            pil_image = Image.open(os.path.join(ICON_PATH, icon_filename))
            if size:
                new_width = int(pil_image.width * (size / pil_image.height))
                resized_image = pil_image.resize((new_width, size), Image.Resampling.LANCZOS)
            else:
                width, height = pil_image.size
                new_width = int(width * (self.icon_size / height))
                resized_image = pil_image.resize((new_width, self.icon_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized_image)
        except Exception as e:
            print(f"Error loading and resizing icon {icon_filename}: {e}")
            return None
    
    def _create_main_content_area(self):
        self.main_content_frame = tk.Frame(self, bg="#2B2B2B")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew")
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        self.main_content_frame.grid_columnconfigure(1, weight=1)

        self.left_pane = tk.Frame(self.main_content_frame, bg="#2B2B2B", width=250)
        self.left_pane.grid(row=0, column=0, sticky="nsw")
        self.left_pane.grid_propagate(False)

        self.file_manager_label = tk.Label(self.left_pane, text="File Manager", bg="#3C3C3C", fg="white", font=("Segoe UI", 10, "bold"))
        self.file_manager_label.pack(fill="x", pady=5)

        self.file_explorer = FileExplorer(self.left_pane, project_root_dir, self.open_file) # Pass open_file to file explorer
        self.file_explorer.pack(fill="both", expand=True)
        self.file_explorer.populate_tree() # Populate tree on startup

        self.tabs_label = tk.Label(self.left_pane, text="Tabs", bg="#3C3C3C", fg="white", font=("Segoe UI", 10, "bold"))
        self.tabs_label.pack(fill="x", pady=5)

        self.tabs_frame = tk.Frame(self.left_pane, bg="#2B2B2B")
        self.tabs_frame.pack(fill="both", expand=True)

        self.right_pane = ttk.PanedWindow(self.main_content_frame, orient=tk.VERTICAL)
        self.right_pane.grid(row=0, column=1, sticky="nsew")

        self.file_header_frame = tk.Frame(self.right_pane, bg="#3C3C3C", height=25)
        self.file_header_frame.pack_propagate(False)
        
        if self.python_logo_icon:
            self.python_logo_label = tk.Label(self.file_header_frame, image=self.python_logo_icon, bg="#3C3C3C")
            self.python_logo_label.pack(side="left", padx=5, pady=0)
        
        self.current_filename_label = tk.Label(self.file_header_frame, text="unknown.py", 
                                                bg="#3C3C3C", fg="white", font=("Segoe UI", 9))
        self.current_filename_label.pack(side="left", padx=0, pady=0)

        self.right_pane.add(self.file_header_frame, weight=0)

        self.code_editor = CodeEditor(self.right_pane)
        self.right_pane.add(self.code_editor, weight=3)

        self.output_notebook = ttk.Notebook(self.right_pane)
        self.output_console = ConsoleUi(self.output_notebook)
        self.error_console = ConsoleUi(self.output_notebook)
        self.output_notebook.add(self.output_console, text="Output")
        self.output_notebook.add(self.error_console, text="Errors")
        self.right_pane.add(self.output_notebook, weight=1)

        self.error_console.insert_text("No errors to display.\n", "info_tag")

    def _create_menu_bar(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=lambda: messagebox.showinfo("New File", "New File functionality coming soon!"))
        file_menu.add_command(label="Open File...", command=self._open_file_dialog) # Changed to call a new method
        file_menu.add_command(label="Save", command=lambda: messagebox.showinfo("Save File", "Save File functionality coming soon!"))
        file_menu.add_command(label="Save As...", command=lambda: messagebox.showinfo("Save As", "Save As functionality coming soon!"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        edit_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Cut", command=lambda: self.code_editor.text_area.event_generate("<<Cut>>"))
        edit_menu.add_command(label="Copy", command=lambda: self.code_editor.text_area.event_generate("<<Copy>>"))
        edit_menu.add_command(label="Paste", command=lambda: self.code_editor.text_area.event_generate("<<Paste>>"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Undo", command=lambda: self.code_editor.text_area.event_generate("<<Undo>>"))
        edit_menu.add_command(label="Redo", command=lambda: self.code_editor.text_area.event_generate("<<Redo>>"))

        view_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Fullscreen", command=lambda: self.attributes('-fullscreen', not self.attributes('-fullscreen')))
        view_menu.add_command(label="Reset UI Layout", command=self._reset_ui_layout) # New button

        terminal_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Terminal", menu=terminal_menu)
        terminal_menu.add_command(label="New Terminal", command=self._open_new_terminal)

        help_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About PriestyCode", command=lambda: messagebox.showinfo("About", "PriestyCode v0.1.0\nA simple Python IDE built with Tkinter."))

    def _run_code(self):
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Busy", "A process is already running.")
            return

        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        self.output_console.insert_text(f"\n{timestamp} --- Code Execution ---\n", "timestamp_tag")
        self.code_editor.clear_error_highlight()

        code_content = self.code_editor.text_area.get(1.0, tk.END)
        
        threading.Thread(target=self._execute_in_thread, args=(code_content,), daemon=True).start()

    def _execute_in_thread(self, code_content):
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w', encoding='utf-8') as tmp_file:
                temp_file_path = tmp_file.name
                tmp_file.write(code_content)

            python_executable = sys.executable
            
            popen_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True,
                'encoding': 'utf-8',
                'bufsize': 1 
            }
            if sys.platform == "win32":
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen([python_executable, "-u", temp_file_path], **popen_kwargs)

            stdout_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            self.process.wait(timeout=5)
            stdout_thread.join()
            stderr_thread.join()

            if self.process.returncode != 0:
                self.output_queue.put(("PROCESS_ERROR_SIGNAL", None))

        except subprocess.TimeoutExpired:
            if self.process is not None:
                self.process.kill()
            self.output_queue.put(("\n--- Code execution timed out after 5 seconds ---\n", "error_tag"))
        except FileNotFoundError:
            self.output_queue.put((f"\nError: Python executable not found at '{sys.executable}'.\n", "error_tag"))
        except Exception as e:
            self.output_queue.put((f"\nUnexpected Error: {e}\n", "error_tag"))
        finally:
            if temp_file_path:
                try:
                    os.remove(temp_file_path)
                except OSError:
                    pass
            self.process = None

    def _read_stream_to_queue(self, stream, tag):
        for line in iter(stream.readline, ''):
            self.output_queue.put((line, tag))
        stream.close()

    def _process_output_queue(self):
        full_stderr_output = []
        try:
            while True:
                item = self.output_queue.get_nowait()
                line, tag = item

                if tag == "stderr_tag":
                    self.output_console.insert_text(line, tag)
                    full_stderr_output.append(line)
                elif item == ("PROCESS_ERROR_SIGNAL", None):
                    if full_stderr_output:
                        error_message = "".join(full_stderr_output)
                        
                        concise_error = "An error occurred."
                        line_num = None

                        file_line_match = re.search(r'File ".*?", line (\d+)', error_message)
                        
                        if file_line_match:
                            line_num = int(file_line_match.group(1))

                        error_type_message_match = re.search(r'(?:\w+Error|Warning):\s*(.*)', error_message.splitlines()[-1])
                        if error_type_message_match:
                            concise_error = error_type_message_match.group(0).strip()
                        elif len(error_message.splitlines()) > 1:
                            concise_error = error_message.splitlines()[-1].strip()

                        if line_num:
                            concise_error = f"Line {line_num}: {concise_error}"

                        self.error_console.format_error_output(concise_error, error_message)
                        
                        if line_num:
                            self.code_editor.highlight_error_line(line_num)
                    else:
                        self.error_console.clear()
                        self.code_editor.clear_error_highlight()
                    full_stderr_output = []
                else:
                    self.output_console.insert_text(line, tag)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_output_queue)

    def open_file(self, file_path):
        if file_path not in self.open_files:
            self.open_files.append(file_path)
            self.update_tabs()
        
        with open(file_path, "r") as f:
            self.code_editor.text_area.delete(1.0, tk.END)
            self.code_editor.text_area.insert(tk.END, f.read())
        self.current_filename_label.config(text=os.path.basename(file_path))

    def _open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.working_dir_path,
            title="Select a file",
            filetypes=(("Python files", "*.py"), ("All files", "*.*"))
        )
        if file_path:
            self.open_file(file_path)

    def update_tabs(self):
        for child in self.tabs_frame.winfo_children():
            child.destroy()

        for file_path in self.open_files:
            file_name = os.path.basename(file_path)
            tab = tk.Label(self.tabs_frame, text=file_name, bg="#3C3C3C", fg="white", padx=5, pady=2)
            tab.pack(fill="x")

    def _open_new_terminal(self):
        terminal_window = tk.Toplevel(self)
        terminal_window.title("New Terminal")
        terminal_window.geometry("800x400")
        terminal_window.config(bg="#1E1E1E")
        terminal = Terminal(terminal_window)
        terminal.pack(fill="both", expand=True)

    def _clear_console(self):
        self.output_console.clear()

    def _reset_ui_layout(self):
        """Resets the PanedWindow sashes to their initial positions."""
        # Destroy and re-create the main content area to reset layout
        # This is a bit heavy-handed, but ensures all layout managers are reset.
        # A more granular approach would be to manage sash positions directly if available
        # or reset grid/pack configurations.
        self.main_content_frame.destroy()
        self._create_main_content_area()
        messagebox.showinfo("UI Reset", "UI layout has been reset.")


    def run(self):
        self.mainloop()

    def quit(self):
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
        super().quit()