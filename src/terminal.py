# terminal.py

import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import queue
import os
import sys
import shutil
import time
import re

class Terminal(tk.Frame):
    def __init__(self, parent, stdin_queue: queue.Queue, cwd: str, python_executable: str):
        super().__init__(parent, bg="#1E1E1E")
        self.cwd = cwd
        self.python_executable = python_executable
        self.stdin_queue = stdin_queue
        self.process = None
        self.interactive_mode = False

        self.text = scrolledtext.ScrolledText(
            self, wrap="word", bg="#1E1E1E", fg="#CCCCCC",
            insertbackground="white", selectbackground="#4E4E4E",
            font=("Consolas", 10), borderwidth=0, highlightthickness=0
        )
        self.text.pack(fill="both", expand=True)
        
        self.ansi_escape_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.current_tags = []
        self.ansi_buffer = ""
        self._initialize_ansi_colors()

        self.text.bind("<Return>", self._on_enter_key)
        self.text.bind("<<Modified>>", self._on_modify)
        
        self.text.tag_config("prompt_venv", foreground="#66FF66")
        self.text.tag_config("prompt_path", foreground="#569CD6")
        self.text.tag_config("prompt_arrow", foreground="#C586C0")
        self.text.tag_config("stderr_tag", foreground="#FFB8B8")

        self.input_start_mark = "input_start"
        self.text.mark_set(self.input_start_mark, "1.0")
        self.text.mark_gravity(self.input_start_mark, "left")

        self.after(100, self.show_prompt)
        
    def _initialize_ansi_colors(self):
        self.ansi_colors = {
            '30': 'black', '31': '#CD3131', '32': '#0DBC79', '33': '#E5E510',
            '34': '#2472C8', '35': '#BC3FBC', '36': '#11A8CD', '37': '#E5E5E5',
            '90': '#767676', '91': '#F14C4C', '92': '#16C60C', '93': '#F9F1A5',
            '94': '#3B78FF', '95': '#D670D6', '96': '#61D6D6', '97': '#F2F2F2',
        }
        for code, color in self.ansi_colors.items():
            self.text.tag_config(f'ansi_{code}', foreground=color)

    def prepare_for_input(self):
        """Makes the terminal ready to accept user input after a program has printed output."""
        self.text.config(state="normal")
        # Set the mark before the final implicit newline to correctly capture input.
        self.text.mark_set(self.input_start_mark, self.text.index(f"{tk.END}-1c"))
        self.text.see(tk.END)
        self.text.focus_set()

    def set_cwd(self, new_cwd: str):
        self.cwd = new_cwd
        self.clear()
        self.show_prompt()

    def set_python_executable(self, new_path: str):
        self.python_executable = new_path
    
    def set_interactive_mode(self, is_interactive: bool):
        self.interactive_mode = is_interactive
        if not is_interactive:
            self.text.config(state="normal")
            self.after(100, self.show_prompt)

    def write(self, text: str, tags=None):
        """Writes text to the terminal, handling ANSI color codes and carriage returns robustly."""
        self.text.config(state="normal")

        if tags and "stderr_tag" in tags:
            self.text.insert(tk.END, text, ("stderr_tag",))
            self.text.see(tk.END)
            self.text.config(state="normal") # Keep it normal for subsequent writes
            return

        # Process carriage returns to enable single-line animations
        segments = text.split('\r')
        if len(segments) > 1:
            for i, segment in enumerate(segments):
                if i > 0:
                    # A '\r' was here. Delete the last line of output.
                    last_line_start = self.text.index("end-1c linestart")
                    self.text.delete(last_line_start, tk.END)
                
                # Now, process and write the current segment with ANSI handling
                self._write_segment_with_ansi(segment)
        else:
            # No carriage returns, process the whole text block at once
            self._write_segment_with_ansi(text)

        self.text.see(tk.END)
        # The state is left as 'normal' to allow continuous writing.
        # It should be set to 'disabled' only when waiting for user input.

    def _write_segment_with_ansi(self, text: str):
        """Helper method to process a single text segment for ANSI codes and insert it."""
        text_to_process = self.ansi_buffer + text
        self.ansi_buffer = ""
        
        last_end = 0
        for match in self.ansi_escape_pattern.finditer(text_to_process):
            start, end = match.span()
            
            if start > last_end:
                self.text.insert(tk.END, text_to_process[last_end:start], tuple(self.current_tags))
            
            escape_code = match.group(0)
            parts_str = escape_code.strip('\x1b[').strip('m')
            
            if not parts_str:
                self.current_tags = []
            else:
                parts = parts_str.split(';')
                for part in parts:
                    if part == '0' or part == '':
                        self.current_tags = []
                    elif part in self.ansi_colors:
                        self.current_tags = [f'ansi_{part}']
            
            last_end = end

        remaining_text = text_to_process[last_end:]
        
        # This logic handles partial ANSI codes that might be split between writes
        partial_code_index = remaining_text.rfind('\x1b')
        if partial_code_index != -1:
            safe_to_insert = remaining_text[:partial_code_index]
            self.ansi_buffer = remaining_text[partial_code_index:]
            if safe_to_insert:
                self.text.insert(tk.END, safe_to_insert, tuple(self.current_tags))
        else:
            if remaining_text:
                self.text.insert(tk.END, remaining_text, tuple(self.current_tags))

    def clear(self):
        self.text.config(state="normal")
        self.text.delete(1.0, tk.END)
        
    def show_prompt(self):
        self.text.config(state="normal")
        
        if self.text.index("end-1c") != "1.0":
            last_char = self.text.get("end-2c")
            if last_char != '\n':
                self.text.insert(tk.END, "\n")

        is_venv = '.venv' in self.python_executable or 'venv' in self.python_executable
        if is_venv:
            venv_name = os.path.basename(os.path.dirname(os.path.dirname(self.python_executable)))
            self.text.insert(tk.END, f"({venv_name}) ", ("prompt_venv",))
        
        home_dir = os.path.expanduser("~")
        display_path = self.cwd
        try:
            if self.cwd.startswith(home_dir):
                display_path = "~" + self.cwd[len(home_dir):].replace('\\', '/')
            else:
                display_path = display_path.replace('\\', '/')
        except Exception:
             pass

        self.text.insert(tk.END, f"{display_path} ", ("prompt_path",))
        self.text.insert(tk.END, "> ", ("prompt_arrow",))

        self.text.mark_set(self.input_start_mark, self.text.index(f"{tk.END}-1c"))
        self.text.see(tk.END)
        self.text.config(state="normal")
        self.current_tags = []

    def _on_modify(self, event=None):
        if self.text.compare(tk.INSERT, "<", self.input_start_mark):
             self.text.mark_set(tk.INSERT, self.input_start_mark)
        self.text.edit_modified(False)

    def _on_enter_key(self, event=None):
        command_line = self.text.get(self.input_start_mark, tk.END).strip()
        
        self.text.insert(tk.END, "\n")
        self.text.config(state="disabled")
        
        if self.interactive_mode:
            self.stdin_queue.put(command_line + '\n')
        else:
            self._handle_shell_command(command_line)
            
        return "break"

    def _handle_shell_command(self, command_line):
        if not command_line:
            self.show_prompt()
            return

        # ... (rest of the method is unchanged)
        if command_line.strip().lower() == "cd" or command_line.strip().lower() == "cd ~":
             home = os.path.expanduser("~")
             try:
                 os.chdir(home)
                 self.cwd = home
             except Exception as e:
                 self.write(f"cd: error changing to home directory: {e}\n", ("stderr_tag",))
             self.clear()
             self.show_prompt()
             return

        if command_line.strip().lower().startswith("cd "):
            path = command_line.strip()[3:].strip('"').strip("'")
            new_path = os.path.join(self.cwd, path) if not os.path.isabs(path) else path
            if os.path.isdir(new_path):
                try:
                    os.chdir(new_path)
                    self.cwd = os.path.abspath(new_path)
                except Exception as e:
                    self.write(f"cd: error changing directory: {e}\n", ("stderr_tag",))
            else:
                self.write(f"cd: no such file or directory: {path}\n", ("stderr_tag",))
            self.clear()
            self.show_prompt()
            return

        if command_line.lower() in ["cls", "clear"]:
            self.clear()
            self.show_prompt()
            return
        
        threading.Thread(target=self._execute_command_in_thread, args=(command_line,), daemon=True).start()

    def _execute_command_in_thread(self, command_str: str):
        # ... (method is unchanged)
        env = self._get_execution_env()
        scripts_dir = os.path.dirname(self.python_executable)

        try:
            parts = command_str.split()
            command_exe = parts[0]
            command_args = parts[1:]
        except IndexError:
            self.after(0, self.show_prompt)
            return

        search_path = f"{scripts_dir}{os.pathsep}{env.get('PATH', '')}"
        full_command_path = shutil.which(command_exe, path=search_path)
        
        if full_command_path:
            command_to_run = [full_command_path] + command_args
            use_shell = False
        else:
            command_to_run = command_str
            use_shell = True

        try:
            self.process = subprocess.Popen(
                command_to_run, shell=use_shell,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=self.cwd, env=env,
                bufsize=1, universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                encoding='utf-8'
            )

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    self.after(0, self.write, line)

        except FileNotFoundError:
            err_msg = f"Command not found: {command_exe}\n"
            self.after(0, self.write, err_msg, ("stderr_tag",))
        except Exception as e:
            self.after(0, self.write, f"Error: {repr(e)}\n", ("stderr_tag",))
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()
            self.process = None
            self.after(10, self.show_prompt)

    def _get_execution_env(self):
        # ... (method is unchanged)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"

        scripts_dir = os.path.dirname(self.python_executable)
        
        venv_root = None
        if os.path.basename(scripts_dir).lower() in ('scripts', 'bin'):
            potential_root = os.path.dirname(scripts_dir)
            if os.path.exists(os.path.join(potential_root, 'pyvenv.cfg')):
                venv_root = potential_root

        if venv_root:
            env['VIRTUAL_ENV'] = venv_root
            env['PATH'] = scripts_dir + os.pathsep + env.get('PATH', '')
        else:
            env['PATH'] = scripts_dir + os.pathsep + env.get('PATH', '')

        if sys.platform == 'win32' and 'PATH' in env:
            original_paths = env['PATH'].split(os.pathsep)
            filtered_paths = [p for p in original_paths if 'windowsapps' not in p.lower()]
            env['PATH'] = os.pathsep.join(filtered_paths)

        return env