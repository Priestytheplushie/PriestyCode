# code_editor.py

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import re
import ast
import os # Import os for path manipulation

class AutocompleteManager:
    def __init__(self, editor_instance, icons=None):
        self.editor = editor_instance
        self.text_area = editor_instance.text_area
        self.icons = icons if icons is not None else {}

        self.window = tk.Toplevel(self.text_area)
        self.window.wm_overrideredirect(True) # Remove window decorations
        self.window.withdraw() # Hide initially

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
        """Configures the style and bindings for the Treeview widget used for autocomplete."""
        self.style.configure('Autocomplete.TPanedwindow', sashwidth=2, background="#3C3C3C")
        
        self.style.layout("Custom.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        self.style.configure("Custom.Treeview", background="#3C3C3C", foreground="white",
                             fieldbackground="#3C3C3C", borderwidth=0, rowheight=22)
        self.style.map('Custom.Treeview', background=[('selected', '#555555')])
        self.tree.config(style="Custom.Treeview")
        
        self.tree.heading('#0', text='') # Hide the default heading
        
        # Configure tags for different completion types
        self.tree.tag_configure('variable', foreground='#9CDCFE')
        self.tree.tag_configure('snippet', foreground='#CE9178')
        self.tree.tag_configure('keyword', foreground='#C586C0')
        self.tree.tag_configure('function', foreground='#DCDCAA')
        self.tree.tag_configure('class', foreground='#4EC9B0')

        # Bindings for selection and confirmation
        self.tree.bind('<<TreeviewSelect>>', self.update_preview)
        self.tree.bind('<Return>', self.confirm_selection)
        self.tree.bind('<Tab>', self.confirm_selection)
        self.tree.bind('<Double-1>', self.confirm_selection)

    def show(self, completions, bbox):
        """Displays the autocomplete window with the given completions."""
        if not completions or not bbox:
            self.hide()
            return
        
        self.completions = completions
        self.tree.delete(*self.tree.get_children()) # Clear previous items

        for i, item in enumerate(completions):
            item_type = item.get('type', 'variable')
            
            insert_kwargs = {
                'iid': i, # Unique identifier for the item
                'text': ' ' + item['label'], # Add space for icon alignment
                'tags': (item_type,)
            }
            icon = self.icons.get(item_type)
            if icon:
                insert_kwargs['image'] = icon

            self.tree.insert('', 'end', **insert_kwargs)

        # Adjust window height based on number of items
        num_items = len(completions)
        new_height = min(num_items, 10) * 22 + 6 # Max 10 items visible, plus padding

        # Position and show the window
        if not self.window.winfo_viewable():
            x, y, _, h = bbox # bbox provides (x, y, width, height) of the character
            x += self.text_area.winfo_rootx() # Convert to screen coordinates
            y += self.text_area.winfo_rooty() + h
            self.window.geometry(f"550x{new_height}+{x}+{y}")
            self.window.deiconify() # Show the window
            self.window.lift() # Bring to front
        else:
            # If already visible, just resize
            current_x = self.window.winfo_x()
            current_y = self.window.winfo_y()
            self.window.geometry(f"550x{new_height}+{current_x}+{current_y}")
        
        # Select the first item by default
        if self.tree.get_children():
            self.tree.selection_set('0')
            self.tree.focus('0')

    def hide(self):
        """Hides the autocomplete window."""
        self.window.withdraw()

    def is_visible(self):
        """Checks if the autocomplete window is currently visible."""
        return self.window.winfo_viewable()

    def update_preview(self, event=None):
        """Updates the preview text based on the selected autocomplete item."""
        selected_ids = self.tree.selection()
        if not selected_ids:
            self.preview_text.config(state="normal")
            self.preview_text.delete("1.0", tk.END)
            self.preview_text.config(state="disabled")
            return
        
        selected_index = int(selected_ids[0])
        item = self.completions[selected_index]
        
        item_type = item.get('type', 'variable').capitalize()
        detail = item.get('detail', '')
        preview_content = f"({item_type}) {item.get('label')}\n"
        if detail:
            preview_content += f"-----------------\n{detail}"
        
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", preview_content)
        self.preview_text.config(state="disabled")

    def confirm_selection(self, event=None):
        """Confirms the selected autocomplete item and inserts it into the editor."""
        if not self.is_visible(): return

        selected_ids = self.tree.selection()
        if not selected_ids: return 'break' # Prevent default behavior if no selection
            
        selected_index = int(selected_ids[0])
        item = self.completions[selected_index]
        self.editor.perform_autocomplete(item['insert'])
        self.hide()
        return 'break' # Prevent default behavior

    def navigate(self, direction):
        """Navigates up/down in the autocomplete list."""
        if not self.is_visible(): return
        
        current_focus = self.tree.focus()
        if not current_focus: return
        
        next_item = self.tree.next(current_focus) if direction > 0 else self.tree.prev(current_focus)
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item) # Ensure the item is visible
        return 'break'

class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, autocomplete_icons=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B")

        self.error_console = error_console
        self.last_action_was_autocomplete = False
        self.autocomplete_active = True
        self.proactive_errors_active = True
        self.autocomplete_dismissed_word = None # To prevent re-showing dismissed completions
        self.imported_aliases = {} # To store parsed import information

        self.editor_frame = tk.Frame(self, bg="#2B2B2B")
        self.editor_frame.pack(fill="both", expand=True)

        # Line numbers widget
        self.linenumbers = tk.Text(self.editor_frame, width=4, padx=3, takefocus=0, border=0, background="#2B2B2B", foreground="#888888", state="disabled", wrap="none", font=("Consolas", 10))
        self.linenumbers.pack(side="left", fill="y")

        # Main text area for code
        self.text_area = scrolledtext.ScrolledText(self.editor_frame, wrap="word", bg="#2B2B2B", fg="white", insertbackground="white", selectbackground="#4E4E4E", font=("Consolas", 10), undo=True)
        self.text_area.pack(side="right", fill="both", expand=True)

        # Tooltip for error messages and function help
        self.tooltip_window = tk.Toplevel(self.text_area)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_withdraw() # Hide initially
        self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left', background="#3C3C3C", foreground="white", relief='solid', borderwidth=1, wraplength=400, font=("Consolas", 9), padx=4, pady=2)
        self.tooltip_label.pack(ipadx=1)
        self.error_tooltip_text = "" # Stores the current error message for the tooltip
        
        self.autocomplete_manager = AutocompleteManager(self, icons=autocomplete_icons)
        self.file_path: str | None = None # Added for Bug 5: Stores the path of the current file
        self._configure_autocomplete_data()
        self._configure_tags_and_tooltips()

        # Bindings for editor functionality
        self.text_area.bind("<Configure>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<<Change>>", self._on_text_modified) # Custom event for text changes
        self.text_area.bind("<MouseWheel>", self._on_mouse_scroll)
        self.text_area.bind("<Button-4>", self._on_mouse_scroll) # Linux scroll up
        self.text_area.bind("<Button-5>", self._on_mouse_scroll) # Linux scroll down
        self.text_area.bind("<Button-1>", self._on_click) # Hide autocomplete on click
        self.text_area.bind("<Return>", self._on_return_key) # Handle Enter key (Bug 2)
        self.text_area.bind("<Tab>", self._on_tab) # Handle Tab key
        self.text_area.bind("<BackSpace>", self._on_backspace) # Handle Backspace
        self.text_area.bind("<Control-BackSpace>", self._on_ctrl_backspace) # FIX 3: Handle Ctrl+Backspace
        # Auto-completion for brackets/parentheses
        self.text_area.bind("(", lambda event: self._auto_complete_brackets(event, '(', ')'))
        self.text_area.bind("[", lambda event: self._auto_complete_brackets(event, '[', ']'))
        self.text_area.bind("{", lambda event: self._auto_complete_brackets(event, '{', '}'))
        self.text_area.bind(".", self._on_dot_key) # Context-aware autocomplete trigger
        self.text_area.bind("<Escape>", self._on_escape) # Hide autocomplete on escape
        self.text_area.bind("<Up>", self._on_arrow_up) # Navigate autocomplete list
        self.text_area.bind("<Down>", self._on_arrow_down) # Navigate autocomplete list

        self.text_area.edit_modified(False) # Reset modified flag
        self.apply_syntax_highlighting()

    def set_file_path(self, path: str):
        """Sets the file path associated with this editor instance (Bug 5)."""
        self.file_path = path

    def set_proactive_error_checking(self, is_active):
        """Enables or disables proactive syntax error checking."""
        self.proactive_errors_active = is_active
        if not is_active:
            self.clear_error_highlight()
        else:
            self._proactive_syntax_check()

    def _on_escape(self, event):
        """Handles the Escape key press, primarily for dismissing autocomplete."""
        if self.autocomplete_manager.is_visible():
            self.autocomplete_manager.hide()
            # Store the word that was being autocompleted to avoid immediate re-show
            self.autocomplete_dismissed_word = self.text_area.get("insert-1c wordstart", "insert")
            return "break" # Consume the event
        return None

    def _on_arrow_up(self, event):
        """Navigates up in the autocomplete list if visible."""
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.navigate(-1)
        return None

    def _on_arrow_down(self, event):
        """Navigates down in the autocomplete list if visible."""
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.navigate(1)
        return None

    def _on_click(self, event):
        """Hides the autocomplete window and clears dismissed word on mouse click."""
        self.autocomplete_manager.hide()
        self.autocomplete_dismissed_word = None
    
    def _on_dot_key(self, event):
        """Handles the dot key for context-aware autocompletion."""
        self.autocomplete_dismissed_word = None
        
        # Insert the dot
        self.text_area.insert(tk.INSERT, ".")
        
        # Check word before the dot
        word_before_dot = self.text_area.get("insert-2c wordstart", "insert-1c")
        
        real_module = self.imported_aliases.get(word_before_dot)
        base_module = real_module.split('.')[0] if real_module else None

        if base_module and base_module in self.standard_libraries:
            completions = []
            module_data = self.standard_libraries[base_module]
            for member in module_data.get('members', []):
                completions.append({
                    'label': member, 'match': member, 'type': 'function',
                    'insert': member, 'detail': self.standard_library_function_tooltips.get(f"{base_module}.{member}", "Standard library function/attribute.")
                })
            
            if completions:
                bbox = self.text_area.bbox(tk.INSERT)
                if bbox:
                    self.autocomplete_manager.show(completions, bbox)
        else:
            self.autocomplete_manager.hide() # Not a known std lib, hide window

        return "break" # Prevent default behavior for the dot


    def _configure_autocomplete_data(self):
        """Defines snippets, built-in functions, and keywords for autocomplete."""
        self.snippets = [
            {'label': 'def (function)', 'match': 'def', 'type': 'snippet', 'detail': 'Define a new function.\n\ndef function_name(params):\n    pass', 'insert': 'def function_name(params):\n    pass'},
            {'label': 'def (constructor)', 'match': 'def', 'type': 'snippet', 'detail': 'Define the constructor for a class.\n\ndef __init__(self):\n    pass', 'insert': 'def __init__(self):\n    pass'},
            {'label': 'if', 'match': 'if', 'type': 'snippet', 'detail': 'Create an if statement.\n\nif condition:\n    pass', 'insert': 'if condition:\n    pass'},
            {'label': 'if/else', 'match': 'if', 'type': 'snippet', 'detail': 'Create an if/else block.\n\nif condition:\n    pass\nelse:\n    pass', 'insert': 'if condition:\n    pass\nelse:\n    pass'},
            {'label': 'if/elif/else', 'match': 'if', 'type': 'snippet', 'detail': 'Create an if/elif/else block.\n\nif condition1:\n    pass\nelif condition2:\n    pass\nelse:\n    pass', 'insert': 'if condition1:\n    pass\nelif condition2:\n    pass\nelse:\n    pass'},
            {'label': 'for', 'match': 'for', 'type': 'snippet', 'detail': 'Create a for loop.\n\nfor item in iterable:\n    pass', 'insert': 'for item in iterable:\n    pass'},
            {'label': 'while', 'match': 'while', 'type': 'snippet', 'detail': 'Create a while loop.\n\nwhile condition:\n    pass', 'insert': 'while condition:\n    pass'},
            {'label': 'class', 'match': 'class', 'type': 'snippet', 'detail': 'Create a new class.\n\nclass NewClass:\n    def __init__(self):\n        pass', 'insert': 'class NewClass:\n    def __init__(self):\n        pass'},
            {'label': 'try', 'match': 'try', 'type': 'snippet', 'detail': 'Create a try/except block.\n\ntry:\n    pass\nexcept Exception as e:\n    print(e)', 'insert': 'try:\n    pass\nexcept Exception as e:\n    print(f"An error occurred: {e}")'},
            {'label': 'with (file)', 'match': 'with', 'type': 'snippet', 'detail': "Open a file safely.\n\nwith open('file.txt', 'r') as f:\n    content = f.read()", 'insert': "with open('file.txt', 'r') as f:\n    pass"},
            {'label': 'main', 'match': 'main', 'type': 'snippet', 'detail': 'Standard main execution block.\n\nif __name__ == "__main__":\n    # code here', 'insert': 'if __name__ == "__main__":\n    pass'},
            {'label': '__str__', 'match': '__str__', 'type': 'snippet', 'detail': 'Define the string representation of an object.', 'insert': 'def __str__(self):\n    return super().__str__()'},
            {'label': 'docstring', 'match': 'doc', 'type': 'snippet', 'detail': 'Create a standard docstring for a function or class.', 'insert': '"""\n\n"""'},
            {'label': 'list comprehension', 'match': 'for', 'type': 'snippet', 'detail': 'List comprehension to generate a list.\n\n[expression for item in iterable]', 'insert': '[x for x in iterable]'},
            {'label': 'enumerate loop', 'match': 'for', 'type': 'snippet', 'detail': 'Enumerate loop with index and value.\n\nfor i, val in enumerate(iterable):', 'insert': 'for i, val in enumerate(iterable):\n    pass'},
            {'label': 'property decorator', 'match': '@property', 'type': 'snippet', 'detail': 'Expose method as a read-only property.', 'insert': '@property\ndef attr_name(self):\n    return self._attr_name'},
            {'label': 'lambda function', 'match': 'lambda', 'type': 'snippet', 'detail': 'Anonymous function.\n\nlambda args: expression', 'insert': 'lambda x: x * 2'},
            {'label': 'context manager', 'match': 'with', 'type': 'snippet', 'detail': 'Custom context manager class.\n\nclass MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass', 'insert': 'class MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass\n\nwith MyContext() as ctx:\n    pass'},
            {'label': 'list comprehension', 'match': 'for', 'type': 'snippet', 'detail': 'List comprehension to generate a list.\n\n[expression for item in iterable]', 'insert': '[x for x in iterable]'},
            {'label': 'enumerate loop', 'match': 'for', 'type': 'snippet', 'detail': 'Enumerate loop with index and value.\n\nfor i, val in enumerate(iterable):', 'insert': 'for i, val in enumerate(iterable):\n    pass'},
            {'label': 'property decorator', 'match': '@property', 'type': 'snippet', 'detail': 'Expose method as a read-only property.', 'insert': '@property\ndef attr_name(self):\n    return self._attr_name'},
            {'label': 'lambda function', 'match': 'lambda', 'type': 'snippet', 'detail': 'Anonymous function.\n\nlambda args: expression', 'insert': 'lambda x: x * 2'},
            {'label': 'context manager', 'match': 'with', 'type': 'snippet', 'detail': 'Custom context manager class.\n\nclass MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass', 'insert': 'class MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass\n\nwith MyContext() as ctx:\n    pass'},
            {'label': 'classmethod', 'match': 'def', 'type': 'snippet', 'detail': 'Define a class method.\n\n@classmethod\ndef method(cls):', 'insert': '@classmethod\ndef from_something(cls, arg):\n    return cls(arg)'},
            {'label': 'staticmethod', 'match': 'def', 'type': 'snippet', 'detail': 'Define a static method.\n\n@staticmethod\ndef method():', 'insert': '@staticmethod\ndef util_method(x):\n    return x'},
            {'label': 'dataclass', 'match': '@dataclass', 'type': 'snippet', 'detail': 'Use Python 3.7+ dataclass decorator.\n\n@dataclass\nclass Name:', 'insert': '@dataclass\nclass MyData:\n    field1: int\n    field2: str'},
            {'label': 'generator', 'match': 'def', 'type': 'snippet', 'detail': 'Create a generator function.\n\ndef gen():\n    yield item', 'insert': 'def my_generator():\n    for i in range(10):\n        yield i'},
            {'label': 'list comprehension', 'match': 'for', 'type': 'snippet', 'detail': 'List comprehension to generate a list.\n\n[expression for item in iterable]', 'insert': '[x for x in iterable]'},
            {'label': 'enumerate loop', 'match': 'for', 'type': 'snippet', 'detail': 'Enumerate loop with index and value.\n\nfor i, val in enumerate(iterable):', 'insert': 'for i, val in enumerate(iterable):\n    pass'},
            {'label': 'property decorator', 'match': '@property', 'type': 'snippet', 'detail': 'Expose method as a read-only property.', 'insert': '@property\ndef attr_name(self):\n    return self._attr_name'},
            {'label': 'lambda function', 'match': 'lambda', 'type': 'snippet', 'detail': 'Anonymous function.\n\nlambda args: expression', 'insert': 'lambda x: x * 2'},
            {'label': 'context manager', 'match': 'with', 'type': 'snippet', 'detail': 'Custom context manager class.\n\nclass MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass', 'insert': 'class MyContext:\n    def __enter__(self):\n        pass\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        pass\n\nwith MyContext() as ctx:\n    pass'},
            {'label': 'classmethod', 'match': 'def', 'type': 'snippet', 'detail': 'Define a class method.\n\n@classmethod\ndef method(cls):', 'insert': '@classmethod\ndef from_something(cls, arg):\n    return cls(arg)'},
            {'label': 'staticmethod', 'match': 'def', 'type': 'snippet', 'detail': 'Define a static method.\n\n@staticmethod\ndef method():', 'insert': '@staticmethod\ndef util_method(x):\n    return x'},
            {'label': 'dataclass', 'match': '@dataclass', 'type': 'snippet', 'detail': 'Use Python 3.7+ dataclass decorator.\n\n@dataclass\nclass Name:', 'insert': '@dataclass\nclass MyData:\n    field1: int\n    field2: str'},
            {'label': 'generator', 'match': 'def', 'type': 'snippet', 'detail': 'Create a generator function.\n\ndef gen():\n    yield item', 'insert': 'def my_generator():\n    for i in range(10):\n        yield i'},
            {'label': 'print statement', 'match': 'pri', 'type': 'snippet', 'detail': 'Basic print usage.\n\nprint("message")', 'insert': 'print("Hello, world!")'},
            {'label': 'input prompt', 'match': 'inp', 'type': 'snippet', 'detail': 'Read user input.\n\ninput("prompt")', 'insert': 'user_input = input("Enter value: ")'},
            {'label': 'function call', 'match': 'func', 'type': 'snippet', 'detail': 'Call a function with parameters.\n\nfunction_name(args)', 'insert': 'result = my_function(arg1, arg2)'},
            {'label': 'basic assignment', 'match': 'val', 'type': 'snippet', 'detail': 'Assign a value to a variable.\n\nvar = value', 'insert': 'x = 42'},
            {'label': 'range loop', 'match': 'for', 'type': 'snippet', 'detail': 'For loop with range.\n\nfor i in range(n):', 'insert': 'for i in range(10):\n    print(i)'}
        ]

        self.builtin_list = ['abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip']
        self.keyword_list = ['and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try', 'while', 'with', 'yield']

        self.exception_list = [
            'Exception', 'BaseException', 'ArithmeticError', 'AssertionError', 'AttributeError',
            'EOFError', 'ImportError', 'ModuleNotFoundError', 'IndexError', 'KeyError',
            'KeyboardInterrupt', 'MemoryError', 'NameError', 'NotImplementedError', 'OSError',
            'OverflowError', 'RecursionError', 'RuntimeError', 'SyntaxError', 'SystemError',
            'TypeError', 'ValueError', 'ZeroDivisionError', 'FileNotFoundError',
            'PermissionError', 'TimeoutError', 'ConnectionError'
        ]
        self.exception_tooltips = {
            'Exception': 'Common base class for all non-exit exceptions.',
            'BaseException': 'The base class for all built-in exceptions.',
            'ArithmeticError': 'Base class for arithmetic errors like OverflowError, ZeroDivisionError.',
            'AssertionError': 'Raised when an assert statement fails.',
            'AttributeError': 'Raised when an attribute reference or assignment fails.',
            'EOFError': 'Raised when input() hits an end-of-file condition (EOF).',
            'ImportError': 'Raised when an import statement has trouble trying to load a module.',
            'ModuleNotFoundError': 'A subclass of ImportError; raised when a module could not be found.',
            'IndexError': 'Raised when a sequence subscript is out of range.',
            'KeyError': 'Raised when a mapping (dictionary) key is not found.',
            'KeyboardInterrupt': 'Raised when the user hits the interrupt key (normally Ctrl+C).',
            'MemoryError': 'Raised when an operation runs out of memory.',
            'NameError': 'Raised when a local or global name is not found.',
            'NotImplementedError': 'Raised by abstract methods.',
            'OSError': 'Raised for system-related errors.',
            'OverflowError': 'Raised when the result of an arithmetic operation is too large to be represented.',
            'RecursionError': 'Raised when the maximum recursion depth is exceeded.',
            'RuntimeError': 'Raised when an error is detected that doesn’t fall in any of the other categories.',
            'SyntaxError': 'Raised when the parser encounters a syntax error.',
            'SystemError': 'Raised for interpreter-level errors.',
            'TypeError': 'Raised when an operation or function is applied to an object of inappropriate type.',
            'ValueError': 'Raised when a function receives an argument of the correct type but an inappropriate value.',
            'ZeroDivisionError': 'Raised when the second argument of a division or modulo operation is zero.',
            'FileNotFoundError': 'Raised when a file or directory is requested but doesn’t exist.',
            'PermissionError': 'Raised when trying to run an operation without the adequate access rights.',
            'TimeoutError': 'Raised when a system function timed out at the system level.',
            'ConnectionError': 'A base class for connection-related issues.'
        }
        self.standard_libraries = {
            'os': {'members': ['path', 'name', 'environ', 'getcwd', 'listdir', 'mkdir', 'makedirs', 'remove', 'removedirs', 'rename', 'rmdir', 'stat', 'system'], 'tooltip': 'Operating system interfaces, including file system functions.'},
            'sys': {'members': ['argv', 'exit', 'path', 'platform', 'stdin', 'stdout', 'stderr', 'version'], 'tooltip': 'System-specific parameters and functions.'},
            're': {'members': ['search', 'match', 'fullmatch', 'split', 'findall', 'finditer', 'sub', 'compile', 'escape'], 'tooltip': 'Regular expression operations.'},
            'json': {'members': ['dump', 'dumps', 'load', 'loads'], 'tooltip': 'JSON encoder and decoder.'},
            'datetime': {'members': ['datetime', 'date', 'time', 'timedelta', 'timezone', 'now', 'utcnow'], 'tooltip': 'Classes for manipulating dates and times.'},
            'math': {'members': ['ceil', 'floor', 'sqrt', 'pi', 'e', 'sin', 'cos', 'tan', 'log', 'log10', 'pow', 'fabs'], 'tooltip': 'Mathematical functions.'},
            'random': {'members': ['random', 'randint', 'choice', 'choices', 'shuffle', 'uniform'], 'tooltip': 'Generate pseudo-random numbers.'},
            'subprocess': {'members': ['run', 'Popen', 'call', 'check_call', 'check_output', 'PIPE', 'STDOUT'], 'tooltip': 'Subprocess management.'},
            'threading': {'members': ['Thread', 'Lock', 'Event', 'Semaphore', 'current_thread'], 'tooltip': 'Thread-based parallelism.'},
            'collections': {'members': ['defaultdict', 'Counter', 'deque', 'namedtuple', 'OrderedDict'], 'tooltip': 'High-performance container datatypes.'},
            'tkinter': {'members': ['Tk', 'Frame', 'Button', 'Label', 'Entry', 'Text', 'ttk', 'filedialog', 'messagebox'], 'tooltip': 'The standard Python interface to the Tcl/Tk GUI toolkit.'},
            'traceback': {'members': ['print_exc', 'format_exc', 'extract_stack'], 'tooltip': 'Print or retrieve a stack traceback.'},
            'time': {'members': ['time', 'sleep', 'asctime','pthread_getcpuclockid, clock_getres, '], 'tooltip': 'Time access and conversions.'}
        }
        self.standard_library_function_tooltips = {
            'os.path': 'Common pathname manipulations.',
            'os.path.join': 'os.path.join(*paths) -> str\nJoin one or more path components intelligently.',
            'os.path.exists': 'os.path.exists(path) -> bool\nReturn True if path refers to an existing path.',
            'os.path.isdir': 'os.path.isdir(path) -> bool\nReturn True if path is an existing directory.',
            'os.path.isfile': 'os.path.isfile(path) -> bool\nReturn True if path is an existing regular file.',
            'os.getcwd': 'os.getcwd() -> str\nReturn a string representing the current working directory.',
            'os.listdir': 'os.listdir(path=".") -> list\nReturn a list containing the names of the entries in the directory.',
            'sys.exit': 'sys.exit(status=0)\nExit from Python. This is implemented by raising SystemExit.',
            'sys.argv': 'A list of command-line arguments passed to a Python script.',
            're.search': 're.search(pattern, string) -> Match object or None\nScan through string looking for the first location where the pattern produces a match.',
            're.match': 're.match(pattern, string) -> Match object or None\nTry to apply the pattern at the start of the string.',
            're.findall': 're.findall(pattern, string) -> list\nReturn all non-overlapping matches of pattern in string as a list of strings.',
            're.sub': 're.sub(pattern, repl, string) -> str\nReturn the string obtained by replacing the leftmost non-overlapping occurrences of pattern.',
            'json.loads': 'json.loads(s) -> object\nDeserialize a JSON formatted str to a Python object.',
            'json.dumps': 'json.dumps(obj) -> str\nSerialize a Python object to a JSON formatted str.',
            'json.load': 'json.load(fp) -> object\nDeserialize a file-like object containing a JSON document to a Python object.',
            'json.dump': 'json.dump(obj, fp)\nSerialize a Python object as a JSON formatted stream to a file-like object.',
            'datetime.datetime.now': 'datetime.datetime.now(tz=None) -> datetime\nReturn the current local date and time.',
            'random.randint': 'random.randint(a, b) -> int\nReturn a random integer N such that a <= N <= b.',
            'random.choice': 'random.choice(seq)\nReturn a random element from the non-empty sequence.',
            'threading.Thread': 'A class that represents a thread of control.',
            'tkinter.ttk': 'Themed widget set for Tkinter, providing modern-looking widgets.',
            'tkinter.filedialog': 'Provides classes and factory functions for creating file/directory selection windows.',
            'traceback.print_exc': 'traceback.print_exc()\nPrint the exception information and stack trace to sys.stderr.'
        }


    def _configure_tags_and_tooltips(self):
        """Configures Tkinter tags for syntax highlighting and binds tooltips."""
        tag_configs = {
            "reactive_error_line": {"background": "#FF4C4C"}, "handled_exception_line": {"background": "#FFA500"},
            "proactive_error_line": {"background": "#b3b300"}, "priesty_keyword": {"foreground": "#DA70D6"},
            "def_keyword": {"foreground": "#569CD6"}, "class_keyword": {"foreground": "#569CD6"},
            "keyword_if": {"foreground": "#C586C0"}, "keyword_else": {"foreground": "#C586C0"},
            "keyword_elif": {"foreground": "#C586C0"}, "keyword_for": {"foreground": "#C586C0"},
            "keyword_while": {"foreground": "#C586C0"}, "keyword_return": {"foreground": "#C586C0"},
            "keyword_break": {"foreground": "#C586C0"}, "keyword_continue": {"foreground": "#C586C0"},
            "keyword_yield": {"foreground": "#C586C0"}, "keyword_pass": {"foreground": "#C586C0"},
            "keyword_import": {"foreground": "#4EC9B0"}, "keyword_from": {"foreground": "#4EC9B0"},
            "keyword_as": {"foreground": "#4EC9B0"}, "keyword_try": {"foreground": "#D16969"},
            "keyword_except": {"foreground": "#D16969"}, "keyword_finally": {"foreground": "#D16969"},
            "keyword_raise": {"foreground": "#D16969"}, "keyword_assert": {"foreground": "#D16969"},
            "keyword_True": {"foreground": "#569CD6"}, "keyword_False": {"foreground": "#569CD6"},
            "keyword_None": {"foreground": "#569CD6"}, "keyword_and": {"foreground": "#DCDCAA"},
            "keyword_or": {"foreground": "#DCDCAA"}, "keyword_not": {"foreground": "#DCDCAA"},
            "keyword_in": {"foreground": "#DCDCAA"}, "keyword_is": {"foreground": "#DCDCAA"},
            "keyword_del": {"foreground": "#B8D7A3"}, "keyword_global": {"foreground": "#B8D7A3"},
            "keyword_nonlocal": {"foreground": "#B8D7A3"}, "keyword_async": {"foreground": "#FFD700"},
            "keyword_await": {"foreground": "#FFD700"}, "keyword_with": {"foreground": "#CE9178"},
            "keyword_lambda": {"foreground": "#CE9178"}, "string_literal": {"foreground": "#A3C78B"},
            "number_literal": {"foreground": "#B5CEA8"}, "comment_tag": {"foreground": "#6A9955"},
            "function_param": {"foreground": "#9CDCFE"}, "bracket_tag": {"foreground": "#FFD700"},
            "builtin_function": {"foreground": "#DCDCAA"}, "exception_type": {"foreground": "#4EC9B0"},
            "dunder_method": {"foreground": "#DA70D6"},
            "standard_library_module": {"foreground": "#4EC9B0"}, "custom_import": {"foreground": "#9CDCFE"},
            "standard_library_function": {"foreground": "#DCDCAA"}
        }
        for tag, config in tag_configs.items():
            self.text_area.tag_configure(tag, **config)

        # General tooltips for syntax highlighting tags
        tag_tooltips = {
            "def_keyword": "def function_name(params):\n    ...\n\nDefines a function. It is followed by a name, parameters in parentheses, and a colon.\nThe indented block below is the function's body.",
            "class_keyword": "class ClassName(ParentClass):\n    ...\n\nDefines a class. It is followed by a name, an optional parent class in parentheses, and a colon.\nThe indented block contains methods and attributes.",
            "keyword_if": "if condition:\n    ...\n\nStarts a conditional block. The code inside runs only if the condition is True.",
            "keyword_else": "else:\n    ...\n\nUsed with 'if'. The code inside this block runs if the 'if' condition (and any 'elif' conditions) are False.",
            "keyword_elif": "elif condition:\n    ...\n\nShort for 'else if'. Checks another condition if the preceding 'if'/'elif' conditions were False.",
            "keyword_for": "for item in iterable:\n    ...\n\nCreates a loop that iterates over a sequence (e.g., a list, tuple, or string).",
            "keyword_while": "while condition:\n    ...\n\nCreates a loop that continues as long as its condition evaluates to True.",
            "keyword_return": "return [value]\n\nExits a function and optionally sends a value back to the caller. If no value is given, it returns None.",
            "keyword_break": "break\n\nImmediately terminates the innermost 'for' or 'while' loop.",
            "keyword_continue": "continue\n\nSkips the rest of the current loop iteration and proceeds to the next one.",
            "keyword_yield": "yield [value]\n\nPauses a generator function and returns a value. When resumed, it continues from where it left off.",
            "keyword_pass": "pass\n\nA null statement. It acts as a placeholder where code is syntactically required but no action is needed.",
            "keyword_import": "import module\n\nBrings a module into the current scope, making its contents available.",
            "keyword_from": "from module import name\n\nImports specific names from a module directly into the current scope.",
            "keyword_as": "import module as alias\n\nCreates an alternative name (an alias) for an imported module or name.",
            "keyword_try": "try:\n    ...\n\nStarts a block to test for errors. Must be followed by at least one 'except' or 'finally' block.",
            "keyword_except": "except [ExceptionType]:\n    ...\n\nCatches and handles exceptions that occurred in the preceding 'try' block.",
            "keyword_finally": "finally:\n    ...\n\nDefines a block of code that is always executed after a 'try'/'except' block, regardless of errors.",
            "keyword_raise": "raise [Exception]\n\nManually triggers an exception.",
            "keyword_assert": "assert condition, [message]\n\nTests a condition. If it's False, raises an AssertionError. Used for debugging.",
            "keyword_True": "The boolean value for true.", "keyword_False": "The boolean value for false.",
            "keyword_None": "Represents the absence of a value. Often used to indicate uninitialized variables.",
            "keyword_and": "logical AND: x and y", "keyword_or": "logical OR: x or y", "keyword_not": "logical NOT: not x",
            "keyword_in": "Membership test: item in sequence", "keyword_is": "Identity test: object is object",
            "keyword_del": "del object\n\nDeletes an object, variable, or item.",
            "keyword_global": "global variable\n\nDeclares that a variable inside a function belongs to the global scope.",
            "keyword_nonlocal": "nonlocal variable\n\nRefers to a variable in the nearest enclosing (non-global) scope.",
            "keyword_with": "with context_manager as var:\n    ...\n\nUsed with context managers to wrap a block of code, often for resource management (e.g., files).",
            "keyword_lambda": "lambda arguments: expression\n\nCreates a small, anonymous function.",
            "keyword_async": "async def function():\n    ...\n\nDeclares a coroutine, an awaitable function for asynchronous programming.",
            "keyword_await": "await awaitable\n\nPauses a coroutine until an awaitable object (e.g., another coroutine) completes.",
            "string_literal": "A sequence of characters, enclosed in single, double, or triple quotes.",
            "number_literal": "A numeric value, such as an integer or a floating-point number.",
            "comment_tag": "A line of text ignored by the interpreter, starting with #.",
            "custom_import": "A user-defined or third-party import.",
        }
        
        # Tooltips for built-in functions and dunders
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
        self.dunder_tooltips = {
            '__init__': '__init__(self, ...)\n\nThe constructor method for a class. It is automatically called when a new instance is created and is used to initialize the object\'s attributes.',
            '__str__': '__str__(self) -> str\n\nReturns the "informal" or nicely printable string representation of an object. Used by str() and print().',
            '__repr__': '__repr__(self) -> str\n\nReturns the "official" string representation of an object. This should be an unambiguous representation, ideally one that can be used to recreate the object.'
        }
        
        def create_tooltip_handler(tooltip_text):
            def handler(event):
                if any(tag in self.text_area.tag_names(f"@{event.x},{event.y}") for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]): return
                self._show_tooltip(event, tooltip_text)
            return handler

        for tag, text in tag_tooltips.items():
            self.text_area.tag_bind(tag, "<Enter>", create_tooltip_handler(text))
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

        def create_word_hover_handler(tooltip_dict):
            def handler(event):
                if any(tag in self.text_area.tag_names(f"@{event.x},{event.y}") for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]): return
                self._on_hover_word(event, tooltip_dict)
            return handler
        
        self.text_area.tag_bind("builtin_function", "<Enter>", create_word_hover_handler(self.builtin_tooltips))
        self.text_area.tag_bind("builtin_function", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("exception_type", "<Enter>", create_word_hover_handler(self.exception_tooltips))
        self.text_area.tag_bind("exception_type", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("dunder_method", "<Enter>", create_word_hover_handler(self.dunder_tooltips))
        self.text_area.tag_bind("dunder_method", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("standard_library_module", "<Enter>", self._on_hover_standard_lib_module)
        self.text_area.tag_bind("standard_library_module", "<Leave>", self._hide_tooltip)
        self.text_area.tag_bind("standard_library_function", "<Enter>", self._on_hover_standard_lib_function)
        self.text_area.tag_bind("standard_library_function", "<Leave>", self._hide_tooltip)
        
        for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]:
            self.text_area.tag_bind(tag, "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text))
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

    def _on_hover_standard_lib_module(self, event):
        """Tooltip handler for standard library modules."""
        word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
        real_module = self.imported_aliases.get(word)
        base_module = real_module.split('.')[0] if real_module else None
        if base_module and base_module in self.standard_libraries:
            tooltip_text = self.standard_libraries[base_module].get('tooltip', 'Standard library module.')
            self._show_tooltip(event, tooltip_text)

    def _on_hover_standard_lib_function(self, event):
        """Tooltip handler for functions/attributes from standard library modules."""
        index = f"@{event.x},{event.y}"
        current_word = self.text_area.get(f"{index} wordstart", f"{index} wordend")
        
        word_range = self.text_area.tag_prevrange("standard_library_module", f"{index} wordstart")
        if not word_range: return
        
        module_word = self.text_area.get(word_range[0], word_range[1])
        real_module = self.imported_aliases.get(module_word)
        base_module = real_module.split('.')[0] if real_module else None

        if base_module:
            full_name = f"{base_module}.{current_word}"
            tooltip_text = self.standard_library_function_tooltips.get(full_name, "Standard library function/attribute.")
            self._show_tooltip(event, tooltip_text)


    def _on_hover_word(self, event, tooltip_dict):
        """Displays a tooltip for the word under the mouse cursor."""
        try:
            index = self.text_area.index(f"@{event.x},{event.y}")
            word_start = self.text_area.index(f"{index} wordstart")
            word_end = self.text_area.index(f"{index} wordend")
            word = self.text_area.get(word_start, word_end)
            tooltip_text = tooltip_dict.get(word)
            if tooltip_text:
                self._show_tooltip(event, tooltip_text)
        except tk.TclError: pass

    def perform_autocomplete(self, text_to_insert):
        """Performs the actual text insertion for autocomplete."""
        self.text_area.edit_separator()
        current_word_start = self.text_area.index("insert-1c wordstart")
        self.text_area.delete(current_word_start, "insert")
        self.text_area.insert(current_word_start, text_to_insert)
        self.last_action_was_autocomplete = True
        self.text_area.focus_set()
        self._on_content_changed()

    def _on_backspace(self, event):
        if self.last_action_was_autocomplete:
            self.last_action_was_autocomplete = False
            self.text_area.edit_undo()
            self.autocomplete_manager.hide()
            return "break"
        self.after(10, self._update_autocomplete_display)
        return None
    
    def _on_ctrl_backspace(self, event):
        """Handles Ctrl+Backspace to delete the previous word."""
        self.text_area.delete("insert-1c wordstart", "insert")
        return "break"

    def _on_tab(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.confirm_selection()
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    ")
        return "break"
    
    def _on_return_key(self, event):
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
            if current_word == self.autocomplete_dismissed_word: return
            else: self.autocomplete_dismissed_word = None

        if len(current_word) < 1:
            self.autocomplete_manager.hide()
            return

        all_text = self.text_area.get("1.0", tk.END)
        words_in_doc = set(re.findall(r'\b\w{3,}\b', all_text))
        
        completions = []
        labels_so_far = set()

        def add_completion(item):
            if item['label'] not in labels_so_far:
                completions.append(item)
                labels_so_far.add(item['label'])
        
        for s in self.snippets:
            if s['match'].startswith(current_word): add_completion(s)
        for k in self.keyword_list:
            if k.startswith(current_word): add_completion({'label': k, 'type': 'keyword', 'insert': k, 'detail': 'Python keyword.'})
        for f in self.builtin_list:
            if f.startswith(current_word): add_completion({'label': f, 'type': 'function', 'insert': f, 'detail': self.builtin_tooltips.get(f, 'Built-in Python function.')})
        for e in self.exception_list:
            if e.startswith(current_word): add_completion({'label': e, 'type': 'class', 'insert': e, 'detail': self.exception_tooltips.get(e, 'Built-in Python exception.')})
        for m in self.standard_libraries:
            if m.startswith(current_word): add_completion({'label': m, 'type': 'class', 'insert': m, 'detail': self.standard_libraries[m].get('tooltip', 'Standard library module.')})
        for w in sorted(list(words_in_doc)):
            if w.startswith(current_word) and len(w) > len(current_word): add_completion({'label': w, 'type': 'variable', 'insert': w, 'detail': 'Variable from current document.'})
        
        completions.sort(key=lambda x: x['label'])

        if completions:
            bbox = self.text_area.bbox(tk.INSERT)
            if bbox: self.autocomplete_manager.show(completions, bbox)
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
        self.linenumbers.yview_moveto(self.text_area.yview()[0])

    def _on_content_changed(self, event=None):
        self.update_line_numbers()
        self.apply_syntax_highlighting()
        self._proactive_syntax_check()

    def _on_key_release(self, event=None):
        if not event: return
        self.last_action_was_autocomplete = False
        
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape", "period"): return 
        
        if len(event.keysym) == 1 or event.keysym in ('underscore', 'BackSpace'):
            self.after(50, self._update_autocomplete_display)
        else:
            self.autocomplete_manager.hide()
            self.autocomplete_dismissed_word = None
            
        self._on_content_changed()

    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            self.last_action_was_autocomplete = False
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self.autocomplete_manager.hide()
        self.after(10, self.update_line_numbers)

    def _auto_complete_brackets(self, event, open_char, close_char):
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, open_char + close_char)
        self.text_area.mark_set(tk.INSERT, "insert-1c")
        self.last_action_was_autocomplete = True
        return "break"

    def _auto_indent(self, event):
        self.text_area.edit_separator()
        current_index = self.text_area.index(tk.INSERT)
        line_num_str, _ = current_index.split('.')
        prev_line_index = f"{line_num_str}.0 - 1 lines"
        prev_line_content = self.text_area.get(prev_line_index, f"{prev_line_index} lineend")
        indent_to_insert = ""
        if prev_line_content:
            prev_indent_match = re.match(r'^(\s*)', prev_line_content)
            if prev_indent_match: indent_to_insert = prev_indent_match.group(1)
            if prev_line_content.strip().endswith(':'): indent_to_insert += "    "
        self.text_area.insert(tk.INSERT, f"\n{indent_to_insert}")
        self._proactive_syntax_check()
        self.last_action_was_autocomplete = True
        return "break"

    def highlight_syntax_error(self, line_number, error_message):
        self.clear_error_highlight()
        self.error_tooltip_text = error_message
        self.text_area.tag_add("proactive_error_line", f"{line_number}.0", f"{line_number}.end")

    def highlight_runtime_error(self, line_number, error_message):
        self.clear_error_highlight()
        self.error_tooltip_text = error_message
        self.text_area.tag_add("reactive_error_line", f"{line_number}.0", f"{line_number}.end")

    def highlight_handled_exception(self, line_number, error_message):
        self.clear_error_highlight()
        self.error_tooltip_text = error_message
        self.text_area.tag_add("handled_exception_line", f"{line_number}.0", f"{line_number}.end")

    def clear_error_highlight(self):
        for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]:
            self.text_area.tag_remove(tag, "1.0", tk.END)
        self.error_tooltip_text = ""

    def apply_syntax_highlighting(self):
        error_tags = ("sel", "insert", "current", "reactive_error_line", "proactive_error_line", "handled_exception_line")
        for tag in self.text_area.tag_names():
            if tag not in error_tags:
                self.text_area.tag_remove(tag, "1.0", tk.END)

        content = self.text_area.get("1.0", tk.END)
        
        # Pass 1: Comments and Strings (highest priority)
        for match in re.finditer(r"(#.*)", content): self._apply_tag("comment_tag", match.start(), match.end())
        for pattern in [r"'''.*?'''", r'""".*?"""']:
            for match in re.finditer(pattern, content, re.DOTALL): self._apply_tag("string_literal", match.start(), match.end())
        string_regex = r"""'[^'\\\n]*(?:\\.[^'\\\n]*)*'|\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\""""
        for match in re.finditer(string_regex, content):
            if not self._is_inside_tag(match.start(), ("comment_tag", "string_literal")):
                self._apply_tag("string_literal", match.start(), match.end())

        # Pass 2: Parse and highlight imports
        self._parse_imports(content)
        for alias, source in self.imported_aliases.items():
            base_source = source.split('.')[0]
            tag = "standard_library_module" if base_source in self.standard_libraries else "custom_import"
            pattern = r"\b" + re.escape(alias) + r"\b"
            for match in re.finditer(pattern, content):
                if not self._is_inside_tag(match.start(), ("comment_tag", "string_literal")):
                    self._apply_tag(tag, match.start(), match.end())
        
        # Pass 3: Keywords, Built-ins, and other fixed patterns
        keywords_map = { r"\bif\b": "keyword_if", r"\belse\b": "keyword_else", r"\belif\b": "keyword_elif", r"\bfor\b": "keyword_for", r"\bwhile\b": "keyword_while", r"\breturn\b": "keyword_return", r"\bbreak\b": "keyword_break", r"\bcontinue\b": "keyword_continue", r"\byield\b": "keyword_yield", r"\bpass\b": "keyword_pass", r"\bimport\b": "keyword_import", r"\bfrom\b": "keyword_from", r"\bas\b": "keyword_as", r"\btry\b": "keyword_try", r"\bexcept\b": "keyword_except", r"\bfinally\b": "keyword_finally", r"\braise\b": "keyword_raise", r"\bassert\b": "keyword_assert", r"\bTrue\b": "keyword_True", r"\bFalse\b": "keyword_False", r"\bNone\b": "keyword_None", r"\band\b": "keyword_and", r"\bor\b": "keyword_or", r"\bnot\b": "keyword_not", r"\bin\b": "keyword_in", r"\bis\b": "keyword_is", r"\bdel\b": "keyword_del", r"\bglobal\b": "keyword_global", r"\bnonlocal\b": "keyword_nonlocal", r"\basync\b": "keyword_async", r"\bawait\b": "keyword_await", r"\bwith\b": "keyword_with", r"\blambda\b": "keyword_lambda" }
        static_patterns = { **keywords_map, r"\bPriesty\b": "priesty_keyword", r"\bdef\b": "def_keyword", r"\bclass\b": "class_keyword", r"\b(" + "|".join(self.builtin_list) + r")\b": "builtin_function", r"\b(" + "|".join(self.exception_list) + r")\b": "exception_type", r"[(){}[\]]": "bracket_tag", r"\b(__init__|__str__|__repr__)\b": "dunder_method" }
        
        for pattern, tag in static_patterns.items():
            for match in re.finditer(pattern, content):
                if not self._is_inside_tag(match.start(), ("comment_tag", "string_literal", "standard_library_module", "custom_import")):
                    self._apply_tag(tag, match.start(), match.end())

        # Pass 4: Standard lib member access (e.g., os.path)
        for alias, source in self.imported_aliases.items():
            base_source = source.split('.')[0]
            if base_source in self.standard_libraries:
                for m in re.finditer(r"\b" + re.escape(alias) + r"\.([\w]+)", content):
                    if not self._is_inside_tag(m.start(1), ("comment_tag", "string_literal")):
                        self._apply_tag("standard_library_function", m.start(1), m.end(1))
        
        # Pass 5: Numbers
        for match in re.finditer(r'\b\d+(\.\d*)?([eE][+-]?\d+)?\b', content):
            if not self._is_inside_tag(match.start(), ("comment_tag", "string_literal")):
                self._apply_tag("number_literal", match.start(), match.end())

    def _parse_imports(self, content):
        self.imported_aliases.clear()
        # import module, module as alias
        for match in re.finditer(r"^\s*import\s+([^\n]+)", content, re.MULTILINE):
            modules_str = match.group(1).strip()
            modules_str = modules_str.split('#')[0].strip()
            for part in re.split(r'\s*,\s*', modules_str):
                if ' as ' in part:
                    real, alias = re.split(r'\s+as\s+', part, 1)
                    self.imported_aliases[alias.strip()] = real.strip()
                else:
                    part = part.strip()
                    self.imported_aliases[part] = part
        # from module import name, name as alias
        for match in re.finditer(r"^\s*from\s+([\w.]+)\s+import\s+([^\n]+)", content, re.MULTILINE):
            source = match.group(1).strip()
            names_str = match.group(2).strip().split('#')[0].strip().replace('\\', '')
            
            if names_str.startswith('(') and names_str.endswith(')'):
                names_str = names_str[1:-1]

            for part in re.split(r'\s*,\s*', names_str):
                part = part.strip()
                if not part: continue
                if ' as ' in part:
                    real, alias = re.split(r'\s+as\s+', part, 1)
                    self.imported_aliases[alias.strip()] = f"{source}.{real.strip()}"
                else:
                    self.imported_aliases[part] = f"{source}.{part}"


    def _apply_tag(self, tag_name, start_offset, end_offset):
        try:
            self.text_area.tag_add(tag_name, f"1.0 + {start_offset} chars", f"1.0 + {end_offset} chars")
        except tk.TclError: pass

    def _is_inside_tag(self, offset, tag_names):
        if isinstance(tag_names, str): tag_names = (tag_names,)
        current_tags = self.text_area.tag_names(f"1.0 + {offset} chars")
        return any(tag in current_tags for tag in tag_names)

    def _proactive_syntax_check(self):
        if not self.proactive_errors_active:
            self.clear_error_highlight()
            if self.error_console: self.error_console.clear()
            return

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
            
            error_title = f"Syntax Error: {e.msg}"
            self.highlight_syntax_error(e.lineno or 1, error_title)
            
            if self.error_console:
                file_display_name = os.path.basename(self.file_path) if self.file_path else "<current editor>"
                error_details = f"File: {file_display_name}\nLine {e.lineno}, Column {e.offset or 0}\n\n{e.text.strip()}\n{' ' * (e.offset - 1 if e.offset else 0)}^" #type: ignore
                self.error_console.display_error(error_title, error_details)
        except Exception as e:
            if self.error_console:
                self.error_console.display_error(f"Proactive Check Error: {type(e).__name__}", str(e))