# priesty_ide.py
# Imports necessary libraries

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

# Importing custom modules

from code_editor import CodeEditor
from console_ui import ConsoleUi
from terminal import Terminal
from file_explorer import FileExplorer

current_dir = os.path.dirname(__file__)
initial_project_root_dir = os.path.abspath(os.path.join(current_dir, '..'))
ICON_PATH = os.path.join(initial_project_root_dir, 'assets', 'icons')
CODE_PREFIX_LINES = 4 # Number of lines added to the script before execution

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
        self.current_open_file = None # Track the currently active file
        self.is_running = False # Track if a process is currently running
        self.last_output_time = 0.0 # Timestamp of the last output for timeout
        
        self.workspace_root_dir = initial_project_root_dir

        try:
            pil_image = Image.open(os.path.join(ICON_PATH, 'priesty.png'))
            self.window_icon = tk.PhotoImage(file=os.path.join(ICON_PATH, 'priesty.png'))
            self.iconphoto(True, self.window_icon)

            width, height = pil_image.size
            new_width = int(width * (self.icon_size / pil_image.height))
            resized_image = pil_image.resize((new_width, self.icon_size), Image.Resampling.LANCZOS)
            self.priesty_icon = ImageTk.PhotoImage(resized_image)

            self.folder_icon = self._load_and_resize_icon('folder_icon.png')
            self.git_icon = self._load_and_resize_icon('git_icon.png')
            self.run_icon = self._load_and_resize_icon('run.png')
            self.unknown_file_icon = self._load_and_resize_icon('unknwon.png')
            self.clear_icon = self._load_and_resize_icon('clear_icon.png')
            self.python_logo_icon = self._load_and_resize_icon('python_logo.png', size=16)
            self.close_icon = self._load_and_resize_icon('close_icon.png') # New close icon
            self.pause_icon = self._load_and_resize_icon('pause.png')

        except FileNotFoundError as e:
            print(f"Error: One or more icon files not found. {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
            self.clear_icon = None
            self.python_logo_icon = None
            self.close_icon = None
        except Exception as e:
            print(f"Unexpected error loading icons: {e}")
            self.priesty_icon = None
            self.folder_icon = None
            self.git_icon = None
            self.run_icon = None
            self.unknown_file_icon = None
            self.clear_icon = None
            self.python_logo_icon = None
            self.close_icon = None

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

        self.top_toolbar_frame.grid_columnconfigure(0, weight=0) # For Priesty icon
        self.top_toolbar_frame.grid_columnconfigure(1, weight=1) # Filler space
        self.top_toolbar_frame.grid_columnconfigure(2, weight=0) # For run/stop button
        self.top_toolbar_frame.grid_columnconfigure(3, weight=0) # For clear button

        if self.priesty_icon:
            self.priesty_icon_label = tk.Label(self.top_toolbar_frame, image=self.priesty_icon, bg="#3C3C3C")
            self.priesty_icon_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        # Dynamic Run/Stop Button
        if self.run_icon: # Assuming run_icon will be the default
            self.run_stop_button = tk.Button(self.top_toolbar_frame, image=self.run_icon, bg="#3C3C3C",
                                         bd=0, highlightthickness=0, command=self._run_code)
            self.run_stop_button.grid(row=0, column=2, padx=5, pady=2, sticky="e")
            self.run_stop_button.bind("<Enter>", lambda e: self.run_stop_button.config(bg="#555555"))
            self.run_stop_button.bind("<Leave>", lambda e: self.run_stop_button.config(bg="#3C3C3C"))
        else: # Fallback to text if icon not found
            self.run_stop_button = tk.Button(self.top_toolbar_frame, text="Run", bg="#3C3C3C", fg="white",
                                         bd=0, highlightthickness=0, command=self._run_code)
            self.run_stop_button.grid(row=0, column=2, padx=5, pady=2, sticky="e")
            self.run_stop_button.bind("<Enter>", lambda e: self.run_stop_button.config(bg="#555555"))
            self.run_stop_button.bind("<Leave>", lambda e: self.run_stop_button.config(bg="#3C3C3C"))

        if self.clear_icon:
            self.clear_button = tk.Button(self.top_toolbar_frame, image=self.clear_icon, bg="#3C3C3C",
                                            bd=0, highlightthickness=0, command=self._clear_console)
            self.clear_button.grid(row=0, column=3, padx=5, pady=2, sticky="e")
            self.clear_button.bind("<Enter>", lambda e: self.clear_button.config(bg="#555555"))
            self.clear_button.bind("<Leave>", lambda e: self.clear_button.config(bg="#3C3C3C"))

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

        # File Manager Label
        self.file_manager_label = tk.Label(self.left_pane, text="File Manager", bg="#3C3C3C", fg="white", font=("Segoe UI", 10, "bold"))
        self.file_manager_label.pack(fill="x", pady=(0, 0))

        # New frame for Workspace Path and Folder Icon, below "File Manager" text
        self.workspace_path_frame = tk.Frame(self.left_pane, bg="#3C3C3C", height=30)
        self.workspace_path_frame.pack(fill="x", pady=(5, 5), padx=0)
        self.workspace_path_frame.pack_propagate(False)
        
        self.workspace_path_frame.grid_columnconfigure(1, weight=1)

        if self.folder_icon:
            self.change_folder_button = tk.Button(self.workspace_path_frame, image=self.folder_icon, bg="#3C3C3C",
                                                  bd=0, highlightthickness=0, command=self._change_workspace_folder)
            self.change_folder_button.grid(row=0, column=0, padx=(5, 2), pady=2, sticky="w")
            self.change_folder_button.bind("<Enter>", lambda e: self.change_folder_button.config(bg="#555555"))
            self.change_folder_button.bind("<Leave>", lambda e: self.change_folder_button.config(bg="#3C3C3C"))
        
        self.path_label = tk.Label(self.workspace_path_frame, text=self.workspace_root_dir, bg="#3C3C3C", fg="#A0A0A0", font=("Segoe UI", 9))
        self.path_label.grid(row=0, column=1, padx=(2, 5), pady=2, sticky="ew")


        # File Explorer treeview
        self.file_explorer = FileExplorer(self.left_pane, self.workspace_root_dir, self.open_file,
                                         folder_icon=self.folder_icon, python_icon=self.python_logo_icon,
                                         git_icon=self.git_icon, unknown_icon=self.unknown_file_icon)
        self.file_explorer.pack(fill="both", expand=True)
        self.file_explorer.populate_tree()

        self.tabs_label = tk.Label(self.left_pane, text="Tabs", bg="#3C3C3C", fg="white", font=("Segoe UI", 10, "bold"))
        self.tabs_label.pack(fill="x", pady=5)

        # Frame for tabs and scrollbar
        self.tabs_container_frame = tk.Frame(self.left_pane, bg="#2B2B2B")
        self.tabs_container_frame.pack(fill="both", expand=True)

        self.tabs_canvas = tk.Canvas(self.tabs_container_frame, bg="#2B2B2B", highlightthickness=0)
        self.tabs_canvas.pack(side="left", fill="both", expand=True)

        self.tabs_scrollbar = ttk.Scrollbar(self.tabs_container_frame, orient="vertical", command=self.tabs_canvas.yview)
        self.tabs_scrollbar.pack(side="right", fill="y")

        self.tabs_canvas.configure(yscrollcommand=self.tabs_scrollbar.set)
        self.tabs_canvas.bind('<Configure>', lambda e: self.tabs_canvas.configure(scrollregion = self.tabs_canvas.bbox("all")))
        self.tabs_canvas.bind("<MouseWheel>", self._on_mousewheel) # For Windows/Mac scroll

        self.tabs_frame = tk.Frame(self.tabs_canvas, bg="#2B2B2B")
        self.tabs_canvas.create_window((0, 0), window=self.tabs_frame, anchor="nw", width=self.tabs_container_frame.winfo_width())

        self.tabs_frame.bind("<Configure>", lambda e: self.tabs_canvas.configure(scrollregion = self.tabs_canvas.bbox("all")))
        self.tabs_container_frame.bind("<Configure>", lambda e: self.tabs_canvas.itemconfig(self.tabs_canvas.find_all()[-1], width=e.width))


        self.right_pane = ttk.PanedWindow(self.main_content_frame, orient=tk.VERTICAL)
        self.right_pane.grid(row=0, column=1, sticky="nsew")

        self.file_header_frame = tk.Frame(self.right_pane, bg="#3C3C3C", height=25)
        self.file_header_frame.pack_propagate(False)
        
        # Renamed python_logo_label to file_type_icon_label for dynamic icon
        self.file_type_icon_label = tk.Label(self.file_header_frame, bg="#3C3C3C")
        if self.python_logo_icon: # Use python logo as default if no file is open
            self.file_type_icon_label.config(image=self.python_logo_icon)
            self._file_type_icon_ref = self.python_logo_icon # Keep reference
        self.file_type_icon_label.pack(side="left", padx=5, pady=0)
        
        self.current_filename_label = tk.Label(self.file_header_frame, text="unknown.py", 
                                                bg="#3C3C3C", fg="white", font=("Segoe UI", 9))
        self.current_filename_label.pack(side="left", padx=0, pady=0)

        self.right_pane.add(self.file_header_frame, weight=0)

        self.output_notebook = ttk.Notebook(self.right_pane)
        self.output_console = ConsoleUi(self.output_notebook)
        self.error_console = ConsoleUi(self.output_notebook)
        self.terminal_console = Terminal(self.output_notebook) # Initialize Terminal

        # Pass the error_console to the CodeEditor
        self.code_editor = CodeEditor(self.right_pane, error_console=self.error_console)
        self.right_pane.add(self.code_editor, weight=3)
        
        self.output_notebook.add(self.output_console, text="Output")
        self.output_notebook.add(self.error_console, text="Errors")
        self.output_notebook.add(self.terminal_console, text="Terminal") # Add Terminal tab
        
        self.right_pane.add(self.output_notebook, weight=1)

        self.error_console.insert_text("No errors to display.\n", "info_tag")


    def _on_mousewheel(self, event):
        self.tabs_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _create_menu_bar(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=lambda: messagebox.showinfo("New File", "New File functionality coming soon!"))
        file_menu.add_command(label="Open File...", command=self._open_file_dialog)
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
        view_menu.add_command(label="Reset UI Layout", command=self._reset_ui_layout)

        terminal_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Terminal", menu=terminal_menu)
        terminal_menu.add_command(label="New Terminal", command=self._open_new_terminal)

        help_menu = tk.Menu(menubar, tearoff=0, bg="#3C3C3C", fg="white", activebackground="#555555", activeforeground="white")
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About PriestyCode", command=lambda: messagebox.showinfo("About", "PriestyCode v0.1.0\nA simple Python IDE built with Tkinter."))

    def _run_code(self):
        if self.is_running:
            self._stop_code()
            return

        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        self.output_console.insert_text(f"\n{timestamp} --- Code Execution ---\n", "timestamp_tag")
        self.code_editor.clear_error_highlight()

        code_content = self.code_editor.text_area.get(1.0, tk.END)
        
        self.is_running = True
        if self.pause_icon:
            self.run_stop_button.config(image=self.pause_icon, command=self._stop_code) # Change to pause icon
        else:
            self.run_stop_button.config(text="Stop", command=self._stop_code)

        threading.Thread(target=self._execute_in_thread, args=(code_content,), daemon=True).start()

    def _stop_code(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
                self.output_queue.put(("\n--- Process terminated by user ---\n", "error_tag"))
            except Exception as e:
                self.output_queue.put((f"\nError terminating process: {e}\n", "error_tag"))
            finally:
                self.is_running = False
                if self.run_icon:
                    self.run_stop_button.config(image=self.run_icon, command=self._run_code) # Change back to run icon
                else:
                    self.run_stop_button.config(text="Run", command=self._run_code)
        else:
            messagebox.showinfo("No Process", "No active process to stop.")
            self.is_running = False
            if self.run_icon != None:
                self.run_stop_button.config(image=self.run_icon, command=self._run_code)
            else:
                self.run_stop_button.config(text="Run", command=self._run_code)

    def _execute_in_thread(self, code_content):
        temp_file_path = None
        try:
            # Calculate execution_dir before creating modified_code_content
            execution_dir = os.path.dirname(self.current_open_file) if self.current_open_file else self.workspace_root_dir

            # Create a modified code content that adds the project root and execution directory to sys.path
            # at the beginning of the script.
            modified_code_content = (
                f"import sys\n"
                f"import os\n"
                f"sys.path.insert(0, r'{initial_project_root_dir.replace(os.sep, '/')}')\n" # Use raw string and forward slashes for path consistency
                f"sys.path.insert(1, r'{execution_dir.replace(os.sep, '/')}')\n"
                f"{code_content}"
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w', encoding='utf-8') as tmp_file:
                temp_file_path = tmp_file.name
                tmp_file.write(modified_code_content) # Write the modified content

            python_executable = sys.executable
            
            popen_kwargs = {
                'stdout': subprocess.PIPE,
                'stderr': subprocess.PIPE,
                'text': True,
                'encoding': 'utf-8',
                'bufsize': 1,
                'cwd': execution_dir,  # Keep the cwd for relative file operations within the executed script
            }
            if sys.platform == "win32":
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen([python_executable, "-u", temp_file_path], **popen_kwargs)

            stdout_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stdout, "stdout_tag"), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream_to_queue, args=(self.process.stderr, "stderr_tag"), daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            # Wait for the process to complete without a timeout
            self.process.wait()
            stdout_thread.join()
            stderr_thread.join()

            if self.process.returncode != 0:
                self.output_queue.put(("PROCESS_ERROR_SIGNAL", None))

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
            if self.run_icon:
                self.after(0, lambda: self.run_stop_button.config(image=self.run_icon, command=self._run_code)) # type: ignore
            else:
                self.after(0, lambda: self.run_stop_button.config(text="Run", command=self._run_code))
            self.is_running = False

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
                    # Reset button state on process error
                    self.is_running = False
                    if self.run_icon:
                        self.run_stop_button.config(image=self.run_icon, command=self._run_code)
                    else:
                        self.run_stop_button.config(text="Run", command=self._run_code)
                    self.is_running = False

                    if full_stderr_output:
                        error_message = "".join(full_stderr_output)
                        
                        concise_error = "An error occurred."
                        editor_line_num = None

                        # Find the last traceback line to get the most relevant error location
                        matches = list(re.finditer(r'File ".*?", line (\d+)', error_message))
                        if matches:
                            last_match = matches[-1]
                            line_num_from_traceback = int(last_match.group(1))
                            # Adjust for the lines prepended to the script
                            editor_line_num = line_num_from_traceback - CODE_PREFIX_LINES

                        # Get the final error type and message
                        error_type_message_match = re.search(r'(?:\w+Error|Warning):\s*(.*)', error_message.splitlines()[-1])
                        if error_type_message_match:
                            concise_error = error_type_message_match.group(0).strip()
                        elif len(error_message.splitlines()) > 1:
                            concise_error = error_message.splitlines()[-1].strip()

                        # Update error console and highlight the line in the editor
                        if editor_line_num and editor_line_num > 0:
                            concise_error_with_line = f"Line {editor_line_num}: {concise_error}"
                            self.error_console.format_error_output(concise_error_with_line, error_message)
                            # Use the new method to highlight and set tooltip
                            self.code_editor.highlight_runtime_error(editor_line_num, concise_error)
                        else:
                            # If line number couldn't be parsed, just show the error without highlighting
                            self.error_console.format_error_output(concise_error, error_message)
                            self.code_editor.clear_error_highlight()
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
        self.current_open_file = file_path # Set the newly opened file as current
        self.update_tabs()
        
        with open(file_path, "r") as f:
            self.code_editor.text_area.delete(1.0, tk.END)
            self.code_editor.text_area.insert(tk.END, f.read())
        
        self.current_filename_label.config(text=os.path.basename(file_path))
        
        # Update the file type icon based on file extension/name
        file_extension = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path).lower()
        
        selected_icon = self.unknown_file_icon
        if file_extension == '.py':
            selected_icon = self.python_logo_icon
        elif file_name in ['.gitignore', '.gitattributes', '.gitmodules', 'readme.md']:
            selected_icon = self.git_icon
        
        if selected_icon is not None:
            self.file_type_icon_label.config(image=selected_icon)
        else:
            self.file_type_icon_label.config(image="")
        self._file_type_icon_ref = selected_icon # Keep reference
        
        # Apply syntax highlighting and proactive syntax check immediately after opening the file
        self.code_editor.apply_syntax_highlighting()
        self.code_editor._proactive_syntax_check()


    def _close_tab(self, file_path):
        if file_path in self.open_files:
            self.open_files.remove(file_path)
            if self.current_open_file == file_path:
                if self.open_files:
                    # Open the last remaining file
                    self.open_file(self.open_files[-1]) 
                else:
                    # No files open, clear editor and reset labels
                    self.code_editor.text_area.delete(1.0, tk.END)
                    self.current_filename_label.config(text="unknown.py")
                    if self.python_logo_icon:
                        self.file_type_icon_label.config(image=self.python_logo_icon)
                        self._file_type_icon_ref = self.python_logo_icon
                    else:
                        self.file_type_icon_label.config(image="")
                    self.current_open_file = None
                    self.code_editor.clear_error_highlight() # Clear highlights if no file is open
                    self.error_console.clear() # Clear error console if no file is open
            self.update_tabs()


    def _open_file_dialog(self):
        file_path = filedialog.askopenfilename(
            initialdir=self.workspace_root_dir,
            title="Select a file",
            filetypes=(("Python files", "*.py"), ("All files", "*.*"))
        )
        if file_path:
            self.open_file(file_path)

    def _change_workspace_folder(self):
        """Allows the user to select a new folder for the workspace."""
        new_folder_path = filedialog.askdirectory(
            initialdir=self.workspace_root_dir,
            title="Select New Workspace Folder"
        )
        if new_folder_path and new_folder_path != self.workspace_root_dir:
            self.workspace_root_dir = new_folder_path
            self.path_label.config(text=self.workspace_root_dir)
            
            self.file_explorer.project_root = self.workspace_root_dir
            self.file_explorer.populate_tree()
            
            messagebox.showinfo("Workspace Changed", f"Workspace changed to:\n{self.workspace_root_dir}")
            
    def update_tabs(self):
        # Clear existing tabs
        for widget in self.tabs_frame.winfo_children():
            widget.destroy()

        # Clear existing icon references to avoid memory leaks
        if hasattr(self, '_tab_icons_refs'):
            self._tab_icons_refs.clear()
        if hasattr(self, '_close_icons_refs'):
            self._close_icons_refs.clear()

        for file_path in self.open_files:
            file_name = os.path.basename(file_path)
            
            # Determine icon for the file
            file_extension = os.path.splitext(file_path)[1].lower()
            icon_to_use = self.unknown_file_icon
            if file_extension == '.py':
                icon_to_use = self.python_logo_icon
            elif file_name in ['.gitignore', '.gitattributes', '.gitmodules', 'readme.md']:
                icon_to_use = self.git_icon

            # Create a frame for each tab
            tab_frame = tk.Frame(self.tabs_frame, padx=5, pady=2)
            tab_frame.pack(fill="x", pady=1)

            # Set initial background based on whether it's the current active tab
            if file_path == self.current_open_file:
                tab_frame.config(bg="#555555")
            else:
                tab_frame.config(bg="#3C3C3C")

            # File icon
            icon_label = None
            if icon_to_use:
                icon_label = tk.Label(tab_frame, image=icon_to_use, bg=tab_frame.cget("bg"))
                icon_label.pack(side="left", padx=(0, 5))
                # Keep a reference to prevent garbage collection
                if not hasattr(self, '_tab_icons_refs'):
                    self._tab_icons_refs = []
                self._tab_icons_refs.append(icon_to_use)

            # File name label
            tab_label = tk.Label(tab_frame, text=file_name, bg=tab_frame.cget("bg"), fg="white", font=("Segoe UI", 9))
            tab_label.pack(side="left", expand=True, fill="x")

            # Close button
            if self.close_icon:
                close_button = tk.Button(
                    tab_frame, image=self.close_icon, bg=tab_frame.cget("bg"),
                    bd=0, highlightthickness=0, command=lambda fp=file_path: self._close_tab(fp),
                    height=24, width=24  # Explicit size, adjust as needed
                )
                close_button.pack(side="right", padx=(2, 15), pady=(2, 2))  # Add vertical padding
                close_button.bind("<Enter>", lambda e, tf=tab_frame: tf.config(bg="#6A6A6A"))
                close_button.bind("<Leave>", lambda e, tf=tab_frame, fp=file_path: tf.config(bg="#555555" if fp == self.current_open_file else "#3C3C3C"))
                if not hasattr(self, '_close_icons_refs'):
                    self._close_icons_refs = []
                self._close_icons_refs.append(self.close_icon)

            # Make the entire tab_frame clickable to switch files
            tab_frame.bind("<Button-1>", lambda e, fp=file_path: self.open_file(fp))
            # Also bind child widgets for a larger clickable area
            if icon_label:
                icon_label.bind("<Button-1>", lambda e, fp=file_path: self.open_file(fp))
            tab_label.bind("<Button-1>", lambda e, fp=file_path: self.open_file(fp))
            
            # Hover effects for tab frame
            tab_frame.bind("<Enter>", lambda e, tf=tab_frame: tf.config(bg="#555555"))
            tab_frame.bind("<Leave>", lambda e, tf=tab_frame, fp=file_path: tf.config(bg="#555555" if fp == self.current_open_file else "#3C3C3C"))

        # Update canvas scroll region after adding/removing tabs
        self.tabs_canvas.update_idletasks()
        self.tabs_canvas.config(scrollregion=self.tabs_canvas.bbox("all"))


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
        # Destroy and recreate the main content frame and its children
        if hasattr(self, 'main_content_frame') and self.main_content_frame.winfo_exists():
            self.main_content_frame.destroy()
        
        self._create_main_content_area()
        self.file_explorer.populate_tree() 
        self.update_tabs() # Ensure tabs are repopulated after UI reset
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