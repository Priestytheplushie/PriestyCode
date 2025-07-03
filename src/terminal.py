import tkinter as tk
import subprocess
import threading
import queue
import os

class Terminal(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.config(bg="#1E1E1E")

        self.text = tk.Text(self, bg="#1E1E1E", fg="#CCCCCC", insertbackground="white",
                            selectbackground="#4E4E4E", font=("Consolas", 10), undo=True)
        self.text.pack(fill="both", expand=True)

        self.text.bind("<Return>", self._on_enter)
        self.output_queue = queue.Queue()

        self.cwd = os.getcwd()
        self.text.insert(tk.END, f"{self.cwd}> ")

        self.after(100, self._process_output_queue)

    def _on_enter(self, event):
        command = self.text.get("insert linestart", "insert").strip()
        if command.startswith(f"{self.cwd}> "):
            command = command[len(self.cwd)+2:]

        self.text.insert(tk.END, "\n")
        self.execute_command(command)
        return "break"

    def execute_command(self, command):
        if not command:
            self.text.insert(tk.END, f"{self.cwd}> ")
            return

        threading.Thread(target=self._run_in_thread, args=(command,), daemon=True).start()

    def _run_in_thread(self, command):
        try:
            if command.startswith("cd "):
                new_dir = command[3:].strip()
                os.chdir(new_dir)
                self.cwd = os.getcwd()
                self.output_queue.put(f"{self.cwd}> ")
                return

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                       shell=True, text=True, cwd=self.cwd)

            stdout, stderr = process.communicate()

            if stdout:
                self.output_queue.put(stdout)
            if stderr:
                self.output_queue.put(stderr)

        except Exception as e:
            self.output_queue.put(str(e) + "\n")
        finally:
            self.output_queue.put(f"{self.cwd}> ")

    def _process_output_queue(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.text.insert(tk.END, line)
                self.text.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_output_queue)
