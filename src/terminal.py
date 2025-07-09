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
    def __init__(
        self, parent, stdin_queue: queue.Queue, cwd: str, python_executable: str
    ):
        super().__init__(parent, bg="#1E1E1E")
        self.cwd = cwd
        self.python_executable = python_executable
        self.stdin_queue = stdin_queue
        self.process = None
        self.interactive_mode = False
        self.display_name_widget: tk.Label | None = None

        self.text = scrolledtext.ScrolledText(
            self,
            wrap="word",
            bg="#1E1E1E",
            fg="#CCCCCC",
            insertbackground="white",
            selectbackground="#4E4E4E",
            font=("Consolas", 10),
            borderwidth=0,
            highlightthickness=0,
        )
        self.text.pack(fill="both", expand=True)

        self.ansi_escape_pattern = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.current_tags = []
        self.ansi_buffer = ""
        self._initialize_ansi_colors()

        self.text.bind("<Return>", self._on_enter_key)
        # FIX: Replace ineffective <<Modified>> binding with a preventative <Key> binding
        self.text.bind("<Key>", self._on_key)

        self.text.tag_config("prompt_venv", foreground="#66FF66")
        self.text.tag_config("prompt_path", foreground="#569CD6")
        self.text.tag_config("prompt_arrow", foreground="#C586C0")
        self.text.tag_config("stderr_tag", foreground="#FFB8B8")

        self.input_start_mark = "input_start"
        self.text.mark_set(self.input_start_mark, "1.0")
        self.text.mark_gravity(self.input_start_mark, "left")

        self.after(100, self.show_prompt)

    def _initialize_ansi_colors(self):
        """Initializes Tkinter tags and categorizes ANSI color codes."""
        # FIX 2: Added background colors to the map for proper parsing.
        ansi_color_map = {
            # Foreground
            "30": ("foreground", "black"),
            "31": ("foreground", "#CD3131"),
            "32": ("foreground", "#0DBC79"),
            "33": ("foreground", "#E5E510"),
            "34": ("foreground", "#2472C8"),
            "35": ("foreground", "#BC3FBC"),
            "36": ("foreground", "#11A8CD"),
            "37": ("foreground", "#E5E5E5"),
            "90": ("foreground", "#767676"),
            "91": ("foreground", "#F14C4C"),
            "92": ("foreground", "#16C60C"),
            "93": ("foreground", "#F9F1A5"),
            "94": ("foreground", "#3B78FF"),
            "95": ("foreground", "#D670D6"),
            "96": ("foreground", "#61D6D6"),
            "97": ("foreground", "#F2F2F2"),
            # Background
            "40": ("background", "#1E1E1E"),
            "41": ("background", "#CD3131"),
            "42": ("background", "#0DBC79"),
            "43": ("background", "#E5E510"),
            "44": ("background", "#2472C8"),
            "45": ("background", "#BC3FBC"),
            "46": ("background", "#11A8CD"),
            "47": ("background", "#E5E5E5"),
            "100": ("background", "#767676"),
            "101": ("background", "#F14C4C"),
            "102": ("background", "#16C60C"),
            "103": ("background", "#F9F1A5"),
            "104": ("background", "#3B78FF"),
            "105": ("background", "#D670D6"),
            "106": ("background", "#61D6D6"),
            "107": ("background", "#F2F2F2"),
        }

        self.ansi_codes = {}
        self.fg_color_codes = set()
        self.bg_color_codes = set()

        for code, (prop, color) in ansi_color_map.items():
            self.text.tag_config(f"ansi_{code}", **{prop: color})
            self.ansi_codes[code] = prop
            if prop == "foreground":
                self.fg_color_codes.add(code)
            elif prop == "background":
                self.bg_color_codes.add(code)

    def prepare_for_input(self):
        self.text.config(state="normal")
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
        self.text.config(state="normal")
        additional_tags = list(tags) if tags else []
        segments = text.split("\r")
        if len(segments) > 1:
            for i, segment in enumerate(segments):
                if i > 0:
                    last_line_start = self.text.index("end-1c linestart")
                    self.text.delete(last_line_start, tk.END)
                self._write_segment_with_ansi(segment, additional_tags)
        else:
            self._write_segment_with_ansi(text, additional_tags)
        self.text.see(tk.END)

    def _remove_tags_by_type(self, color_type: str):
        """Removes all fg or bg tags from the current_tags list."""
        prefixes = ()
        if color_type == "fg":
            prefixes = ("ansi_3", "ansi_9")
        elif color_type == "bg":
            prefixes = ("ansi_4", "ansi_10")
        self.current_tags = [t for t in self.current_tags if not t.startswith(prefixes)]

    def _write_segment_with_ansi(self, text: str, additional_tags: list[str]):
        text_to_process = self.ansi_buffer + text
        self.ansi_buffer = ""

        last_end = 0
        for match in self.ansi_escape_pattern.finditer(text_to_process):
            start, end = match.span()

            if start > last_end:
                current_combined_tags = tuple(self.current_tags + additional_tags)
                self.text.insert(
                    tk.END, text_to_process[last_end:start], current_combined_tags
                )

            escape_code = match.group(0)
            parts_str = escape_code.strip("\x1b[").strip("m")

            if not parts_str:
                self.current_tags = []
            else:
                parts = parts_str.split(";")
                for part in parts:
                    # FIX 2: More robust ANSI state management
                    part = part.lstrip("0") or "0"

                    if part == "0":  # Full Reset
                        self.current_tags = []
                    elif part == "39":  # Reset Foreground
                        self._remove_tags_by_type("fg")
                    elif part == "49":  # Reset Background
                        self._remove_tags_by_type("bg")
                    elif part in self.ansi_codes:
                        prop = self.ansi_codes[part]
                        if prop == "foreground":
                            self._remove_tags_by_type("fg")
                        elif prop == "background":
                            self._remove_tags_by_type("bg")

                        color_tag = f"ansi_{part}"
                        if color_tag not in self.current_tags:
                            self.current_tags.append(color_tag)

            last_end = end

        remaining_text = text_to_process[last_end:]

        partial_code_index = remaining_text.rfind("\x1b")
        if partial_code_index != -1 and not remaining_text[
            partial_code_index:
        ].endswith("m"):
            safe_to_insert = remaining_text[:partial_code_index]
            self.ansi_buffer = remaining_text[partial_code_index:]
            if safe_to_insert:
                current_combined_tags = tuple(self.current_tags + additional_tags)
                self.text.insert(tk.END, safe_to_insert, current_combined_tags)
        else:
            if remaining_text:
                current_combined_tags = tuple(self.current_tags + additional_tags)
                self.text.insert(tk.END, remaining_text, current_combined_tags)

    def clear(self):
        self.text.config(state="normal")
        self.text.delete(1.0, tk.END)
        self.ansi_buffer = ""
        self.current_tags = []

    def show_prompt(self):
        self.text.config(state="normal")
        if self.text.index("end-1c") != "1.0":
            last_char = self.text.get("end-2c")
            if last_char != "\n":
                self.text.insert(tk.END, "\n")
        is_venv = ".venv" in self.python_executable or "venv" in self.python_executable
        if is_venv:
            venv_name = os.path.basename(
                os.path.dirname(os.path.dirname(self.python_executable))
            )
            self.text.insert(tk.END, f"({venv_name}) ", ("prompt_venv",))
        home_dir = os.path.expanduser("~")
        display_path = self.cwd
        try:
            if self.cwd.startswith(home_dir):
                display_path = "~" + self.cwd[len(home_dir) :].replace("\\", "/")
            else:
                display_path = display_path.replace("\\", "/")
        except Exception:
            pass
        self.text.insert(tk.END, f"{display_path} ", ("prompt_path",))
        self.text.insert(tk.END, "> ", ("prompt_arrow",))
        self.text.mark_set(self.input_start_mark, self.text.index(f"{tk.END}-1c"))
        self.text.see(tk.END)
        self.text.config(state="normal")
        self.current_tags = []

    # FIX: Replaced _on_modify with a robust preventative key handler
    def _on_key(self, event):
        """Prevents the user from modifying the read-only part of the terminal."""
        # Allow copy (Ctrl+C)
        if event.state & 4 and event.keysym.lower() == "c":
            return

        # Allow all other Ctrl-key combos for now (e.g., for other shortcuts)
        # except for paste (v) and cut (x) which are handled below.
        if event.state & 4 and event.keysym.lower() not in ("v", "x"):
            return

        # Check if a selection exists.
        try:
            sel_start = self.text.index(tk.SEL_FIRST)
            # If selection is in the protected area, block the key press.
            if self.text.compare(sel_start, "<", self.input_start_mark):
                # Allow navigation keys to move the cursor out of the selection
                if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End"):
                    return
                return "break"
        except tk.TclError:
            # No selection, check the insertion cursor.
            insert_index = self.text.index(tk.INSERT)
            if self.text.compare(insert_index, "<", self.input_start_mark):
                # Allow navigation keys
                if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End"):
                    return
                # Block all other keys
                return "break"

        # Prevent deleting the prompt with backspace at the boundary
        insert_index = self.text.index(tk.INSERT)
        if (
            self.text.compare(insert_index, "==", self.input_start_mark)
            and event.keysym == "BackSpace"
        ):
            return "break"

        return  # Allow the key press

    def _on_enter_key(self, event=None):
        command_line = self.text.get(self.input_start_mark, tk.END).strip()
        self.text.insert(tk.END, "\n")
        self.text.config(state="disabled")
        if self.interactive_mode:
            self.stdin_queue.put(command_line + "\n")
        else:
            self._handle_shell_command(command_line)
        return "break"

    def _handle_shell_command(self, command_line):
        if not command_line:
            self.show_prompt()
            return
        if (
            command_line.strip().lower() == "cd"
            or command_line.strip().lower() == "cd ~"
        ):
            home = os.path.expanduser("~")
            try:
                os.chdir(home)
                self.cwd = home
            except Exception as e:
                self.write(
                    f"cd: error changing to home directory: {e}\n", ("stderr_tag",)
                )
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
        threading.Thread(
            target=self._execute_command_in_thread, args=(command_line,), daemon=True
        ).start()

    def _execute_command_in_thread(self, command_str: str):
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
                command_to_run,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.cwd,
                env=env,
                bufsize=1,
                universal_newlines=True,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
                encoding="utf-8",
            )
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ""):
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
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["FORCE_COLOR"] = "1"
        scripts_dir = os.path.dirname(self.python_executable)
        venv_root = None
        if os.path.basename(scripts_dir).lower() in ("scripts", "bin"):
            potential_root = os.path.dirname(scripts_dir)
            if os.path.exists(os.path.join(potential_root, "pyvenv.cfg")):
                venv_root = potential_root
        if venv_root:
            env["VIRTUAL_ENV"] = venv_root
            env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")
        else:
            env["PATH"] = scripts_dir + os.pathsep + env.get("PATH", "")
        if sys.platform == "win32" and "PATH" in env:
            original_paths = env["PATH"].split(os.pathsep)
            filtered_paths = [
                p for p in original_paths if "windowsapps" not in p.lower()
            ]
            env["PATH"] = os.pathsep.join(filtered_paths)
        return env
