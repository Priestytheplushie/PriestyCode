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
        self.text.insert(tk.END, f"\n{self.cwd}> ")

        self.process = None
        self.error_callback = None
        self.on_execution_start = None
        self.on_execution_finish = None

        self.after(100, self._process_output_queue)

    def stop(self):
        """Stops the currently running subprocess, if any."""
        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
                self.output_queue.put("\n--- Process terminated by user ---\n")
            except Exception as e:
                self.output_queue.put(f"\nError terminating process: {e}\n")

    def _on_enter(self, event):
        # Allow user to enter commands in the terminal
        command_start_index = self.text.search(f"{self.cwd}> ", "insert linestart", backwards=True)
        if command_start_index:
            command = self.text.get(f"{command_start_index} + {len(self.cwd)+2}c", "insert")
        else:
            command = self.text.get("insert linestart", "insert").strip()

        self.text.insert(tk.END, "\n")
        self.execute_command(command)
        return "break"

    def execute_command(self, command):
        if not command:
            self.text.insert(tk.END, f"{self.cwd}> ")
            return
        
        # Use a thread to run the command, keeping the UI responsive
        threading.Thread(target=self._run_in_thread, args=(command,), daemon=True).start()

    def _run_in_thread(self, command):
        if self.on_execution_start:
            self.on_execution_start()
        
        try:
            # Handle 'cd' command separately as it's a shell built-in
            if command.strip().startswith("cd "):
                new_dir = command.strip()[3:].strip()
                try:
                    os.chdir(new_dir)
                    self.cwd = os.getcwd()
                except FileNotFoundError:
                     self.output_queue.put(f"cd: no such file or directory: {new_dir}\n")
                except Exception as e:
                     self.output_queue.put(str(e) + "\n")
                return

            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                            shell=True, text=True, cwd=self.cwd, encoding='utf-8', bufsize=1)

            # Threads to read stdout and stderr without blocking
            stdout_thread = threading.Thread(target=self._read_stream, args=(self.process.stdout,), daemon=True)
            stderr_thread = threading.Thread(target=self._read_stream, args=(self.process.stderr,), daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for the process to complete
            self.process.wait()
            stdout_thread.join()
            stderr_thread.join()
            
            # Capture final stderr for error parsing
            _, stderr_output = self.process.communicate()
            if stderr_output and self.error_callback:
                self.error_callback(stderr_output)

        except Exception as e:
            self.output_queue.put(str(e) + "\n")
        finally:
            self.process = None
            self.output_queue.put(f"{self.cwd}> ")
            if self.on_execution_finish:
                self.on_execution_finish()
    
    def _read_stream(self, stream):
        """Reads lines from a stream and puts them in the output queue."""
        for line in iter(stream.readline, ''):
            self.output_queue.put(line)
        stream.close()

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