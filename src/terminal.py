import tkinter as tk
import subprocess
import threading
import queue
import os

class Terminal(tk.Frame):
    def __init__(self, parent, stdin_queue: queue.Queue, **kwargs):
        super().__init__(parent, **kwargs)
        self.config(bg="#1E1E1E")

        self.text = tk.Text(self, bg="#1E1E1E", fg="#CCCCCC", insertbackground="white",
                            selectbackground="#4E4E4E", font=("Consolas", 10), undo=True,
                            borderwidth=0, highlightthickness=0)
        self.text.pack(fill="both", expand=True)

        self.text.bind("<Return>", self._on_enter)
        self.text.bind("<Button-1>", lambda e: self.after(10, self.text.focus_set))
        
        self.output_queue = queue.Queue()
        self.stdin_queue = stdin_queue

        self.cwd = os.getcwd()
        self.interactive_mode = False
        
        self.input_start_mark = "input_start_mark"
        self.text.mark_set(self.input_start_mark, "1.0")
        self.text.mark_gravity(self.input_start_mark, "left")

        self.after(100, self._process_output_queue)
        self.show_prompt()

    def set_interactive_mode(self, is_interactive: bool):
        self.interactive_mode = is_interactive
        if is_interactive:
            self.text.mark_set(self.input_start_mark, tk.END)
        if not is_interactive:
            self.after(100, self.show_prompt)

    def _on_enter(self, event):
        if self.interactive_mode:
            user_input = self.text.get(self.input_start_mark, "insert")
            self.stdin_queue.put(user_input + "\n")
            self.text.insert(tk.END, "\n")
            self.text.see(tk.END)
            self.text.mark_set(self.input_start_mark, tk.END)
            return "break"

        if self.text.compare("insert", "<", "end-1l linestart"):
            self.text.mark_set(tk.INSERT, tk.END)
            return "break"

        last_prompt_pos = self.text.search(">", "1.0", tk.END, backwards=True)
        if not last_prompt_pos:
            return "break"
        
        command_start_pos = self.text.index(f"{last_prompt_pos} + 2c")
        command = self.text.get(command_start_pos, "end-1c").strip()
        
        self.text.insert(tk.END, "\n")
        self.text.see(tk.END)

        if command:
            self._execute_command(command)
        else:
            self.show_prompt()
            
        return "break"

    def _execute_command(self, command):
        threading.Thread(target=self._run_shell_command, args=(command,), daemon=True).start()

    def _run_shell_command(self, command):
        try:
            if command.strip().lower().startswith("cd "):
                new_dir = command.strip()[3:]
                try: os.chdir(os.path.join(self.cwd, new_dir)); self.cwd = os.getcwd()
                except FileNotFoundError as e: self.output_queue.put(str(e) + "\n")
                self.show_prompt()
                return

            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=self.cwd)
            stdout, stderr = process.communicate()
            if stdout: self.output_queue.put(stdout)
            if stderr: self.output_queue.put(stderr)
            self.show_prompt()
        except Exception as e:
            self.output_queue.put(f"Error: {e}\n")
            self.show_prompt()

    def write(self, text, tag=None):
        self.output_queue.put((text, tag))

    def _process_output_queue(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                self.text.config(state="normal")
                text_to_insert, tag_to_apply = ("", None)

                if isinstance(item, tuple):
                    text_to_insert, tag_to_apply = item
                else:
                    text_to_insert = str(item)
                
                if tag_to_apply:
                    self.text.insert(tk.END, text_to_insert, tag_to_apply)
                else:
                    self.text.insert(tk.END, text_to_insert)

                self.text.see(tk.END)
                
                if self.interactive_mode:
                    self.text.mark_set(self.input_start_mark, tk.END)

                self.text.config(state="normal")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_output_queue)

    def show_prompt(self):
        if not self.interactive_mode:
            self.output_queue.put(f"\n{self.cwd}> ")

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        if not self.interactive_mode:
            self.show_prompt()
        self.text.see(tk.END)