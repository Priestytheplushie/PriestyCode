import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import re
import ast

class AutocompleteManager:
    def __init__(self, editor_instance):
        self.editor = editor_instance
        self.text_area = editor_instance.text_area

        self.window = tk.Toplevel(self.text_area)
        self.window.wm_overrideredirect(True)
        self.window.withdraw()

        main_frame = tk.Frame(self.window, bg="#555555", borderwidth=1, relief="solid")
        main_frame.pack(fill="both", expand=True)

        self.style = ttk.Style()
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL, style='Autocomplete.TPanedwindow')
        paned_window.pack(fill="both", expand=True)

        list_frame = tk.Frame(paned_window, bg="#3C3C3C")
        self.tree = ttk.Treeview(list_frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        paned_window.add(list_frame, weight=2)

        preview_frame = tk.Frame(paned_window, bg="#2B2B2B")
        self.preview_text = tk.Text(preview_frame, wrap="word", bg="#2B2B2B", fg="white",
                                    font=("Consolas", 9), state="disabled", borderwidth=0,
                                    highlightthickness=0)
        self.preview_text.pack(fill="both", expand=True, padx=5, pady=5)
        paned_window.add(preview_frame, weight=3)
        
        self.completions = []
        self._configure_treeview()

    def _configure_treeview(self):
        self.style.configure('Autocomplete.TPanedwindow', sashwidth=2, background="#3C3C3C")
        
        self.style.layout("Custom.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        self.style.configure("Custom.Treeview", background="#3C3C3C", foreground="white",
                             fieldbackground="#3C3C3C", borderwidth=0, rowheight=22)
        self.style.map('Custom.Treeview', background=[('selected', '#555555')])
        self.tree.config(style="Custom.Treeview")
        
        self.tree.tag_configure('variable', foreground='#9CDCFE')
        self.tree.tag_configure('snippet', foreground='#CE9178')
        self.tree.tag_configure('keyword', foreground='#C586C0')
        self.tree.tag_configure('function', foreground='#DCDCAA')

        self.tree.bind('<<TreeviewSelect>>', self.update_preview)
        self.tree.bind('<Return>', self.confirm_selection)
        self.tree.bind('<Tab>', self.confirm_selection)
        self.tree.bind('<Double-1>', self.confirm_selection)

    def show(self, completions, bbox):
        if not completions:
            self.hide()
            return
        
        self.completions = completions
        self.tree.delete(*self.tree.get_children())

        for i, item in enumerate(completions):
            type_char = {
                'variable': '[v]', 'snippet': '[s]',
                'keyword': '[k]', 'function': '[f]'
            }.get(item['type'], '[?]')
            
            display_text = f" {type_char} {item['label']}"
            self.tree.insert('', 'end', iid=i, text=display_text, tags=(item['type'],))

        num_items = len(completions)
        new_height = min(num_items, 10) * 22 + 6

        if not self.window.winfo_viewable():
            x, y, _, h = bbox
            x += self.text_area.winfo_rootx()
            y += self.text_area.winfo_rooty() + h
            self.window.geometry(f"550x{new_height}+{x}+{y}")
            self.window.deiconify()
            self.window.lift()
        else:
            current_x = self.window.winfo_x()
            current_y = self.window.winfo_y()
            self.window.geometry(f"550x{new_height}+{current_x}+{current_y}")
        
        if self.tree.get_children():
            self.tree.selection_set('0')
            self.tree.focus('0')

    def hide(self):
        self.window.withdraw()

    def is_visible(self):
        return self.window.winfo_viewable()

    def update_preview(self, event=None):
        selected_ids = self.tree.selection()
        if not selected_ids:
            self.preview_text.config(state="normal")
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.config(state="disabled")
            return
        
        selected_index = int(selected_ids[0])
        item = self.completions[selected_index]
        
        preview_content = item.get('detail', '') + "\n\n" + item.get('insert', item['label'])
        
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", preview_content)
        self.preview_text.config(state="disabled")

    def confirm_selection(self, event=None):
        if not self.is_visible(): return

        selected_ids = self.tree.selection()
        if not selected_ids: return 'break'
            
        selected_index = int(selected_ids[0])
        item = self.completions[selected_index]
        self.editor.perform_autocomplete(item['insert'])
        self.hide()
        return 'break'

    def navigate(self, direction):
        if not self.is_visible(): return
        
        current_focus = self.tree.focus()
        if not current_focus: return
        
        next_item = self.tree.next(current_focus) if direction > 0 else self.tree.prev(current_focus)
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
        return 'break'

class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B")

        self.error_console = error_console
        self.last_action_was_autocomplete = False
        self.autocomplete_active = True
        self.autocomplete_dismissed_word = None

        self.editor_frame = tk.Frame(self, bg="#2B2B2B")
        self.editor_frame.pack(fill="both", expand=True)

        self.linenumbers = tk.Text(self.editor_frame, width=4, padx=3, takefocus=0, border=0, background="#2B2B2B", foreground="#888888", state="disabled", wrap="none", font=("Consolas", 10))
        self.linenumbers.pack(side="left", fill="y")

        self.text_area = scrolledtext.ScrolledText(self.editor_frame, wrap="word", bg="#2B2B2B", fg="white", insertbackground="white", selectbackground="#4E4E4E", font=("Consolas", 10), undo=True)
        self.text_area.pack(side="right", fill="both", expand=True)

        self.tooltip_window = tk.Toplevel(self.text_area)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_withdraw()
        self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left', background="#3C3C3C", foreground="white", relief='solid', borderwidth=1, wraplength=400, font=("Consolas", 9))
        self.tooltip_label.pack(ipadx=1)
        self.error_tooltip_text = ""
        
        self.autocomplete_manager = AutocompleteManager(self)
        self._configure_autocomplete_data()
        self._configure_tags_and_tooltips()

        self.text_area.bind("<Configure>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<<Change>>", self._on_text_modified)
        self.text_area.bind("<MouseWheel>", self._on_mouse_scroll)
        self.text_area.bind("<Button-4>", self._on_mouse_scroll)
        self.text_area.bind("<Button-5>", self._on_mouse_scroll)
        self.text_area.bind("<Button-1>", self._on_click)
        self.text_area.bind("<Return>", self._on_return)
        self.text_area.bind("<Tab>", self._on_tab)
        self.text_area.bind("<BackSpace>", self._on_backspace)
        self.text_area.bind("(", lambda event: self._auto_complete_brackets(event, '(', ')'))
        self.text_area.bind("[", lambda event: self._auto_complete_brackets(event, '[', ']'))
        self.text_area.bind("{", lambda event: self._auto_complete_brackets(event, '{', '}'))
        self.text_area.bind(".", self._on_dot)
        self.text_area.bind("<Escape>", self._on_escape)
        self.text_area.bind("<Up>", self._on_arrow_up)
        self.text_area.bind("<Down>", self._on_arrow_down)

        self.text_area.edit_modified(False)
        self.apply_syntax_highlighting()

    def _on_escape(self, event):
        if self.autocomplete_manager.is_visible():
            self.autocomplete_manager.hide()
            self.autocomplete_dismissed_word = self.text_area.get("insert-1c wordstart", "insert")
            return "break"
        return None

    def _on_arrow_up(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.navigate(-1)
        return None

    def _on_arrow_down(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.navigate(1)
        return None

    def _on_click(self, event):
        self.autocomplete_manager.hide()
        self.autocomplete_dismissed_word = None
    
    def _on_dot(self, event):
        self.autocomplete_manager.hide()
        self.autocomplete_dismissed_word = None

    def _configure_autocomplete_data(self):
        self.snippets = [
            {'label': 'def (function)', 'match': 'def', 'type': 'snippet', 'detail': 'Define a new function.', 'insert': 'def function_name(params):\n    pass'},
            {'label': 'def (constructor)', 'match': 'def', 'type': 'snippet', 'detail': 'Define the constructor for a class.', 'insert': 'def __init__(self):\n    pass'},
            {'label': 'for', 'match': 'for', 'type': 'snippet', 'detail': 'Create a for loop.', 'insert': 'for item in iterable:\n    pass'},
            {'label': 'if', 'match': 'if', 'type': 'snippet', 'detail': 'Create an if statement.', 'insert': 'if condition:\n    pass'},
            {'label': 'if/else', 'match': 'if', 'type': 'snippet', 'detail': 'Create an if/else block.', 'insert': 'if condition:\n    pass\nelse:\n    pass'},
            {'label': 'class', 'match': 'class', 'type': 'snippet', 'detail': 'Create a new class.', 'insert': 'class NewClass:\n    def __init__(self):\n        pass'},
            {'label': 'try', 'match': 'try', 'type': 'snippet', 'detail': 'Create a try/except block.', 'insert': 'try:\n    pass\nexcept Exception as e:\n    print(f"An error occurred: {e}")'},
            {'label': 'with (file)', 'match': 'with', 'type': 'snippet', 'detail': 'Open a file safely.', 'insert': "with open('file.txt', 'r') as f:\n    pass"},
            {'label': 'main', 'match': 'main', 'type': 'snippet', 'detail': 'Standard main execution block.', 'insert': 'if __name__ == "__main__":\n    pass'},
            {'label': '__str__', 'match': '__str__', 'type': 'snippet', 'detail': 'Define the string representation of an object.', 'insert': 'def __str__(self):\n    return super().__str__()'},
        ]
        self.builtin_list = ['abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip']
        self.keyword_list = ['and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield']

    def _configure_tags_and_tooltips(self):
        tag_configs = {
            "reactive_error_line": {"background": "#DC143C"},
            "proactive_error_line": {"background": "#b3b300"},
            "priesty_keyword": {"foreground": "#DA70D6"}, "def_keyword": {"foreground": "#569CD6"},
            "class_keyword": {"foreground": "#569CD6"}, "keyword_if": {"foreground": "#C586C0"},
            "keyword_else": {"foreground": "#C586C0"}, "keyword_elif": {"foreground": "#C586C0"},
            "keyword_for": {"foreground": "#C586C0"}, "keyword_while": {"foreground": "#C586C0"},
            "keyword_return": {"foreground": "#C586C0"}, "keyword_break": {"foreground": "#C586C0"},
            "keyword_continue": {"foreground": "#C586C0"}, "keyword_yield": {"foreground": "#C586C0"},
            "keyword_pass": {"foreground": "#C586C0"}, "keyword_import": {"foreground": "#4EC9B0"},
            "keyword_from": {"foreground": "#4EC9B0"}, "keyword_as": {"foreground": "#4EC9B0"},
            "keyword_try": {"foreground": "#D16969"}, "keyword_except": {"foreground": "#D16969"},
            "keyword_finally": {"foreground": "#D16969"}, "keyword_raise": {"foreground": "#D16969"},
            "keyword_assert": {"foreground": "#D16969"}, "keyword_True": {"foreground": "#569CD6"},
            "keyword_False": {"foreground": "#569CD6"}, "keyword_None": {"foreground": "#569CD6"},
            "keyword_and": {"foreground": "#DCDCAA"}, "keyword_or": {"foreground": "#DCDCAA"},
            "keyword_not": {"foreground": "#DCDCAA"}, "keyword_in": {"foreground": "#DCDCAA"},
            "keyword_is": {"foreground": "#DCDCAA"}, "keyword_del": {"foreground": "#B8D7A3"},
            "keyword_global": {"foreground": "#B8D7A3"}, "keyword_nonlocal": {"foreground": "#B8D7A3"},
            "keyword_async": {"foreground": "#FFD700"}, "keyword_await": {"foreground": "#FFD700"},
            "keyword_with": {"foreground": "#CE9178"}, "keyword_lambda": {"foreground": "#CE9178"},
            "string_literal": {"foreground": "#A3C78B"}, "number_literal": {"foreground": "#B5CEA8"},
            "comment_tag": {"foreground": "#6A9955"}, "function_param": {"foreground": "#9CDCFE"},
            "bracket_tag": {"foreground": "#FFD700"}, "builtin_function": {"foreground": "#4EC9B0"},
            "dunder_init": {"foreground": "#DA70D6"}
        }
        for tag, config in tag_configs.items():
            self.text_area.tag_configure(tag, **config)

        self.builtin_tooltips = {
            'print': 'print(*objects, sep=\' \', end=\'\\n\')\nPrints objects to the text stream, separated by sep.',
            'len': 'len(obj)\nReturns the number of items in an object.',
            'str': 'str(object=\'\') -> str\nReturns a string version of an object.',
            'int': 'int(x, base=10) -> integer\nConverts a number or string to an integer.',
            'float': 'float(x) -> float\nConverts a number or string to a float.',
            'list': 'list(iterable) -> new list\nCreates a new list.', 'dict': 'dict(**kwarg) -> new dictionary\nCreates a new dictionary.',
            'set': 'set(iterable) -> new set\nCreates a new set object.', 'tuple': 'tuple(iterable) -> new tuple\nCreates a new tuple object.',
            'range': 'range(start, stop[, step])\nReturns an immutable sequence of numbers.',
            'input': 'input(prompt=None) -> string\nReads a line from input, converts it to a string.',
            'open': 'open(file, mode=\'r\', ...) -> file object\nOpens a file and returns a file object.',
            'sum': 'sum(iterable, /, start=0)\nSums the items of an iterable.', 'max': 'max(iterable, *[, key, default])\nReturns the largest item in an iterable.',
            'min': 'min(iterable, *[, key, default])\nReturns the smallest item in an iterable.', 'abs': 'abs(x)\nReturns the absolute value of a number.',
            'round': 'round(number[, ndigits])\nRounds a number to a given precision.', 'sorted': 'sorted(iterable, *, key=None, reverse=False)\nReturns a new sorted list.',
            'any': 'any(iterable) -> bool\nReturns True if any element of the iterable is true.', 'all': 'all(iterable) -> bool\nReturns True if all elements of the iterable are true.',
            'zip': 'zip(*iterables)\nReturns an iterator of tuples.', 'enumerate': 'enumerate(iterable, start=0)\nReturns an enumerate object.',
            'map': 'map(function, iterable, ...)\nApplies function to every item of iterable.', 'filter': 'filter(function, iterable)\nConstructs an iterator from elements for which function returns true.'
        }
        self.dunder_tooltips = {'__init__': '__init__(self, ...)\nThe constructor for a class. Called when an object is instantiated.'}

        tag_tooltips = {
            "priesty_keyword": "A special keyword in PriestyCode, often used for core functionalities.", "def_keyword": "The 'def' keyword is used to define functions.", "class_keyword": "The 'class' keyword is used to define classes.", "keyword_if": "The 'if' keyword executes a block of code if a specified condition is true.", "keyword_else": "The 'else' keyword executes a block of code if the preceding 'if' condition is false.", "keyword_elif": "The 'elif' (else if) keyword checks another condition if the previous conditions were false.", "keyword_for": "The 'for' keyword is used for iterating over a sequence.", "keyword_while": "The 'while' keyword repeats a block of code as long as a condition is true.", "keyword_return": "The 'return' keyword exits a function and optionally passes back a value.", "keyword_break": "The 'break' keyword terminates the current loop.", "keyword_continue": "The 'continue' keyword skips the rest of the current iteration of a loop.", "keyword_yield": "The 'yield' keyword is used in generator functions to return an iterator.", "keyword_pass": "The 'pass' keyword is a null operation; nothing happens when it executes.", "keyword_import": "The 'import' keyword is used to import modules.", "keyword_from": "The 'from' keyword is used with 'import' to import specific attributes or functions.", "keyword_as": "The 'as' keyword is used to create an alias for a module.", "keyword_try": "The 'try' keyword defines a block of code to be tested for errors.", "keyword_except": "The 'except' keyword lets you handle specific errors.", "keyword_finally": "The 'finally' keyword ensures that code within its block is executed regardless of exceptions.", "keyword_raise": "The 'raise' keyword is used to trigger an exception manually.", "keyword_assert": "The 'assert' keyword checks if a condition is true, raising an AssertionError if it's false.", "keyword_True": "Represents the boolean value true.", "keyword_False": "Represents the boolean value false.", "keyword_None": "Represents the absence of a value or a null value.", "keyword_and": "Logical AND operator.", "keyword_or": "Logical OR operator.", "keyword_not": "Logical NOT operator.", "keyword_in": "Membership operator.", "keyword_is": "Identity operator.", "keyword_del": "The 'del' keyword is used to delete objects.", "keyword_global": "The 'global' keyword declares a variable as belonging to the global scope.", "keyword_nonlocal": "The 'nonlocal' keyword refers to variables in the nearest enclosing scope.", "keyword_with": "The 'with' keyword simplifies exception handling.", "keyword_lambda": "The 'lambda' keyword is used to create small, anonymous functions.", "string_literal": "A sequence of characters, representing text.", "number_literal": "A numeric value, integer or float.", "comment_tag": "A line or block of text ignored by the interpreter.",
        }

        for tag, text in tag_tooltips.items():
            self.text_area.tag_bind(tag, "<Enter>", lambda e, t=text: self._show_tooltip(e, t))
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

        self.text_area.tag_bind("builtin_function", "<Enter>", lambda e: self._on_hover_word(e, self.builtin_tooltips))
        self.text_area.tag_bind("builtin_function", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("dunder_init", "<Enter>", lambda e: self._on_hover_word(e, self.dunder_tooltips))
        self.text_area.tag_bind("dunder_init", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("reactive_error_line", "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text))
        self.text_area.tag_bind("reactive_error_line", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("proactive_error_line", "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text))
        self.text_area.tag_bind("proactive_error_line", "<Leave>", self._hide_tooltip)

    def _on_hover_word(self, event, tooltip_dict):
        index = self.text_area.index(f"@{event.x},{event.y}")
        word_start = self.text_area.index(f"{index} wordstart")
        word_end = self.text_area.index(f"{index} wordend")
        word = self.text_area.get(word_start, word_end)
        tooltip_text = tooltip_dict.get(word)
        if tooltip_text:
            self._show_tooltip(event, tooltip_text)

    def perform_autocomplete(self, text_to_insert):
        self.text_area.edit_separator()
        current_word_start = self.text_area.index("insert-1c wordstart")
        self.text_area.delete(current_word_start, "insert")
        self.text_area.insert(current_word_start, text_to_insert)
        self.last_action_was_autocomplete = True
        self.text_area.focus_set()

    def _on_backspace(self, event):
        if self.last_action_was_autocomplete:
            self.last_action_was_autocomplete = False
            self.text_area.edit_undo()
            self.autocomplete_manager.hide()
            return "break"
        self.after(10, self._update_autocomplete_display)
        return None

    def _on_tab(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.confirm_selection()
        
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    ")
        return "break"
    
    def _on_return(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.confirm_selection()
        
        self.autocomplete_dismissed_word = None
        return self._auto_indent(event)

    def _update_autocomplete_display(self):
        if not self.autocomplete_active:
            self.autocomplete_manager.hide()
            return
            
        current_word = self.text_area.get("insert-1c wordstart", "insert")
        
        if self.autocomplete_dismissed_word is not None:
            if current_word == self.autocomplete_dismissed_word:
                return
            else:
                self.autocomplete_dismissed_word = None

        if len(current_word) < 1:
            self.autocomplete_manager.hide()
            return

        all_text = self.text_area.get("1.0", tk.END)
        words_in_doc = set(re.findall(r'\b\w{3,}\b', all_text))
        
        completions = []
        labels_so_far = set()

        def add_completion(item):
            # Use the 'label' for uniqueness check
            if item['label'] not in labels_so_far:
                completions.append(item)
                labels_so_far.add(item['label'])

        for s in self.snippets:
            if s['match'].startswith(current_word):
                add_completion(s)
        for k in self.keyword_list:
            if k.startswith(current_word):
                add_completion({'label': k, 'match': k, 'type': 'keyword', 'insert': k, 'detail': 'Python keyword.'})
        for f in self.builtin_list:
            if f.startswith(current_word):
                add_completion({'label': f, 'match': f, 'type': 'function', 'insert': f, 'detail': self.builtin_tooltips.get(f, 'Built-in Python function.')})
        for w in words_in_doc:
            if w.startswith(current_word):
                add_completion({'label': w, 'match': w, 'type': 'variable', 'insert': w, 'detail': 'Variable from current document.'})
        
        completions.sort(key=lambda x: x['label'])

        if completions:
            bbox = self.text_area.bbox(tk.INSERT)
            if bbox:
                self.autocomplete_manager.show(completions, bbox)
        else:
            self.autocomplete_manager.hide()

    def _show_tooltip(self, event, text):
        if not text: return
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
        num_lines_str = self.text_area.index("end-1c").split('.')[0]
        if not num_lines_str.isdigit(): return
        num_lines = int(num_lines_str)
        line_numbers_text = "\n".join(str(i) for i in range(1, num_lines + 1))
        self.linenumbers.insert("1.0", line_numbers_text)
        self.linenumbers.config(state="disabled")
        first_visible_line = self.text_area.yview()[0]
        self.linenumbers.yview_moveto(first_visible_line)

    def _on_content_changed(self, event=None):
        self.update_line_numbers()
        self.apply_syntax_highlighting()
        self._proactive_syntax_check()

    def _on_key_release(self, event=None):
        if not event: return
        self.last_action_was_autocomplete = False
        
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
            return 
        
        if len(event.keysym) == 1 or event.keysym == '_' or event.keysym == 'BackSpace':
            self.after(50, self._update_autocomplete_display)
        else:
            self.autocomplete_manager.hide()
            self.autocomplete_dismissed_word = None
            
        if event.keysym not in ("Return", "(", "[", "{", "BackSpace", "Delete", "Tab"):
             self._on_content_changed()

    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            self.last_action_was_autocomplete = False
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self.autocomplete_manager.hide()
        
        scroll = 0
        if event.num == 4 or event.delta > 0: scroll = -1
        elif event.num == 5 or event.delta < 0: scroll = 1
        if scroll != 0:
            self.linenumbers.yview_scroll(scroll, "units")
            self.text_area.yview_scroll(scroll, "units")
        return "break"

    def _auto_complete_brackets(self, event, open_char, close_char):
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, open_char + close_char)
        self.text_area.mark_set(tk.INSERT, "insert-1c")
        self.last_action_was_autocomplete = True
        self._on_content_changed()
        return "break"

    def _auto_indent(self, event):
        self.text_area.edit_separator()
        current_index = self.text_area.index(tk.INSERT)
        line_str, _ = current_index.split('.')
        if not line_str.isdigit(): return "break"
        line = int(line_str)
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
        start, end = f"{line_number}.0", f"{line_number}.end"
        self.text_area.tag_add("proactive_error_line", start, end)

    def clear_error_highlight(self):
        self.text_area.tag_remove("reactive_error_line", "1.0", tk.END)
        self.text_area.tag_remove("proactive_error_line", "1.0", tk.END)
        self.error_tooltip_text = ""

    def apply_syntax_highlighting(self):
        for tag in self.text_area.tag_names():
            if tag not in ("sel", "insert", "current", "reactive_error_line", "proactive_error_line"):
                self.text_area.tag_remove(tag, "1.0", tk.END)

        content = self.text_area.get("1.0", tk.END)
        
        # This dictionary maps the regex pattern to the specific tag name
        keywords = { r"\bif\b": "keyword_if", r"\belse\b": "keyword_else", r"\belif\b": "keyword_elif", r"\bfor\b": "keyword_for", r"\bwhile\b": "keyword_while", r"\breturn\b": "keyword_return", r"\bbreak\b": "keyword_break", r"\bcontinue\b": "keyword_continue", r"\byield\b": "keyword_yield", r"\bpass\b": "keyword_pass", r"\bimport\b": "keyword_import", r"\bfrom\b": "keyword_from", r"\bas\b": "keyword_as", r"\btry\b": "keyword_try", r"\bexcept\b": "keyword_except", r"\bfinally\b": "keyword_finally", r"\braise\b": "keyword_raise", r"\bassert\b": "keyword_assert", r"\bTrue\b": "keyword_True", r"\bFalse\b": "keyword_False", r"\bNone\b": "keyword_None", r"\band\b": "keyword_and", r"\bor\b": "keyword_or", r"\bnot\b": "keyword_not", r"\bin\b": "keyword_in", r"\bis\b": "keyword_is", r"\bdel\b": "keyword_del", r"\bglobal\b": "keyword_global", r"\bnonlocal\b": "keyword_nonlocal", r"\basync\b": "keyword_async", r"\bawait\b": "keyword_await", r"\bwith\b": "keyword_with", r"\blambda\b": "keyword_lambda" }
        highlight_patterns = { r"\bPriesty\b": "priesty_keyword", r"\bdef\b": "def_keyword", r"\bclass\b": "class_keyword", r"\b(" + "|".join(self.builtin_list) + r")\b": "builtin_function", r"[(){}[\]]": "bracket_tag", r"\b__init__\b": "dunder_init", **keywords }

        for match in re.finditer(r"(#.*)", content): self._apply_tag("comment_tag", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for pattern in [r"'''.*?'''", r'""".*?"""']:
            for match in re.finditer(pattern, content, re.DOTALL): self._apply_tag("string_literal", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for match in re.finditer(r"""(?<!['"])(['"])(?:(?=(\\?))\2.)*?\1""", content):
             start, end = f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars"
             if not self._is_inside_tag_by_index(start, end, "string_literal"): self._apply_tag("string_literal", start, end)
        
        for pattern, tag in highlight_patterns.items():
            for match in re.finditer(pattern, content):
                start, end = f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars"
                if not (self._is_inside_tag_by_index(start, end, "comment_tag") or self._is_inside_tag_by_index(start, end, "string_literal")):
                    self._apply_tag(tag, start, end)

        for match in re.finditer(r'\b\d+(\.\d*)?([eE][+-]?\d+)?\b', content):
            start, end = f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars"
            if not (self._is_inside_tag_by_index(start, end, "comment_tag") or self._is_inside_tag_by_index(start, end, "string_literal")):
                self._apply_tag("number_literal", start, end)

    def _apply_tag(self, tag_name, start_index, end_index):
        try: self.text_area.tag_add(tag_name, start_index, end_index)
        except tk.TclError: pass

    def _is_inside_tag_by_index(self, start_index, end_index, tag_name):
        return bool(self.text_area.tag_nextrange(tag_name, start_index, end_index))

    def _proactive_syntax_check(self):
        code_content = self.text_area.get("1.0", tk.END)
        self.clear_error_highlight()
        if not code_content.strip():
            if self.error_console: self.error_console.clear()
            return
        try:
            ast.parse(code_content)
            if self.error_console: self.error_console.clear()
        except SyntaxError as e:
            cursor_line_str = self.text_area.index(tk.INSERT).split('.')[0]
            if e.lineno == (int(cursor_line_str) if cursor_line_str.isdigit() else 0): return
            line_num = e.lineno or 1
            tooltip_text = f"Syntax Error: {e.msg}"
            self.highlight_syntax_error(line_num, tooltip_text)
            if self.error_console:
                self.error_console.format_error_output(f"Syntax Error (Line {line_num}): {e.msg}\n", f"Full Syntax Error Details:\n{e}")
        except Exception as e:
            if self.error_console:
                self.error_console.format_error_output(f"Proactive Check Error: {type(e).__name__}: {e}", f"Full Error Details:\n{e}")