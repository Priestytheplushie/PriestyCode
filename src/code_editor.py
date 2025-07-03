import tkinter as tk
from tkinter import scrolledtext
import re

class CodeEditor(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B") 

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
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<MouseWheel>", self._on_mousewheel)
        self.text_area.bind("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.text_area.bind("<Button-5>", self._on_mousewheel) # Linux scroll down
        self.text_area.bind("<Return>", self._auto_indent) # Auto-indent on Enter
        self.text_area.bind("<<Modified>>", self._on_text_modified)
        self.text_area.edit_modified(False) # Reset modified flag

        # --- New Bindings for Auto-completion ---
        self.text_area.bind("(", lambda event: self._auto_complete_brackets(event, '(', ')'))
        self.text_area.bind("[", lambda event: self._auto_complete_brackets(event, '[', ']'))
        self.text_area.bind("{", lambda event: self._auto_complete_brackets(event, '{', '}'))

        self._update_line_numbers()

        # Syntax highlighting tags with refined colors
        self.text_area.tag_configure("priesty_keyword", foreground="#DA70D6") # Orchid (pink/purple-ish)

        self.text_area.tag_configure("def_class_keyword", foreground="#569CD6") # Light Blue for def, class
        self.text_area.tag_configure("flow_control_keyword", foreground="#C586C0") # Light Purple for if, else, for, while, return, break, continue, pass, yield
        self.text_area.tag_configure("import_keyword", foreground="#4EC9B0") # Teal for import, from, as
        self.text_area.tag_configure("exception_keyword", foreground="#D16969") # Reddish for try, except, finally, raise, assert
        self.text_area.tag_configure("boolean_none_keyword", foreground="#569CD6") # Light Blue for True, False, None
        self.text_area.tag_configure("operator_keyword", foreground="#DCDCAA") # Light Yellow for and, or, not, in, is
        self.text_area.tag_configure("global_del_keyword", foreground="#B8D7A3") # Light Green for del, global, nonlocal
        self.text_area.tag_configure("async_await_keyword", foreground="#FFD700") # Gold for async, await
        self.text_area.tag_configure("with_lambda_keyword", foreground="#CE9178") # Orange for with, lambda

        # New tags for values, comments, and parameters
        self.text_area.tag_configure("string_literal", foreground="#A3C78B") # Light Green for strings
        self.text_area.tag_configure("number_literal", foreground="#B5CEA8") # Lighter Green for numbers
        self.text_area.tag_configure("comment_tag", foreground="#6A9955") # Darker Green for comments
        self.text_area.tag_configure("function_param", foreground="#9CDCFE") # Lighter Blue for function parameters/arguments
        self.text_area.tag_configure("error_line_tag", foreground="#FF3333", underline=True)

        # --- New tag for parentheses/brackets ---
        self.text_area.tag_configure("bracket_tag", foreground="#FFD700") # Gold for brackets

        # Initial highlighting
        self._highlight_syntax()

    def highlight_error_line(self, line_number):
        self.text_area.tag_remove("error_line_tag", 1.0, tk.END) # Clear previous error highlights
        start_index = f"{line_number}.0"
        end_index = f"{line_number}.end"
        self.text_area.tag_add("error_line_tag", start_index, end_index)

    def clear_error_highlight(self):
        self.text_area.tag_remove("error_line_tag", 1.0, tk.END)

    def _on_key_release(self, event=None):
        self._update_line_numbers()
        # Only re-highlight on general key release, auto-complete will call it too
        # Exclude enter key as auto_indent calls highlight
        if event and event.keysym not in ("Return", "(", "[", "{"):
            self._highlight_syntax()

    def _on_mousewheel(self, event):
        self.linenumbers.yview_moveto(self.text_area.yview()[0])

    def _on_text_modified(self, event=None):
        self.text_area.edit_modified(False)
        self._update_line_numbers()
        self._highlight_syntax()

    # --- New method for auto-completion ---
    def _auto_complete_brackets(self, event, open_char, close_char):
        self.text_area.edit_separator() # Mark for undo/redo
        self.text_area.insert(tk.INSERT, open_char) # Insert the opening char
        self.text_area.insert(tk.INSERT, close_char) # Insert the closing char
        self.text_area.mark_set(tk.INSERT, tk.INSERT + "-1c") # Move cursor back one character
        self._highlight_syntax() # Re-highlight after insertion
        return "break" # Prevent Tkinter's default insertion of the open_char


    def _update_line_numbers(self):
        self.linenumbers.config(state="normal")
        self.linenumbers.delete(1.0, tk.END)

        content = self.text_area.get(1.0, tk.END)
        line_count = content.count('\n')
        if not content.strip() and line_count <= 1:
             line_count = 1
        elif content.endswith('\n') and content.strip():
            pass
        elif not content.endswith('\n') and content.strip():
            line_count += 1

        for i in range(1, line_count + 1):
            self.linenumbers.insert(tk.END, f"{i}\n")
        self.linenumbers.config(state="disabled")

        self.linenumbers.yview_moveto(self.text_area.yview()[0])


    def _auto_indent(self, event):
        self.text_area.edit_separator()
        current_index = self.text_area.index(tk.INSERT)
        line, char_index = map(int, current_index.split('.'))

        current_line_content = self.text_area.get(f"{line}.0", current_index)
        stripped_current_line = current_line_content.rstrip()

        self.text_area.insert(tk.INSERT, "\n")

        prev_indent_match = re.match(r'^(\s*)', stripped_current_line)
        prev_indent = prev_indent_match.group(1) if prev_indent_match else ""

        indent_to_insert = prev_indent
        if stripped_current_line.endswith(':'):
            indent_to_insert += "    " # Add one more level of indentation (4 spaces)

        self.text_area.insert(tk.INSERT, indent_to_insert)

        self._update_line_numbers()
        self._highlight_syntax()
        return "break" # Prevent default Tkinter Enter behavior


    def _highlight_syntax(self):
        for tag in self.text_area.tag_names():
            if tag not in ("sel", "insert", "current"):
                self.text_area.tag_remove(tag, 1.0, tk.END)

        content = self.text_area.get(1.0, tk.END)

        highlight_patterns = {
            r"\bPriesty\b": "priesty_keyword",

            # Definition keywords
            r"\b(def|class)\b": "def_class_keyword",

            # Control flow and statements
            r"\b(if|else|elif|for|while|return|break|continue|yield|pass)\b": "flow_control_keyword",

            # Import keywords
            r"\b(import|from|as)\b": "import_keyword",

            # Exception handling
            r"\b(try|except|finally|raise|assert)\b": "exception_keyword",

            # Boolean and None
            r"\b(True|False|None)\b": "boolean_none_keyword",

            # Logical/Membership/Identity operators as keywords
            r"\b(and|or|not|in|is)\b": "operator_keyword",

            # Variable scope and deletion
            r"\b(del|global|nonlocal)\b": "global_del_keyword",

            # Async/Await for coroutines
            r"\b(async|await)\b": "async_await_keyword",

            # Context manager and anonymous function
            r"\b(with|lambda)\b": "with_lambda_keyword",

            # Strings: single-quoted and double-quoted
            # This regex needs to be careful not to match across lines or in comments
            # A more robust string regex would handle escaped quotes, but this is a start
            r"""("|')(?:(?=(\\?))\2.)*?\1""": "string_literal",
            r"('''|\"\"\")(?:.|\n)*?\1": "string_literal", # Triple quoted strings

            # Numbers: integers and floats
            r"\b\d+(\.\d*)?([eE][+-]?\d+)?\b": "number_literal",
            # Comments: lines starting with #
            r"#.*": "comment_tag",

            # --- New: Parentheses and Brackets ---
            r"[(){}[\]]": "bracket_tag",
        }

        # Temporarily remove string and comment tags for re-highlighting
        self.text_area.tag_remove("string_literal", 1.0, tk.END)
        self.text_area.tag_remove("comment_tag", 1.0, tk.END)
        self.text_area.tag_remove("bracket_tag", 1.0, tk.END) # Clear bracket tags too

        # Process comments first
        for match in re.finditer(r"(#.*)", content):
            start_index = self.text_area.index(f"1.0 + {match.start()} chars")
            end_index = self.text_area.index(f"1.0 + {match.end()} chars")
            self.text_area.tag_add("comment_tag", start_index, end_index)

        # Process strings (single, double, triple quotes)
        # Triple-quoted strings
        for match in re.finditer(r"('''.*?''')", content, re.DOTALL):
            start_index = self.text_area.index(f"1.0 + {match.start()} chars")
            end_index = self.text_area.index(f"1.0 + {match.end()} chars")
            self.text_area.tag_add("string_literal", start_index, end_index)
        for match in re.finditer(r'(""".*?""")', content, re.DOTALL):
            start_index = self.text_area.index(f"1.0 + {match.start()} chars")
            end_index = self.text_area.index(f"1.0 + {match.end()} chars")
            self.text_area.tag_add("string_literal", start_index, end_index)
        
        # Single and double quoted strings (ensure not to highlight parts of triple-quoted ones again)
        for match in re.finditer(r"""(?<!['"])(['"])(?:(?=(\\?))\2.)*?\1""", content):
             start_index = self.text_area.index(f"1.0 + {match.start()} chars")
             end_index = self.text_area.index(f"1.0 + {match.end()} chars")
             # Check if this part is already covered by a triple-quote tag
             if not self.text_area.tag_nextrange("string_literal", start_index, end_index):
                self.text_area.tag_add("string_literal", start_index, end_index)


        # Apply other patterns (keywords, numbers, brackets)
        for pattern, tag in highlight_patterns.items():
            # Skip comments and string patterns as they were handled above
            if tag in ["comment_tag", "string_literal"]:
                continue

            for match in re.finditer(pattern, content):
                start_index = self.text_area.index(f"1.0 + {match.start()} chars")
                end_index = self.text_area.index(f"1.0 + {match.end()} chars")
                # Only apply tag if it's not already part of a string or comment
                if not (self.text_area.tag_nextrange("string_literal", start_index, end_index) or
                        self.text_area.tag_nextrange("comment_tag", start_index, end_index)):
                    self.text_area.tag_add(tag, start_index, end_index)

        # Highlight function parameters (simplified heuristic)
        lines = content.split('\n')
        for i, line_content in enumerate(lines):
            line_num = i + 1
            def_match = re.search(r"def\s+[\w_]+\s*\((.*?)\):", line_content)
            if def_match:
                params_str = def_match.group(1)
                # Find parameters considering potential default values or type hints
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
                            
                        current_offset = start_char_in_line + len(param) # Update offset for next search