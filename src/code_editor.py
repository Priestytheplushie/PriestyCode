import tkinter as tk
from tkinter import scrolledtext
import re
import ast

class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B")

        self.error_console = error_console

        # --- NEW: State tracking for smart backspace ---
        self.last_action_was_autocomplete = False

        self.editor_frame = tk.Frame(self, bg="#2B2B2B")
        self.editor_frame.pack(fill="both", expand=True)

        self.linenumbers = tk.Text(self.editor_frame, width=4, padx=3, takefocus=0,
                                   border=0, background="#2B2B2B", foreground="#888888",
                                   state="disabled", wrap="none", font=("Consolas", 10))
        self.linenumbers.pack(side="left", fill="y")

        self.text_area = scrolledtext.ScrolledText(self.editor_frame, wrap="word",
                                                   bg="#2B2B2B", fg="white",
                                                   insertbackground="white",
                                                   selectbackground="#4E4E4E",
                                                   font=("Consolas", 10),
                                                   undo=True)
        self.text_area.pack(side="right", fill="both", expand=True)

        # --- Tooltip Implementation ---
        self.tooltip_window = tk.Toplevel(self.text_area)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_withdraw()
        self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left',
                                      background="#3C3C3C", foreground="white", relief='solid', borderwidth=1,
                                      wraplength=400, font=("Consolas", 9))
        self.tooltip_label.pack(ipadx=1)
        self.error_tooltip_text = ""
        # -----------------------------

        # --- NEW: Enhanced Auto-complete Window ---
        self.autocomplete_window = tk.Toplevel(self)
        self.autocomplete_window.wm_overrideredirect(True)
        self.autocomplete_window.wm_withdraw()
        self.autocomplete_listbox = tk.Listbox(self.autocomplete_window, bg="#3C3C3C", fg="white",
                                               selectbackground="#555555", exportselection=False,
                                               font=("Consolas", 10))
        self.autocomplete_listbox.pack(fill="both", expand=True)
        self.autocomplete_listbox.bind("<Return>", self._insert_completion)
        self.autocomplete_listbox.bind("<Tab>", self._insert_completion)
        self.autocomplete_listbox.bind("<Escape>", self._hide_autocomplete)
        # ----------------------------------------

        # Bindings for scrolling and text modification
        self.text_area.bind("<Configure>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<<Change>>", self._on_text_modified)
        self.text_area.bind("<MouseWheel>", self._on_mouse_scroll)
        self.text_area.bind("<Button-4>", self._on_mouse_scroll)
        self.text_area.bind("<Button-5>", self._on_mouse_scroll)
        self.text_area.bind("<Return>", self._auto_indent)
        self.text_area.bind("<Tab>", self._on_tab)

        self.text_area.bind("<BackSpace>", self._on_backspace)

        # Bindings for auto-completion
        self.text_area.bind("(", lambda event: self._auto_complete_brackets(event, '(', ')'))
        self.text_area.bind("[", lambda event: self._auto_complete_brackets(event, '[', ']'))
        self.text_area.bind("{", lambda event: self._auto_complete_brackets(event, '{', '}'))
        self.text_area.bind(".", self._hide_autocomplete) # Hide on dot
        self.text_area.bind("<FocusOut>", self._hide_autocomplete)

        # --- Tag Configuration ---
        self.text_area.tag_config("reactive_error_line", background="#DC143C")
        self.text_area.tag_config("proactive_error_line", background="#b3b300")
        
        # Individual keyword tags
        self.text_area.tag_configure("priesty_keyword", foreground="#DA70D6")
        self.text_area.tag_configure("def_keyword", foreground="#569CD6")
        self.text_area.tag_configure("class_keyword", foreground="#569CD6")
        self.text_area.tag_configure("keyword_if", foreground="#C586C0")
        self.text_area.tag_configure("keyword_else", foreground="#C586C0")
        self.text_area.tag_configure("keyword_elif", foreground="#C586C0")
        self.text_area.tag_configure("keyword_for", foreground="#C586C0")
        self.text_area.tag_configure("keyword_while", foreground="#C586C0")
        self.text_area.tag_configure("keyword_return", foreground="#C586C0")
        self.text_area.tag_configure("keyword_break", foreground="#C586C0")
        self.text_area.tag_configure("keyword_continue", foreground="#C586C0")
        self.text_area.tag_configure("keyword_yield", foreground="#C586C0")
        self.text_area.tag_configure("keyword_pass", foreground="#C586C0")
        self.text_area.tag_configure("keyword_import", foreground="#4EC9B0")
        self.text_area.tag_configure("keyword_from", foreground="#4EC9B0")
        self.text_area.tag_configure("keyword_as", foreground="#4EC9B0")
        self.text_area.tag_configure("keyword_try", foreground="#D16969")
        self.text_area.tag_configure("keyword_except", foreground="#D16969")
        self.text_area.tag_configure("keyword_finally", foreground="#D16969")
        self.text_area.tag_configure("keyword_raise", foreground="#D16969")
        self.text_area.tag_configure("keyword_assert", foreground="#D16969")
        self.text_area.tag_configure("keyword_True", foreground="#569CD6")
        self.text_area.tag_configure("keyword_False", foreground="#569CD6")
        self.text_area.tag_configure("keyword_None", foreground="#569CD6")
        self.text_area.tag_configure("keyword_and", foreground="#DCDCAA")
        self.text_area.tag_configure("keyword_or", foreground="#DCDCAA")
        self.text_area.tag_configure("keyword_not", foreground="#DCDCAA")
        self.text_area.tag_configure("keyword_in", foreground="#DCDCAA")
        self.text_area.tag_configure("keyword_is", foreground="#DCDCAA")
        self.text_area.tag_configure("keyword_del", foreground="#B8D7A3")
        self.text_area.tag_configure("keyword_global", foreground="#B8D7A3")
        self.text_area.tag_configure("keyword_nonlocal", foreground="#B8D7A3")
        self.text_area.tag_configure("keyword_async", foreground="#FFD700")
        self.text_area.tag_configure("keyword_await", foreground="#FFD700")
        self.text_area.tag_configure("keyword_with", foreground="#CE9178")
        self.text_area.tag_configure("keyword_lambda", foreground="#CE9178")

        self.text_area.tag_config("string_literal", foreground="#A3C78B")
        self.text_area.tag_config("number_literal", foreground="#B5CEA8")
        self.text_area.tag_config("comment_tag", foreground="#6A9955")
        self.text_area.tag_config("function_param", foreground="#9CDCFE") # This tag needs more specific application
        self.text_area.tag_config("bracket_tag", foreground="#FFD700")
        self.text_area.tag_config("builtin_function", foreground="#4EC9B0")
        
        # New tags for specific standard methods (examples)
        self.text_area.tag_configure("method_append", foreground="#FFC66D")
        self.text_area.tag_configure("method_strip", foreground="#FFC66D")
        self.text_area.tag_configure("method_keys", foreground="#FFC66D")
        self.text_area.tag_configure("method_values", foreground="#FFC66D")
        self.text_area.tag_configure("method_items", foreground="#FFC66D")
        self.text_area.tag_configure("method_get", foreground="#FFC66D")
        self.text_area.tag_configure("method_lower", foreground="#FFC66D")
        self.text_area.tag_configure("method_upper", foreground="#FFC66D")
        self.text_area.tag_configure("method_split", foreground="#FFC66D")
        self.text_area.tag_configure("method_join", foreground="#FFC66D")

        # Dunder methods
        self.text_area.tag_configure("dunder_init", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_str", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_repr", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_len", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_add", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_sub", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_mul", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_truediv", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_eq", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_ne", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_lt", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_le", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_gt", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_ge", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_call", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_getitem", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_setitem", foreground="#DA70D6")
        self.text_area.tag_configure("dunder_delitem", foreground="#DA70D6")


        # --- Tooltip Bindings ---
        tag_tooltips = {
            "priesty_keyword": "A special keyword in PriestyCode, often used for core functionalities.",
            "def_keyword": "The 'def' keyword is used to define functions. Functions are blocks of organized, reusable code that perform a single, related action.",
            "class_keyword": "The 'class' keyword is used to define classes. Classes serve as blueprints for creating objects, providing initial values for state (member variables or attributes), and implementations of behavior (member functions or methods).",
            
            "keyword_if": "The 'if' keyword executes a block of code if a specified condition is true.",
            "keyword_else": "The 'else' keyword executes a block of code if the preceding 'if' condition is false.",
            "keyword_elif": "The 'elif' (else if) keyword checks another condition if the previous 'if' or 'elif' conditions were false.",
            "keyword_for": "The 'for' keyword is used for iterating over a sequence (such as a list, tuple, dictionary, set, or string).",
            "keyword_while": "The 'while' keyword repeats a block of code as long as a certain condition is true.",
            "keyword_return": "The 'return' keyword exits a function and optionally passes back a value.",
            "keyword_break": "The 'break' keyword terminates the current loop (for or while) and resumes execution at the next statement.",
            "keyword_continue": "The 'continue' keyword skips the rest of the current iteration of a loop and continues to the next iteration.",
            "keyword_yield": "The 'yield' keyword is used in generator functions to return an iterator.",
            "keyword_pass": "The 'pass' keyword is a null operation; nothing happens when it executes. It can be used as a placeholder where a statement is syntactically required but you don't want any command or code to execute.",

            "keyword_import": "The 'import' keyword is used to import modules or packages.",
            "keyword_from": "The 'from' keyword is used in conjunction with 'import' to import specific attributes or functions from a module instead of the entire module.",
            "keyword_as": "The 'as' keyword is used to create an alias (an alternative name) when importing a module or attribute, making it easier to refer to.",

            "keyword_try": "The 'try' keyword defines a block of code to be tested for errors while it is being executed.",
            "keyword_except": "The 'except' keyword lets you handle specific errors that occur within the 'try' block. You can define what kind of error to catch.",
            "keyword_finally": "The 'finally' keyword ensures that the code within its block is executed regardless of whether an exception occurred or was handled.",
            "keyword_raise": "The 'raise' keyword is used to trigger an exception or error manually.",
            "keyword_assert": "The 'assert' keyword checks if a condition is true. If the condition is false, it raises an AssertionError, typically used for debugging.",

            "keyword_True": "Represents the boolean value true.",
            "keyword_False": "Represents the boolean value false.",
            "keyword_None": "Represents the absence of a value or a null value.",

            "keyword_and": "Logical AND operator. Returns True if both operands are true.",
            "keyword_or": "Logical OR operator. Returns True if at least one of the operands is true.",
            "keyword_not": "Logical NOT operator. Reverses the boolean result of its operand.",
            "keyword_in": "Membership operator; tests if a sequence (like a substring or item) is present in an object (like a string, list, or tuple).",
            "keyword_is": "Identity operator; tests if two variables refer to the exact same object in memory.",

            "keyword_del": "The 'del' keyword is used to delete objects, elements from a list, or slices from a list.",
            "keyword_global": "The 'global' keyword declares a variable as global, allowing it to be modified inside a function even if it was defined outside.",
            "keyword_nonlocal": "The 'nonlocal' keyword declares a variable as nonlocal, meaning it refers to a variable in an enclosing but non-global scope, allowing it to be modified.",

            "keyword_async": "The 'async' keyword is used to declare an asynchronous function, which can await other asynchronous operations.",
            "keyword_await": "The 'await' keyword is used to pause the execution of an async function until a specified awaitable (like a coroutine or a Future) completes.",

            "keyword_with": "The 'with' keyword is used to simplify exception handling by ensuring that certain operations (like file handling) are properly set up and torn down.",
            "keyword_lambda": "The 'lambda' keyword is used to create small, anonymous functions. Lambda functions can take any number of arguments but can only have one expression.",

            "string_literal": "A sequence of characters, representing text. Enclosed in single, double, or triple quotes.",
            "number_literal": "A numeric value, which can be an integer (e.g., 123) or a floating-point number (e.g., 3.14).",
            "comment_tag": "A line or block of text that is ignored by the interpreter, used for explanations or notes.",
            "function_param": "A parameter of a function, serving as a placeholder for arguments passed when the function is called.",
            "bracket_tag": "Parentheses '()', square brackets '[]', or curly braces '{}'. Used for function calls, indexing, or defining collections.",
            "builtin_function": "A function that is pre-defined in Python and always available for use without explicit imports.",
            
            # Specific standard method tooltips
            "method_append": "List.append(item): Adds an item to the end of the list.",
            "method_strip": "String.strip([chars]): Returns a copy of the string with leading and trailing whitespace (or specified characters) removed.",
            "method_keys": "Dictionary.keys(): Returns a new view of the dictionary's keys.",
            "method_values": "Dictionary.values(): Returns a new view of the dictionary's values.",
            "method_items": "Dictionary.items(): Returns a new view of the dictionary's items (key-value pairs).",
            "method_get": "Dictionary.get(key, default): Returns the value for key if key is in the dictionary, else default. If default is not given, it defaults to None.",
            "method_lower": "String.lower(): Returns a copy of the string with all the cased characters converted to lowercase.",
            "method_upper": "String.upper(): Returns a copy of the string with all the cased characters converted to uppercase.",
            "method_split": "String.split([sep[, maxsplit]]): Returns a list of the words in the string, using sep as the delimiter string.",
            "method_join": "String.join(iterable): Returns a string which is the concatenation of the strings in iterable. The string on which the method is called is the separator.",

            # Dunder method tooltips
            "dunder_init": "__init__(self, ...): The constructor method, automatically called when a new object instance is created. Used to initialize the object's attributes.",
            "dunder_str": "__str__(self): Returns a human-readable, informal string representation of an object. Called by functions like print() and str().",
            "dunder_repr": "__repr__(self): Returns an 'official' string representation of an object, often used for debugging. It should ideally be unambiguous and, if possible, allow the object to be recreated from its string representation.",
            "dunder_len": "__len__(self): Returns the length of the object (e.g., number of items in a list, characters in a string). Called by len().",
            "dunder_add": "__add__(self, other): Implements the addition operator (+). Defines the behavior when two objects are added.",
            "dunder_sub": "__sub__(self, other): Implements the subtraction operator (-). Defines the behavior when one object is subtracted from another.",
            "dunder_mul": "__mul__(self, other): Implements the multiplication operator (*). Defines the behavior when two objects are multiplied.",
            "dunder_truediv": "__truediv__(self, other): Implements the true division operator (/). Defines the behavior for floating-point division.",
            "dunder_eq": "__eq__(self, other): Implements the equality comparison operator (==). Defines when two objects are considered equal.",
            "dunder_ne": "__ne__(self, other): Implements the inequality comparison operator (!=). Defines when two objects are considered not equal.",
            "dunder_lt": "__lt__(self, other): Implements the less than operator (<).",
            "dunder_le": "__le__(self, other): Implements the less than or equal to operator (<=).",
            "dunder_gt": "__gt__(self, other): Implements the greater than operator (>).",
            "dunder_ge": "__ge__(self, other): Implements the greater than or equal to operator (>=).",
            "dunder_call": "__call__(self, *args, **kwargs): Makes an instance of the class callable like a function. Defines the behavior when the object is called directly.",
            "dunder_getitem": "__getitem__(self, key): Implements behavior for accessing an item using square bracket notation (e.g., obj[key]). Used for indexing.",
            "dunder_setitem": "__setitem__(self, key, value): Implements behavior for assigning a value to an item using square bracket notation (e.g., obj[key] = value).",
            "dunder_delitem": "__delitem__(self, key): Implements behavior for deleting an item using square bracket notation (e.g., del obj[key])."
        }

        for tag, text in tag_tooltips.items():
            self.text_area.tag_bind(tag, "<Enter>", lambda e, t=text: self._show_tooltip(e, t))
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

        self.text_area.tag_bind("reactive_error_line", "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text))
        self.text_area.tag_bind("reactive_error_line", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("proactive_error_line", "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text))
        self.text_area.tag_bind("proactive_error_line", "<Leave>", self._hide_tooltip)
        # -----------------------------

        self.text_area.edit_modified(False)
        self.apply_syntax_highlighting()

    def _on_backspace(self, event):
        """
        If the last action was an auto-completion, undo it.
        Otherwise, perform a normal backspace.
        """
        if self.last_action_was_autocomplete:
            self.last_action_was_autocomplete = False
            self.text_area.edit_undo()
            self._hide_autocomplete()
            return "break"

    def _on_tab(self, event):
        """Inserts 4 spaces for a tab press."""
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    ")
        self.last_action_was_autocomplete = True
        return "break"

    def _update_autocomplete(self, event=None):
        """
        Shows a listbox with word suggestions based on the current text.
        """
        current_word = self.text_area.get("insert-1c wordstart", "insert")
        if len(current_word) < 2:
            self._hide_autocomplete()
            return

        all_text = self.text_area.get("1.0", tk.END)
        all_words = set(re.findall(r'\b\w+\b', all_text))

        matches = [word for word in all_words if word.startswith(current_word) and word != current_word]

        if not matches:
            self._hide_autocomplete()
            return

        self.autocomplete_listbox.delete(0, tk.END)
        for match in sorted(matches, key=len):
            self.autocomplete_listbox.insert(tk.END, match)

        x, y, _, h = self.text_area.bbox(tk.INSERT) # type: ignore
        x += self.text_area.winfo_rootx()
        y += self.text_area.winfo_rooty() + h

        self.autocomplete_window.geometry(f"150x100+{x}+{y}")
        self.autocomplete_window.wm_deiconify()
        self.autocomplete_window.lift()
        self.autocomplete_listbox.focus_set()
        self.autocomplete_listbox.selection_set(0)
        self.autocomplete_listbox.activate(0)

    def _insert_completion(self, event):
        """Inserts the selected completion into the text area."""
        selected_index = self.autocomplete_listbox.curselection()
        if not selected_index:
            self._hide_autocomplete()
            return "break"

        completion = self.autocomplete_listbox.get(selected_index[0])
        current_word_start = self.text_area.index("insert-1c wordstart")
        self.text_area.delete(current_word_start, "insert")
        self.text_area.insert(current_word_start, completion)
        self._hide_autocomplete()
        return "break"

    def _hide_autocomplete(self, event=None):
        self.autocomplete_window.wm_withdraw()
        self.text_area.focus_set()

    def _show_tooltip(self, event, text):
        if not text:
            return
        x = self.winfo_rootx() + self.text_area.winfo_x() + event.x + 20
        y = self.winfo_rooty() + self.text_area.winfo_y() + event.y + 20
        self.tooltip_label.config(text=text)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.wm_deiconify()

    def _hide_tooltip(self, event=None):
        self.tooltip_window.wm_withdraw()

    def update_line_numbers(self, event=None):
        self.linenumbers.config(state="normal")
        self.linenumbers.delete("1.0", tk.END)
        num_lines = self.text_area.index("end-1c").split('.')[0]
        line_numbers_text = "\n".join(str(i) for i in range(1, int(num_lines) + 1))
        self.linenumbers.insert("1.0", line_numbers_text)
        self.linenumbers.config(state="disabled")
        first_visible_line = self.text_area.yview()[0]
        self.linenumbers.yview_moveto(first_visible_line)

    def _on_content_changed(self, event=None):
        """A centralized method to run all updates when content changes."""
        self.last_action_was_autocomplete = False
        self.update_line_numbers()
        self.apply_syntax_highlighting()
        self._proactive_syntax_check()

    def _on_key_release(self, event=None):
        """Triggers updates on key release for immediate feedback."""
        self.last_action_was_autocomplete = False

        if event and event.char and event.char.isalnum() or event.keysym == '_':  # type: ignore
            self._update_autocomplete()
        elif event and event.keysym not in ('Up', 'Down', 'Left', 'Right'):
            self._hide_autocomplete()

        if event and event.keysym not in ("Return", "(", "[", "{", "BackSpace", "Delete", "Tab"):
             self._on_content_changed()

    def _on_text_modified(self, event=None):
        """Triggers updates for undoable actions like paste, cut, undo, redo."""
        if self.text_area.edit_modified():
            self.last_action_was_autocomplete = False
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self.linenumbers.yview_scroll(-1 * (event.delta // 120), "units")
        self.text_area.yview_scroll(-1 * (event.delta // 120), "units")
        return "break"

    def _auto_complete_brackets(self, event, open_char, close_char):
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, open_char + close_char)
        self.text_area.mark_set(tk.INSERT, "insert-1c")
        self.last_action_was_autocomplete = True
        self._on_content_changed()
        return "break"

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
            indent_to_insert += "    "
        self.text_area.insert(tk.INSERT, indent_to_insert)
        self.last_action_was_autocomplete = True
        self._on_content_changed()
        return "break"

    def highlight_syntax_error(self, line_number, error_message):
        self.clear_error_highlight()
        self.error_tooltip_text = error_message
        start = f"{line_number}.0"
        end = f"{line_number}.end"
        self.text_area.tag_add("proactive_error_line", start, end)

    def highlight_runtime_error(self, line_number, error_message):
        self.clear_error_highlight()
        self.error_tooltip_text = error_message
        start = f"{line_number}.0"
        end = f"{line_number}.end"
        self.text_area.tag_add("reactive_error_line", start, end)

    def clear_error_highlight(self):
        self.text_area.tag_remove("reactive_error_line", "1.0", tk.END)
        self.text_area.tag_remove("proactive_error_line", "1.0", tk.END)
        self.error_tooltip_text = ""

    def apply_syntax_highlighting(self):
        for tag in self.text_area.tag_names():
            if tag not in ("sel", "insert", "current", "reactive_error_line", "proactive_error_line"):
                self.text_area.tag_remove(tag, "1.0", tk.END)

        content = self.text_area.get("1.0", tk.END)

        builtin_functions = [
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray',
            'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex',
            'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec',
            'filter', 'float', 'format', 'frozenset', 'getattr', 'globals',
            'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance',
            'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max',
            'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow',
            'print', 'property', 'range', 'repr', 'reversed', 'round', 'set',
            'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
            'tuple', 'type', 'vars', 'zip'
        ]

        # Individual keyword mappings for precise tagging and tooltips
        individual_keywords = {
            r"\bif\b": "keyword_if",
            r"\belse\b": "keyword_else",
            r"\belif\b": "keyword_elif",
            r"\bfor\b": "keyword_for",
            r"\bwhile\b": "keyword_while",
            r"\breturn\b": "keyword_return",
            r"\bbreak\b": "keyword_break",
            r"\bcontinue\b": "keyword_continue",
            r"\byield\b": "keyword_yield",
            r"\bpass\b": "keyword_pass",
            r"\bimport\b": "keyword_import",
            r"\bfrom\b": "keyword_from",
            r"\bas\b": "keyword_as",
            r"\btry\b": "keyword_try",
            r"\bexcept\b": "keyword_except",
            r"\bfinally\b": "keyword_finally",
            r"\braise\b": "keyword_raise",
            r"\bassert\b": "keyword_assert",
            r"\bTrue\b": "keyword_True",
            r"\bFalse\b": "keyword_False",
            r"\bNone\b": "keyword_None",
            r"\band\b": "keyword_and",
            r"\bor\b": "keyword_or",
            r"\bnot\b": "keyword_not",
            r"\bin\b": "keyword_in",
            r"\bis\b": "keyword_is",
            r"\bdel\b": "keyword_del",
            r"\bglobal\b": "keyword_global",
            r"\bnonlocal\b": "keyword_nonlocal",
            r"\basync\b": "keyword_async",
            r"\bawait\b": "keyword_await",
            r"\bwith\b": "keyword_with",
            r"\blambda\b": "keyword_lambda",
        }

        # Specific standard methods for individual highlighting and tooltips
        specific_standard_methods_patterns = {
            r'\.append\b': 'method_append',
            r'\.strip\b': 'method_strip',
            r'\.keys\b': 'method_keys',
            r'\.values\b': 'method_values',
            r'\.items\b': 'method_items',
            r'\.get\b': 'method_get',
            r'\.lower\b': 'method_lower',
            r'\.upper\b': 'method_upper',
            r'\.split\b': 'method_split',
            r'\.join\b': 'method_join',
        }
        
        # Dunder methods
        dunder_method_patterns = {
            r'__init__\b': 'dunder_init',
            r'__str__\b': 'dunder_str',
            r'__repr__\b': 'dunder_repr',
            r'__len__\b': 'dunder_len',
            r'__add__\b': 'dunder_add',
            r'__sub__\b': 'dunder_sub',
            r'__mul__\b': 'dunder_mul',
            r'__truediv__\b': 'dunder_truediv',
            r'__eq__\b': 'dunder_eq',
            r'__ne__\b': 'dunder_ne',
            r'__lt__\b': 'dunder_lt',
            r'__le__\b': 'dunder_le',
            r'__gt__\b': 'dunder_gt',
            r'__ge__\b': 'dunder_ge',
            r'__call__\b': 'dunder_call',
            r'__getitem__\b': 'dunder_getitem',
            r'__setitem__\b': 'dunder_setitem',
            r'__delitem__\b': 'dunder_delitem'
        }


        # Combine all patterns
        highlight_patterns = {
            r"\bPriesty\b": "priesty_keyword",
            r"\bdef\b": "def_keyword",
            r"\bclass\b": "class_keyword",
            r"\b(" + "|".join(builtin_functions) + r")\b": "builtin_function",
            r"[(){}[\]]": "bracket_tag",
            **individual_keywords, # Merge individual keyword patterns
            **specific_standard_methods_patterns, # Merge specific method patterns
            **dunder_method_patterns # Merge dunder method patterns
        }

        # Apply comments first to prevent other tags from overriding
        for match in re.finditer(r"(#.*)", content):
            self._apply_tag("comment_tag", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        # Apply triple-quoted string literals
        for pattern in [r"'''.*?'''", r'""".*?"""']:
            for match in re.finditer(pattern, content, re.DOTALL):
                self._apply_tag("string_literal", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        # Apply single/double quoted string literals, avoiding re-tagging triple quotes
        for match in re.finditer(r"""(?<!['"])(['"])(?:(?=(\\?))\2.)*?\1""", content):
             start_index, end_index = (f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
             if not self._is_inside_tag_by_index(start_index, end_index, "string_literal"): # Check if already part of a triple-quoted string
                self._apply_tag("string_literal", start_index, end_index)

        # Apply other highlight patterns
        for pattern, tag in highlight_patterns.items():
            for match in re.finditer(pattern, content):
                start, end = (f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
                # Ensure we don't tag inside comments or strings
                if not (self._is_inside_tag_by_index(start, end, "string_literal") or self._is_inside_tag_by_index(start, end, "comment_tag")):
                    self._apply_tag(tag, start, end)

        # Apply number literals
        for match in re.finditer(r'\b\d+(\.\d*)?([eE][+-]?\d+)?\b', content):
            start, end = (f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
            if not (self._is_inside_tag_by_index(start, end, "string_literal") or self._is_inside_tag_by_index(start, end, "comment_tag")):
                self._apply_tag("number_literal", start, end)


    def _apply_tag(self, tag_name, start_index, end_index):
        self.text_area.tag_add(tag_name, start_index, end_index)

    def _is_inside_tag_by_index(self, start_index, end_index, tag_name):
        return bool(self.text_area.tag_nextrange(tag_name, start_index, end_index))

    def _proactive_syntax_check(self):
        code_content = self.text_area.get("1.0", tk.END)

        self.clear_error_highlight()

        if not code_content.strip():
            if self.error_console:
                self.error_console.clear()
            return

        try:
            ast.parse(code_content)
            if self.error_console:
                self.error_console.clear()

        except SyntaxError as e:
            cursor_line = int(self.text_area.index(tk.INSERT).split('.')[0])

            if e.lineno == cursor_line:
                return

            line_num = e.lineno or 1
            message = e.msg

            content_lines = code_content.splitlines()
            if line_num > len(content_lines):
                line_num = len(content_lines) if content_lines else 1

            tooltip_text = f"Syntax Error: {message}"
            self.highlight_syntax_error(line_num, tooltip_text)

            if self.error_console:
                console_text = f"Syntax Error (Line {line_num}): {message}\n"
                self.error_console.format_error_output(console_text, f"Full Syntax Error Details:\n{e}")
        except Exception as e:
            self.clear_error_highlight()
            if self.error_console:
                self.error_console.format_error_output(f"Proactive Check Error: {type(e).__name__}: {e}", f"Full Error Details:\n{e}")