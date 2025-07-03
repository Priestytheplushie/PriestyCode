# code_editor.py
import tkinter as tk
from tkinter import scrolledtext
import re
import ast # Added this import

class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, **kwargs): # Added error_console parameter
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B") 

        # Store the error_console instance
        self.error_console = error_console

        # Create a frame to hold the line numbers and text area
        self.editor_frame = tk.Frame(self, bg="#2B2B2B")
        self.editor_frame.pack(fill="both", expand=True)

        # Line numbers widget
        self.linenumbers = tk.Text(self.editor_frame, width=4, padx=3, takefocus=0,
                                   border=0, background="#2B2B2B", foreground="#888888",
                                   state="disabled", wrap="none", font=("Consolas", 10))
        self.linenumbers.pack(side="left", fill="y")

        # Code text area
        self.text_area = scrolledtext.ScrolledText(self.editor_frame, wrap="word",
                                                   bg="#2B2B2B", fg="white",
                                                   insertbackground="white",
                                                   selectbackground="#4E4E4E",
                                                   font=("Consolas", 10),
                                                   undo=True) # Enable undo/redo
        self.text_area.pack(side="right", fill="both", expand=True)

        # Bindings for scrolling and text modification
        self.text_area.bind("<Configure>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<<Change>>", self._on_text_modified)
        self.text_area.bind("<MouseWheel>", self._on_mouse_scroll) # For Windows and macOS
        self.text_area.bind("<Button-4>", self._on_mouse_scroll) # For Linux
        self.text_area.bind("<Button-5>", self._on_mouse_scroll) # For Linux

        # Create a tag for error highlighting
        self.text_area.tag_config("error_line", background="red", foreground="white")
        self.error_line_tag_added = False # To track if the tag is currently applied

        # Syntax highlighting tags
        self.text_area.tag_config("keyword", foreground="#569CD6")
        self.text_area.tag_config("string_literal", foreground="#D69D85")
        self.text_area.tag_config("comment_tag", foreground="#6A9955")
        self.text_area.tag_config("function_def", foreground="#DCDCAA")
        self.text_area.tag_config("class_def", foreground="#DCDCAA")
        self.text_area.tag_config("number", foreground="#B5CEA8")
        self.text_area.tag_config("operator", foreground="#D4D4D4")
        self.text_area.tag_config("builtin", foreground="#4EC9B0")
        self.text_area.tag_config("function_param", foreground="#9CDCFE") # Color for function parameters

        # Custom keywords for Python (can be expanded)
        self.keywords = ["False", "None", "True", "and", "as", "assert", "async", "await",
                         "break", "class", "continue", "def", "del", "elif", "else",
                         "except", "finally", "for", "from", "global", "if", "import",
                         "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
                         "return", "try", "while", "with", "yield"]

        self.builtin_functions = ["abs", "all", "any", "ascii", "bin", "bool", "dir",
                                  "divmod", "enumerate", "filter", "float", "format",
                                  "frozenset", "getattr", "hasattr", "hash", "help",
                                  "hex", "id", "input", "int", "isinstance", "issubclass",
                                  "iter", "len", "list", "map", "max", "min", "next",
                                  "object", "oct", "open", "ord", "pow", "print", "range",
                                  "repr", "reversed", "round", "set", "setattr", "slice",
                                  "sorted", "sum", "super", "tuple", "type", "vars", "zip"]

        # Configure a custom tag for tracking changes (hidden)
        self.text_area.tag_configure("change", foreground="red")
        self.text_area.edit_modified(False) # Reset modified flag

    def update_line_numbers(self, event=None):
        self.linenumbers.config(state="normal")
        self.linenumbers.delete("1.0", tk.END)

        # Get the number of lines in the text area
        num_lines = self.text_area.index("end-1c").split('.')[0]
        line_numbers_text = "\n".join(str(i) for i in range(1, int(num_lines) + 1))
        self.linenumbers.insert("1.0", line_numbers_text)

        self.linenumbers.config(state="disabled")

        # Sync scrolling
        first_visible_line = self.text_area.yview()[0]
        self.linenumbers.yview_moveto(first_visible_line)

    def _on_key_release(self, event=None):
        # Trigger syntax highlighting on key release
        self.apply_syntax_highlighting()

    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            self.update_line_numbers()
            self.apply_syntax_highlighting()
            self._proactive_syntax_check() # Added this call
            self.text_area.edit_modified(False) # Reset the modified flag

    def _on_mouse_scroll(self, event):
        self.linenumbers.yview_scroll(-1 * (event.delta // 120), "units")
        self.text_area.yview_scroll(-1 * (event.delta // 120), "units")
        return "break" # Prevent default scroll behavior for text_area

    def get_content(self):
        return self.text_area.get("1.0", tk.END)

    def set_content(self, content):
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)
        self.update_line_numbers()
        self.apply_syntax_highlighting()

    def highlight_error_line(self, line_number):
        self.clear_error_highlight() # Clear any existing highlights first
        start = f"{line_number}.0"
        end = f"{line_number}.end"
        self.text_area.tag_add("error_line", start, end)
        self.error_line_tag_added = True

    def clear_error_highlight(self):
        if self.error_line_tag_added:
            self.text_area.tag_remove("error_line", "1.0", tk.END)
            self.error_line_tag_added = False

    def apply_syntax_highlighting(self):
        for tag in ["keyword", "string_literal", "comment_tag", "function_def",
                    "class_def", "number", "operator", "builtin", "function_param"]:
            self.text_area.tag_remove(tag, "1.0", tk.END)

        content = self.text_area.get("1.0", tk.END)
        lines = content.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1
            # Comments
            for match in re.finditer(r'#.*$', line):
                start, end = match.span()
                self._apply_tag("comment_tag", line_num, start, end)

            # Strings (single, double, triple single, triple double)
            for match in re.finditer(r'''("""[^"]*"""|'''
                                     r"""'''[^']*'''|"""
                                     r'''"[^"\\]*(?:\\.[^"\\]*)*"|'''
                                     r"""'[^'\\]*(?:\\.[^'\\]*)*'?)""", line):
                start, end = match.span()
                self._apply_tag("string_literal", line_num, start, end)

            # Keywords (ensure whole words)
            for keyword in self.keywords:
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', line):
                    # Check if the match is not inside a string or comment
                    if not (self._is_inside_tag(line_num, match.start(), match.end(), "string_literal") or
                            self._is_inside_tag(line_num, match.start(), match.end(), "comment_tag")):
                        self._apply_tag("keyword", line_num, match.start(), match.end())

            # Function definitions
            for match in re.finditer(r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line):
                name_start = match.start(1)
                name_end = match.end(1)
                if not (self._is_inside_tag(line_num, name_start, name_end, "string_literal") or
                        self._is_inside_tag(line_num, name_start, name_end, "comment_tag")):
                    self._apply_tag("function_def", line_num, name_start, name_end)

            # Class definitions
            for match in re.finditer(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]', line):
                name_start = match.start(1)
                name_end = match.end(1)
                if not (self._is_inside_tag(line_num, name_start, name_end, "string_literal") or
                        self._is_inside_tag(line_num, name_start, name_end, "comment_tag")):
                    self._apply_tag("class_def", line_num, name_start, name_end)

            # Numbers
            for match in re.finditer(r'\b\d+(\.\d*)?([eE][+-]?\d+)?\b', line):
                if not (self._is_inside_tag(line_num, match.start(), match.end(), "string_literal") or
                        self._is_inside_tag(line_num, match.start(), match.end(), "comment_tag")):
                    self._apply_tag("number", line_num, match.start(), match.end())

            # Operators (a simpler approach, could be more exhaustive)
            for match in re.finditer(r'[+\-*/%&|^~=<>!:]', line):
                if not (self._is_inside_tag(line_num, match.start(), match.end(), "string_literal") or
                        self._is_inside_tag(line_num, match.start(), match.end(), "comment_tag")):
                    self._apply_tag("operator", line_num, match.start(), match.end())

            # Built-in functions
            for builtin in self.builtin_functions:
                for match in re.finditer(r'\b' + re.escape(builtin) + r'\b', line):
                    if not (self._is_inside_tag(line_num, match.start(), match.end(), "string_literal") or
                            self._is_inside_tag(line_num, match.start(), match.end(), "comment_tag") or
                            self._is_inside_tag(line_num, match.start(), match.end(), "function_def") or # Avoid highlighting if it's a func name
                            self._is_inside_tag(line_num, match.start(), match.end(), "class_def")): # Avoid highlighting if it's a class name
                        self._apply_tag("builtin", line_num, match.start(), match.end())
            
            # Function parameters within def
            def_matches = list(re.finditer(r'\bdef\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\((.*?)\):', line))
            for def_match in def_matches:
                params_str = def_match.group(1) # Get the content inside the parentheses
                
                # Regex to find parameter names, ignoring default values or type hints
                # This regex is a bit more robust for parameter extraction
                params = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*=\s*.*?)?(?:\s*:\s*.*?)?(?:,\s*|\s*$)', params_str)
                
                current_offset = def_match.start(1) # Start looking from where the parameters begin
                for param in params:
                    # Find the exact start position of the parameter name within the params_str
                    match_in_params = re.search(r'\b' + re.escape(param) + r'\b', params_str[current_offset - def_match.start(1):])
                    if match_in_params:
                        start_char_in_line = def_match.start(1) + (current_offset - def_match.start(1)) + match_in_params.start()
                        
                        start_index = f"{line_num}.{start_char_in_line}"
                        end_index = f"{line_num}.{start_char_in_line + len(param)}"
                        
                        # Only highlight if not inside a string or comment
                        if not (self.text_area.tag_nextrange("string_literal", start_index, end_index) or
                                self.text_area.tag_nextrange("comment_tag", start_index, end_index)):
                            self.text_area.tag_add("function_param", start_index, end_index)


    def _apply_tag(self, tag_name, line_num, start_char, end_char):
        self.text_area.tag_add(tag_name, f"{line_num}.{start_char}", f"{line_num}.{end_char}")

    def _is_inside_tag(self, line_num, start_char, end_char, tag_name):
        # Check if the given range is inside an already applied tag (e.g., string or comment)
        # This prevents keywords/functions being highlighted inside strings/comments
        index_start = f"{line_num}.{start_char}"
        index_end = f"{line_num}.{end_char}"
        return bool(self.text_area.tag_nextrange(tag_name, index_start, index_end))
    
    def _proactive_syntax_check(self):
        code_content = self.text_area.get("1.0", tk.END)
        self.clear_error_highlight() # Clear previous highlights before checking again

        if not code_content.strip(): # Don't check empty content
            if self.error_console:
                self.error_console.clear() # Clear console if code is empty
            return

        try:
            # Attempt to parse the code. This will raise SyntaxError on invalid syntax.
            ast.parse(code_content)
            # If parsing is successful, clear any previous error messages
            if self.error_console:
                self.error_console.clear() # Clear any proactive error messages
        except SyntaxError as e:
            line_num = e.lineno
            message = e.msg
            offset = e.offset if e.offset is not None else 0

            # Highlight the line in the editor
            self.highlight_error_line(line_num)

            # Display the error in the error console
            if self.error_console:
                # Use your format_error_output method
                error_text = f"Proactive Syntax Error (Line {line_num}): {message}\n"
                self.error_console.format_error_output(error_text, f"Full Error Details:\n{e}")
        except Exception as e:
            # Catch other potential parsing errors (less common for basic syntax issues)
            if self.error_console:
                self.error_console.format_error_output(f"Proactive Check Error: {e}", f"Full Error Details:\n{e}")