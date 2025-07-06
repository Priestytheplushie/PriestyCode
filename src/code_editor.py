# code_editor.py

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import re
import ast
import os
import inspect
import keyword

class ClassAttributeVisitor(ast.NodeVisitor):
    """An AST visitor specifically for finding 'self.attribute' assignments and method defs."""
    def __init__(self):
        self.attributes = set()

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if (isinstance(target, ast.Attribute) and
                isinstance(target.value, ast.Name) and target.value.id == 'self'):
                self.attributes.add(target.attr)
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.attributes.add(node.name)
        self.generic_visit(node)

class CodeAnalyzer:
    """Parses Python code using AST to understand its global structure."""
    def __init__(self):
        self.tree = None
        self.definitions = {}

    def analyze(self, code):
        """Analyzes code, using a fault-tolerant method to generate an AST."""
        self.definitions.clear()
        
        temp_code = code
        parsed_tree = None
        for _ in range(10): # Limit attempts
            try:
                parsed_tree = ast.parse(temp_code)
                break 
            except SyntaxError as e:
                if e.lineno is None: break
                lines = temp_code.splitlines()
                if 0 < e.lineno <= len(lines):
                    error_line = lines[e.lineno - 1]
                    indent = len(error_line) - len(error_line.lstrip())
                    lines[e.lineno - 1] = " " * indent + "pass"
                    temp_code = "\n".join(lines)
                else: break
            except Exception: break
        
        self.tree = parsed_tree
        if self.tree:
            for node in ast.walk(self.tree):
                for child in ast.iter_child_nodes(node):
                    child.parent = node #type: ignore
            self._traverse(self.tree)

    def _traverse(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docstring = ast.get_docstring(node) or f"User-defined {type(node).__name__.replace('Def', '').lower()}."
            self.definitions[node.name] = {
                'type': 'class' if isinstance(node, ast.ClassDef) else 'function',
                'docstring': docstring,
                'lineno': node.lineno
            }
        for child in ast.iter_child_nodes(node):
            self._traverse(child)

    def get_scope_context(self, line_number: int, code_text: str):
        """
        Determines the current logical scope by robustly scanning upwards from the
        given line number, correctly identifying the outermost relevant scope.
        """
        lines = code_text.splitlines()
        if not (0 < line_number <= len(lines)):
            return None, None

        # Start from the current line and find its indentation
        try:
            start_line_index = line_number - 1
            while start_line_index > 0 and not lines[start_line_index].strip():
                start_line_index -= 1
            
            current_indent = len(lines[start_line_index]) - len(lines[start_line_index].lstrip(' '))
        except IndexError:
            return None, None
        
        # Find the hierarchy of parent blocks by their indentation
        block_starters = []
        last_indent = current_indent
        for i in range(start_line_index, -1, -1):
            line = lines[i]
            stripped_line = line.strip()
            if not stripped_line:
                continue
            
            line_indent = len(line) - len(line.lstrip(' '))
            if line_indent < last_indent:
                block_starters.append({'line_index': i, 'indent': line_indent, 'text': stripped_line})
                last_indent = line_indent
        
        # Determine the primary context from the hierarchy
        for block in block_starters:
            text = block['text']
            if text.startswith('class '):
                return 'class', block['line_index'] + 1
            
            if text.startswith(('def ', 'async def ')):
                continue

            if text.startswith(('for ', 'while ', 'async for ')):
                return 'loop_body', block['line_index'] + 1
            
            if text.startswith('try:'):
                return 'try', block['line_index'] + 1
        
        if block_starters and block_starters[0]['text'].startswith(('def ', 'async def ')):
            return 'function', block_starters[0]['line_index'] + 1

        return 'global_scope', 0


    def get_definitions(self):
        return self.definitions

    def get_scope_completions(self, line_number):
        if not self.tree: return []
        visitor = ScopeVisitor(line_number)
        visitor.visit(self.tree)
        return visitor.get_completions()


class ScopeVisitor(ast.NodeVisitor):
    """
    Traverses the AST to find all variables in the lexical scope of a given line.
    It will only suggest global variables inside a function if they are explicitly
    declared with the 'global' keyword.
    """
    def __init__(self, target_line):
        self.target_line = target_line
        self.scopes = [{'variables': {}, 'declared_globals': set()}] # Global scope at index 0
        self.final_completions = []
        self.completions_found = False

    def get_completions(self):
        return self.final_completions

    def _is_in_node_scope(self, node):
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', 0) or getattr(node.body[-1], 'end_lineno', node.body[-1].lineno) if hasattr(node, 'body') and node.body else start_line
        return start_line <= self.target_line <= end_line

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        if not self.completions_found:
            for name, info in self.scopes[0]['variables'].items():
                self.final_completions.append({**info, 'label': name, 'scope': 'Global Variable'})

    def visit_FunctionDef(self, node: ast.FunctionDef):
        in_this_scope = self._is_in_node_scope(node)
        self.scopes.append({'variables': {}, 'declared_globals': set()})

        for arg in node.args.args:
            if arg.lineno < self.target_line:
                self.scopes[-1]['variables'][arg.arg] = {'lineno': arg.lineno, 'scope': 'Parameter'}

        self.generic_visit(node)

        if in_this_scope and not self.completions_found:
            visible_vars = {}
            # Add explicitly declared global variables
            for name in self.scopes[-1]['declared_globals']:
                if name in self.scopes[0]['variables']:
                    visible_vars[name] = {**self.scopes[0]['variables'][name], 'scope': 'Global Variable'}
            # Add local variables and params, overwriting globals if names conflict
            visible_vars.update(self.scopes[-1]['variables'])
            
            for name, info in visible_vars.items():
                self.final_completions.append({**info, 'label': name})
            
            self.completions_found = True
        
        self.scopes.pop()

    def visit_Global(self, node: ast.Global):
        if node.lineno < self.target_line:
            for name in node.names:
                self.scopes[-1]['declared_globals'].add(name)
        self.generic_visit(node)

    def _add_variable(self, name, lineno, scope_name):
        if lineno < self.target_line:
            self.scopes[-1]['variables'][name] = {'lineno': lineno, 'scope': scope_name}

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                scope_name = 'Global Variable' if len(self.scopes) == 1 else 'Local Variable'
                self._add_variable(target.id, node.lineno, scope_name)
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        for target_node in ast.walk(node.target):
            if isinstance(target_node, ast.Name):
                scope_name = 'Global Variable' if len(self.scopes) == 1 else 'Local Variable'
                self._add_variable(target_node.id, node.lineno, scope_name)
        self.generic_visit(node)
        
    def visit_With(self, node: ast.With):
        for item in node.items:
            if item.optional_vars:
                for target_node in ast.walk(item.optional_vars):
                    if isinstance(target_node, ast.Name):
                        scope_name = 'Global Variable' if len(self.scopes) == 1 else 'Local Variable'
                        self._add_variable(target_node.id, node.lineno, scope_name)
        self.generic_visit(node)


class AutocompleteManager:
    def __init__(self, editor_instance, icons=None):
        self.editor = editor_instance
        self.text_area = editor_instance.text_area
        self.icons = icons if icons is not None else {}
        self.current_word_for_preview = ""
        self.window = tk.Toplevel(self.text_area)
        self.window.wm_overrideredirect(True)
        self.window.withdraw()
        main_frame = tk.Frame(self.window, bg="#555555", borderwidth=1, relief="solid")
        main_frame.pack(fill="both", expand=True)
        self.style = ttk.Style()
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL, style='Autocomplete.TPanedwindow')
        self.paned_window.pack(fill="both", expand=True)
        list_frame = tk.Frame(self.paned_window, bg="#3C3C3C")
        self.tree = ttk.Treeview(list_frame, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.paned_window.add(list_frame, weight=2)
        
        preview_outer_frame = tk.Frame(self.paned_window, bg="#2B2B2B")
        self.preview_text = tk.Text(preview_outer_frame, wrap="word", bg="#2B2B2B", fg="white",font=("Consolas", 9), state="disabled", borderwidth=0,highlightthickness=0, spacing1=2, spacing3=2)
        self.preview_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.context_separator = ttk.Separator(preview_outer_frame, orient=tk.HORIZONTAL)
        self.context_label = tk.Label(preview_outer_frame, text="", bg="#2B2B2B", fg="#AAAAAA", font=("Consolas", 8), justify=tk.LEFT)

        self.preview_text.tag_config("type", foreground="#AAAAAA")
        self.preview_text.tag_config("label", foreground="white", font=("Consolas", 9, "bold"))
        self.preview_text.tag_config("detail", foreground="#AAAAAA")
        self.preview_text.tag_config("code_preview", foreground="#B4B4B4", background="#222222", font=("Consolas", 9), relief="sunken", borderwidth=1, lmargin1=10, lmargin2=10, spacing1=4, spacing3=4)
        self.preview_text.tag_config("preview_match_highlight", font=("Consolas", 9, "bold", "underline"))
        self.paned_window.add(preview_outer_frame, weight=3)
        
        self.completions = []
        self._configure_treeview()

    def _configure_treeview(self):
        self.style.configure('Autocomplete.TPanedwindow', sashwidth=2, background="#3C3C3C")
        font_name = "Segoe UI Symbol" if os.name == 'nt' else "Arial"
        self.style.configure("Custom.Treeview", background="#3C3C3C", foreground="white",
                             fieldbackground="#3C3C3C", borderwidth=0, rowheight=22,
                             font=(font_name, 10))
        self.style.map('Custom.Treeview', background=[('selected', '#555555')])
        self.style.layout("Custom.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        self.tree.config(style="Custom.Treeview")
        self.tree.heading('#0', text='')
        self.tree.tag_configure('variable', foreground='#80D0FF')
        self.tree.tag_configure('attribute', foreground='#80D0FF') 
        self.tree.tag_configure('snippet', foreground='#80D0FF')
        self.tree.tag_configure('keyword', foreground='#FFFFFF')
        self.tree.tag_configure('constant', foreground='#FFA500')
        self.tree.tag_configure('function', foreground='#A3E8A3')
        self.tree.tag_configure('method', foreground='#A3E8A3')
        self.tree.tag_configure('constructor', foreground='#C586C0')
        self.tree.tag_configure('class', foreground='#4EC9B0')
        self.tree.tag_configure('module', foreground='#FFD700')
        self.tree.tag_configure('text', foreground='#999999') 
        self.tree.bind('<<TreeviewSelect>>', self.update_preview)
        self.tree.bind('<Return>', self.confirm_selection)
        self.tree.bind('<Tab>', self.confirm_selection)
        self.tree.bind('<Double-1>', self.confirm_selection)
        
    def show(self, completions, current_word):
        bbox = self.editor.text_area.bbox(tk.INSERT)
        if not completions or not bbox: self.hide(); return
        
        self.completions = completions
        self.current_word_for_preview = current_word
        self.tree.delete(*self.tree.get_children())

        for i, item in enumerate(completions):
            item_type = item.get('type', 'variable')
            symbol = self.icons.get(item_type, ' ')
            self.tree.insert('', 'end', iid=i, text=f" {symbol} {item['label']}", tags=(item_type,))

        self.update_preview()
        self.window.update_idletasks()
        
        bbox_info = self.preview_text.dlineinfo("end-1c")
        required_height = bbox_info[1] + bbox_info[3] + 10 if bbox_info else 100
        if self.context_label.winfo_ismapped():
            required_height += self.context_label.winfo_height() + self.context_separator.winfo_height()

        list_height = min(len(completions), 10) * 22 + 6
        new_height = max(list_height, required_height)
        new_height = min(new_height, 400)

        if not self.window.winfo_viewable():
            x, y, _, h = bbox
            x += self.text_area.winfo_rootx(); y += self.text_area.winfo_rooty() + h
            self.window.geometry(f"550x{new_height}+{x}+{y}")
            self.window.deiconify(); self.window.lift()
        else:
            current_x, current_y = self.window.winfo_x(), self.window.winfo_y()
            self.window.geometry(f"550x{new_height}+{current_x}+{current_y}")
        
        if self.tree.get_children():
            self.tree.selection_set('0')
            self.tree.focus('0')

    def hide(self):
        self.editor.clear_context_highlight()
        self.window.withdraw()
        
    def is_visible(self): return self.window.winfo_viewable()
    
    def update_preview(self, event=None):
        self.editor.clear_context_highlight()
        self.context_label.pack_forget()
        self.context_separator.pack_forget()
        selected_ids = self.tree.selection()
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        if selected_ids:
            try:
                selected_index = int(selected_ids[0])
                item = self.completions[selected_index]
            except (ValueError, IndexError):
                self.preview_text.config(state="disabled")
                return
            
            # Use item's 'source' for the primary label, e.g., (Global Variable)
            source_text_type = item.get('source', 'Suggestion')
            source_text = 'Text' if source_text_type == 'text' else source_text_type
            
            detail = item.get('detail', '')
            
            self.preview_text.insert("end", f"({source_text}) ", "type")
            label = item.get('label', '')
            match_len = len(self.current_word_for_preview)
            if self.current_word_for_preview and label.lower().startswith(self.current_word_for_preview.lower()):
                self.preview_text.insert("end", label[:match_len], "preview_match_highlight")
                self.preview_text.insert("end", label[match_len:] + "\n", "label")
            else:
                self.preview_text.insert("end", f"{label}\n", "label")

            if detail:
                self.preview_text.insert("end", "-----------------\n", "detail")
                if '[code]' in detail:
                    parts = detail.split('[code]', 1)
                    description = parts[0].strip()
                    code_part = parts[1].replace('[/code]', '').strip()
                    if description: self.preview_text.insert("end", description + "\n\n", "detail")
                    if code_part: self.preview_text.insert("end", code_part, "code_preview")
                else:
                    self.preview_text.insert("end", detail, "detail")
            
            # Use context_info for the bottom label and highlighting
            context_info = item.get('context_info')
            if context_info:
                self.context_separator.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(5,0))
                self.context_label.config(text=f"Info: {context_info['message']}")
                self.context_label.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(0,5))
                self.editor.highlight_context_line(context_info['line'])

        self.preview_text.config(state="disabled")

    def confirm_selection(self, event=None):
        if not self.is_visible(): return 'break'
        selected_ids = self.tree.selection()
        if not selected_ids: return 'break'
        
        if event and event.keysym == 'Tab':
            self.editor.just_completed_with_tab = True

        try:
            selected_index = int(selected_ids[0])
            item = self.completions[selected_index]
        except (ValueError, IndexError):
            return 'break'
        self.editor.perform_autocomplete(item)
        self.hide(); return 'break'
        
    def navigate(self, direction):
        if not self.is_visible(): return
        current_focus = self.tree.focus()
        if not current_focus: 
             if self.tree.get_children():
                self.tree.selection_set('0'); self.tree.focus('0')
             return 'break'
        try:
            current_index = int(current_focus)
            new_index = current_index + direction
            children = self.tree.get_children()
            if 0 <= new_index < len(children):
                self.tree.selection_set(str(new_index))
                self.tree.focus(str(new_index))
                self.tree.see(str(new_index))
        except (ValueError, tk.TclError):
             if self.tree.get_children():
                self.tree.selection_set('0'); self.tree.focus('0')
        return 'break'
class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, autocomplete_icons=None, 
                 autoindent_var=None, tooltips_var=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B")
        self.error_console = error_console
        self.last_action_was_auto_feature = False
        self.last_cursor_pos_before_auto_action = None
        self.last_auto_action_details = None
        self.autocomplete_active = True
        self.proactive_errors_active = True
        self.autocomplete_dismissed_word = None
        self.manual_trigger_active = False
        self.just_completed_with_tab = False
        # Snippet session state
        self.active_snippet_session = False
        self.snippet_placeholders = []
        self.current_placeholder_index = -1
        self.snippet_exit_point = None
        
        self.imported_aliases = {}
        self.code_analyzer = CodeAnalyzer()
        self.autoindent_var = autoindent_var
        self.tooltips_var = tooltips_var
        self.line_error_messages = {}

        self.CONTEXT_DISPLAY_NAMES = {
            "loop_body": "Loop",
            "class": "Class",
            "function": "Function",
            "global_scope": "Global Scope",
            "try": "Try Block"
        }
        
        self.VARIABLE_SCOPE_DESCRIPTIONS = {
            "Global Variable": "A variable defined at the top level of the module.",
            "Local Variable": "A variable defined within the current function.",
            "Parameter": "A variable passed as an argument to the current function."
        }

        self.editor_frame = tk.Frame(self, bg="#2B2B2B")
        self.editor_frame.pack(fill="both", expand=True)
        self.linenumbers = tk.Text(self.editor_frame, width=4, padx=3, takefocus=0, border=0, background="#2B2B2B", foreground="#888888", state="disabled", wrap="none", font=("Consolas", 10))
        self.linenumbers.pack(side="left", fill="y")
        self.text_area = scrolledtext.ScrolledText(self.editor_frame, wrap="word", bg="#2B2B2B", fg="white", insertbackground="white", selectbackground="#4E4E4E", font=("Consolas", 10), undo=True)
        self.text_area.pack(side="right", fill="both", expand=True)
        self.tooltip_window = tk.Toplevel(self.text_area)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_withdraw()
        self.tooltip_label = tk.Label(self.tooltip_window, text="", justify='left', background="#3C3C3C", foreground="white", relief='solid', borderwidth=1, wraplength=400, font=("Consolas", 9), padx=4, pady=2)
        self.tooltip_label.pack(ipadx=1)

        self.autocomplete_icons = {
            'snippet': '▶', 'keyword': '🝰', 'function': 'ƒ', 'method': '𝘮',
            'constructor': '⊕', 'constant': 'π', 'variable': 'ⓥ', 'module': '📦',
            'class': '🅒', 'attribute': 'ⓐ', 'text': '🗛'
        }
        self.autocomplete_manager = AutocompleteManager(self, icons=self.autocomplete_icons)
        self.file_path: str | None = None
        self._configure_autocomplete_data()
        self._configure_tags_and_tooltips()
        self.text_area.bind("<Configure>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<<Modified>>", self._on_text_modified)
        self.text_area.bind("<MouseWheel>", self._on_mouse_scroll)
        self.text_area.bind("<Button-4>", self._on_mouse_scroll)
        self.text_area.bind("<Button-5>", self._on_mouse_scroll)
        self.text_area.bind("<Button-1>", self._on_click)
        self.text_area.bind("<Return>", self._on_return_key)
        self.text_area.bind("<Tab>", self._on_tab)
        self.text_area.bind("<BackSpace>", self._on_backspace)
        self.text_area.bind("<Control-BackSpace>", self._on_ctrl_backspace)
        self.text_area.bind("(", lambda event: self._auto_complete_brackets(event, '(', ')', show_signature=True))
        self.text_area.bind("[", lambda event: self._auto_complete_brackets(event, '[', ']'))
        self.text_area.bind("{", lambda event: self._auto_complete_brackets(event, '{', '}'))
        self.text_area.bind('"', lambda event: self._auto_complete_brackets(event, '"', '"'))
        self.text_area.bind("'", lambda event: self._auto_complete_brackets(event, "'", "'"))
        self.text_area.bind(".", self._on_dot_key)
        self.text_area.bind("<Escape>", self._on_escape)
        self.text_area.bind("<Up>", self._on_arrow_up)
        self.text_area.bind("<Down>", self._on_arrow_down)
        self.text_area.bind("<Control-space>", self._on_manual_autocomplete_trigger)
        self.text_area.bind("<Control-j>", self._on_manual_autocomplete_trigger)
        self.text_area.edit_modified(False)
        self.apply_syntax_highlighting()

    def set_font_size(self, size: int):
        new_font = ("Consolas", size)
        self.text_area.config(font=new_font)
        self.linenumbers.config(font=new_font)
        ac_preview_font = ("Consolas", max(8, size - 1))
        ac_preview_bold_font = ("Consolas", max(8, size - 1), "bold", "underline")
        ac_context_font = ("Consolas", max(7, size-2))
        self.autocomplete_manager.preview_text.config(font=ac_preview_font)
        self.autocomplete_manager.preview_text.tag_config("label", font=("Consolas", max(8, size - 1), "bold"))
        self.autocomplete_manager.preview_text.tag_config("preview_match_highlight", font=ac_preview_bold_font)
        self.autocomplete_manager.context_label.config(font=ac_context_font)
        tooltip_font = ("Consolas", max(8, size - 1))
        self.tooltip_label.config(font=tooltip_font)
        self.update_line_numbers()
        
    def set_file_path(self, path: str):
        self.file_path = path

    def set_proactive_error_checking(self, is_active: bool):
        self.proactive_errors_active = is_active
        if not is_active: self.clear_error_highlight()
        else: self._proactive_syntax_check()
    
    def _class_has_init(self) -> bool:
        """Checks if the class currently containing the cursor already has an __init__ method."""
        try:
            current_line_num = int(self.text_area.index(tk.INSERT).split('.')[0])
            all_code = self.text_area.get("1.0", "end-1c")
            lines = all_code.splitlines()

            # Find the start of the current class
            class_start_line, class_indent = -1, -1
            for i in range(current_line_num -1, -1, -1):
                line = lines[i]
                if line.strip().startswith('class '):
                    indent_match = re.match(r'^(\s*)', line)
                    if indent_match:
                        current_class_indent = len(indent_match.group(1))
                        current_cursor_line_indent = len(lines[current_line_num-1]) - len(lines[current_line_num-1].lstrip())
                        if current_cursor_line_indent > current_class_indent:
                             class_start_line, class_indent = i, current_class_indent
                             break
            
            if class_start_line == -1: return False

            # Extract the code for this class only
            class_lines = []
            for i in range(class_start_line, len(lines)):
                line = lines[i]
                line_indent = len(line) - len(line.lstrip())
                if line.strip() and line_indent <= class_indent and i > class_start_line:
                    break
                class_lines.append(line)
            
            class_code_block = "\n".join(class_lines)
            unindented_code = re.sub(r'^\s{' + str(class_indent) + '}', '', class_code_block, flags=re.MULTILINE)

            tree = ast.parse(unindented_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == '__init__':
                    return True
        except (ValueError, IndexError, SyntaxError):
            return False
        return False

    def _get_self_completions(self):
        all_code = self.text_area.get("1.0", "end-1c")
        lines = all_code.splitlines()
        try:
            current_line_index = int(self.text_area.index(tk.INSERT).split('.')[0]) - 1
        except (ValueError, IndexError): return []
        class_start_line, class_indent = -1, -1
        for i in range(current_line_index, -1, -1):
            line = lines[i]
            if line.strip().startswith('class '):
                indent_match = re.match(r'^(\s*)', line)
                if indent_match: class_start_line, class_indent = i, len(indent_match.group(1)); break
        if class_start_line == -1: return []
        class_lines = []
        for i in range(class_start_line, len(lines)):
            line = lines[i]
            if i > class_start_line:
                line_indent = len(line) - len(line.lstrip(' '))
                if line.strip() and line_indent <= class_indent: break
            if i == current_line_index:
                indent_match = re.match(r'^(\s*)', line)
                indent_str = indent_match.group(1) if indent_match else ""
                class_lines.append(indent_str + "pass")
            else:
                class_lines.append(line)
        class_code_block = "\n".join(class_lines)
        completions = []
        try:
            unindented_code = re.sub(r'^\s{' + str(class_indent) + '}', '', class_code_block, flags=re.MULTILINE)
            if not unindented_code.strip(): unindented_code = "pass"
            tree = ast.parse(unindented_code)
            visitor = ClassAttributeVisitor(); visitor.visit(tree)
            function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            for attr in sorted(list(visitor.attributes)):
                is_method = attr in function_names
                item_type = 'method' if is_method else 'attribute'
                if attr == '__init__':
                    item_type = 'constructor'
                detail_type = 'Method' if is_method else 'Attribute'
                detail = f"{detail_type} of the current class."
                completions.append({'label': attr, 'type': item_type, 'insert': attr, 'detail': detail, 'source': 'Class Member'})
        except SyntaxError: 
            pass 
        return completions

    def _update_autocomplete_display(self, manual_trigger=False):
        if not self.autocomplete_active: self.autocomplete_manager.hide(); return
        if self.active_snippet_session: return # Don't show completions during snippet navigation
        
        insert_index = self.text_area.index(tk.INSERT)
        line_text_before_cursor = self.text_area.get(f"{insert_index} linestart", insert_index)
        stripped_line = line_text_before_cursor.strip()

        # --- Exception Assistance ---
        except_match = re.search(r'^\s*except(?:\s+(.*))?$', stripped_line)
        if except_match:
            captured_text = except_match.group(1) or ""
            partial_word = ""
            if captured_text:
                partial_word = captured_text.split(',')[-1].lstrip().split('(')[-1]

            in_tuple = '(' in captured_text
            completions = []
            for exc_name in self.exception_list:
                if exc_name.lower().startswith(partial_word.lower()):
                    completions.append({
                        'label': exc_name, 
                        'type': 'class', 
                        'source': 'Exception', 
                        'insert': exc_name,
                        'detail': self.exception_tooltips.get(exc_name, "Built-in Exception."),
                        'priority': 2
                    })
                    if not in_tuple:
                        completions.append({
                            'label': f"{exc_name} as e",
                            'type': 'snippet',
                            'source': 'Exception Snippet',
                            'insert': f"{exc_name} as e:",
                            'detail': f"Catch the {exc_name} and assign it to a variable 'e'.",
                            'priority': 1
                        })
            if completions:
                completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
                self.autocomplete_manager.show(completions, partial_word)
            else:
                self.autocomplete_manager.hide()
            return

        # --- Suppress Autocomplete for Aliases ---
        if re.search(r'\bas\s+\w*$', stripped_line):
            self.autocomplete_manager.hide()
            return

        # --- Import Assistance ---
        from_import_match = re.match(r'^\s*from\s+([\w\.]+)\s+import(?:\s+(.*))?$', stripped_line)
        if from_import_match:
            module_name = from_import_match.group(1)
            members_text = from_import_match.group(2)
            partial_member = ""
            if members_text is not None:
                partial_member = members_text.split(',')[-1].strip()
            completions = []
            if module_name in self.standard_libraries:
                lib_members = self.standard_libraries.get(module_name, {}).get('members', [])
                for member in lib_members:
                    if member.lower().startswith(partial_member.lower()):
                        item_type = 'function'
                        if member and member[0].isupper(): item_type = 'class'
                        if member in self.standard_libraries: item_type = 'module'
                        completions.append({'label': member, 'type': item_type, 'insert': member, 'detail': f'Member of the "{module_name}" module.'})
            if completions:
                completions.sort(key=lambda x: x['label'])
                self.autocomplete_manager.show(completions, partial_member)
            else: self.autocomplete_manager.hide()
            return

        import_match = re.match(r'^\s*(?:import|from)\s+(?!.*\bas\b)([\w.]*)$', stripped_line)
        if import_match or stripped_line in ['import', 'from']:
            partial_module = ""
            if import_match: partial_module = import_match.group(1)
            completions = []
            for name, data in self.standard_libraries.items():
                if name.lower().startswith(partial_module.lower()):
                    completions.append({'label': name, 'type': 'module', 'insert': name, 'detail': data.get('tooltip', 'Standard library module.')})
            if completions:
                completions.sort(key=lambda x: x['label'])
                self.autocomplete_manager.show(completions, partial_module)
            else: self.autocomplete_manager.hide()
            return
        # --- End Import Assistance ---

        try:
            dot_match = re.search(r'(\b[\w_]+)\.([\w_]*)$', line_text_before_cursor)
            if dot_match:
                base_word, partial_member = dot_match.group(1), dot_match.group(2)
                completions = []
                partial_member_lower = partial_member.lower()
                if base_word == 'self':
                    all_self_members = self._get_self_completions()
                    for member in all_self_members:
                        if member['label'].lower().startswith(partial_member_lower):
                            member['priority'] = 1
                            completions.append(member)
                else:
                    real_module = self.imported_aliases.get(base_word)
                    base_module_name = real_module.split('.')[0] if real_module else None
                    if base_module_name and base_module_name in self.standard_libraries:
                        for member_name in self.standard_libraries.get(base_module_name, {}).get('members', []):
                            if member_name.lower().startswith(partial_member_lower):
                                completions.append({'label': member_name, 'type': 'function', 'insert': member_name, 'detail': self.standard_library_function_tooltips.get(f"{base_module_name}.{member_name}", "Standard library member."), 'source': 'Standard Library Member', 'priority': 1})
                completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
                self.autocomplete_manager.show(completions, partial_member)
                return
        except (tk.TclError, ValueError):
            self.autocomplete_manager.hide()
            return

        # --- REVISED CURRENT WORD LOGIC ---
        try:
            current_word = ""
            # Check for decorator pattern first: @ followed by zero or more word characters
            decorator_match = re.search(r'@\w*$', line_text_before_cursor)
            if decorator_match:
                current_word = decorator_match.group(0)
            else:
                # Fallback to standard word logic
                current_word = self.text_area.get("insert-1c wordstart", "insert")
            
            current_line_num = int(self.text_area.index(tk.INSERT).split('.')[0])
        except (tk.TclError, ValueError):
            self.autocomplete_manager.hide()
            return
        
        if self.autocomplete_dismissed_word is not None and not manual_trigger:
            if current_word == self.autocomplete_dismissed_word: return
            else: self.autocomplete_dismissed_word = None

        all_text = self.text_area.get("1.0", tk.END)
        completions, labels_so_far = [], set()
        current_word_lower = current_word.lower()

        def is_module_imported(module_name):
            if not module_name: return True
            for real_name in self.imported_aliases.values():
                if real_name.split('.')[0] == module_name:
                    return True
            return False

        def add_completion(item, priority):
            label = item.get('label')
            if not label:
                return

            if item.get('requires_import') and not is_module_imported(item['requires_import']):
                return

            should_add = False
            if manual_trigger:
                should_add = True
            elif current_word and label.lower().startswith(current_word_lower):
                should_add = True
            elif current_word and item.get('match') and item['match'].lower().startswith(current_word_lower):
                should_add = True

            if should_add and label.lower() not in labels_so_far:
                item['priority'] = priority
                labels_so_far.add(label.lower())
                completions.append(item)

        scope_context, context_line = self.code_analyzer.get_scope_context(current_line_num, all_text)

        # --- GATHERING LOGIC (CONTEXT-AWARE FOR ALL SNIPPETS) ---

        # Priority 0: Context-Aware Snippets
        for s in self.snippets:
            s_context = s.get('context')
            if s_context:
                is_correct_context = False
                if s_context == scope_context:
                    is_correct_context = True
                
                if is_correct_context:
                    # Special check for __init__ snippet
                    if s['label'] == 'def (__init__)' and self._class_has_init():
                        continue # Skip if __init__ already exists

                    if context_line is not None and scope_context is not None:
                        display_name = self.CONTEXT_DISPLAY_NAMES.get(scope_context)
                        if display_name:
                            context_message = f"Suggested for {display_name} starting on line {context_line}"
                            context_info = {'message': context_message, 'line': context_line, 'context_name': scope_context}
                            add_completion({**s, 'context_info': context_info}, 0)

        # Priority 1: In-Scope Variables, Parameters, and Class Members
        if self.code_analyzer.tree:
            in_scope_variables = self.code_analyzer.get_scope_completions(current_line_num)
            for var_info in in_scope_variables:
                scope_name = var_info.get('scope', 'Variable')
                line_num = var_info.get('lineno', 1)
                detail = self.VARIABLE_SCOPE_DESCRIPTIONS.get(scope_name, "A variable in the current scope.")
                context_info = {'message': f"Defined on line {line_num}", 'line': line_num}
                add_completion({'label': var_info['label'], 'type': 'variable', 'insert': var_info['label'], 'detail': detail, 'source': scope_name, 'context_info': context_info}, 1)
        
        # Priority 2: User-Defined Functions & Classes
        user_defs = self.code_analyzer.get_definitions()
        for name, info in user_defs.items():
            item_type = info['type']
            if item_type == 'function':
                lines = all_text.splitlines()
                if info['lineno'] > 1 and info['lineno'] -2 < len(lines):
                  for i in range(info['lineno'] - 2, -1, -1):
                      if lines[i].strip().startswith('class '):
                          item_type = 'method'; break
            if name == '__init__': item_type = 'constructor'
            add_completion({'label': name, 'type': item_type, 'insert': name, 'detail': info['docstring'], 'source': 'User-defined'}, 2)

        # Priority 3: General Snippets (Promoted)
        for s in self.snippets:
            if not s.get('context'):
                 add_completion(s, 3)

        # Priority 4: Keywords (Demoted)
        for k in self.raw_keywords:
            if k['type'] == 'keyword':
                add_completion(k, 4)

        # Priority 5: Built-in Functions & Constants
        for k in self.raw_keywords:
            if k['type'] in ('function', 'constant'):
                add_completion(k, 5)

        # Priority 6: Standard Library Modules
        for m, data in self.standard_libraries.items():
            add_completion({'label': m, 'type': 'module', 'insert': m, 'detail': data.get('tooltip', 'Standard library module.'), 'source': 'Standard Library'}, 6)
        
        completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
        if completions:
            self.autocomplete_manager.show(completions, current_word)
        else:
            self.autocomplete_manager.hide()

    def perform_autocomplete(self, item):
        self._end_snippet_session() # End any previous session
        self.text_area.edit_separator()
        
        insert_index_before = self.text_area.index(tk.INSERT)
        current_line_content = self.text_area.get(f"{insert_index_before} linestart", f"{insert_index_before} lineend")
        indent_match = re.match(r'^(\s*)', current_line_content)
        indentation = indent_match.group(1) if indent_match else ""

        current_line_before_cursor = self.text_area.get(f"{insert_index_before} linestart", insert_index_before)

        # --- Placeholder Parsing (Robust Two-Pass Method) ---
        raw_insert_text = item['insert']
        placeholders = []
        has_exit_point = '$0' in raw_insert_text
        
        # Pass 1: Remove the exit point marker to not interfere with text search
        raw_insert_text = raw_insert_text.replace('$0', '')

        # Pass 2: Find all numbered placeholders
        numbered_placeholder_pattern = re.compile(r'\$\{(\d+):(.+?)\}')
        for match in numbered_placeholder_pattern.finditer(raw_insert_text):
            # This is now safe, int() will not receive None
            order = int(match.group(1))
            text = match.group(2)
            placeholders.append({'order': order, 'text': text})
        
        # Clean the insert string by replacing placeholder syntax with just the text
        text_to_insert = numbered_placeholder_pattern.sub(r'\2', raw_insert_text)
        
        # Sort placeholders by their tab-stop order
        placeholders.sort(key=lambda p: p['order'])

        # --- Indentation Logic ---
        if '\n' in text_to_insert:
            lines = text_to_insert.split('\n')
            indented_lines = [lines[0]] + [indentation + line for line in lines[1:]]
            text_to_insert = '\n'.join(indented_lines)
        
        replace_start_index_str = "insert-1c wordstart"
        decorator_match = re.search(r'@\w*$', current_line_before_cursor)
        if decorator_match:
             replace_start_index_str = f"insert - {len(decorator_match.group(0))}c"
        else:
            try:
                dot_match = re.search(r'\.([\w_]*)$', current_line_before_cursor)
                if dot_match:
                    start_offset = dot_match.start(1)
                    line_start_index = self.text_area.index("insert linestart")
                    replace_start_index_str = f"{line_start_index} + {start_offset} chars"
            except (tk.TclError, IndexError):
                 pass
        
        # --- Insertion ---
        try:
            start_index = self.text_area.index(replace_start_index_str)
            self.text_area.delete(start_index, insert_index_before)
            self.text_area.insert(start_index, text_to_insert)
            insertion_start_index = start_index
        except tk.TclError:
             self.text_area.insert(insert_index_before, text_to_insert)
             insertion_start_index = insert_index_before

        # --- Start Snippet Session if placeholders exist ---
        if placeholders:
            self.after_idle(lambda: self._start_snippet_session(placeholders, insertion_start_index, has_exit_point))

        self.last_auto_action_details = {'start': insertion_start_index, 'end': self.text_area.index(tk.INSERT)}
        self.last_action_was_auto_feature = True
        self.text_area.focus_set()
        self.after_idle(self._on_content_changed)

    def _start_snippet_session(self, placeholders, search_start_index, has_exit_point):
        """Calculates placeholder positions and jumps to the first one."""
        final_placeholders = []
        current_search_start = search_start_index
        
        end_of_insertion = self.text_area.index(tk.INSERT)
        
        for p in placeholders:
            try:
                start_pos = self.text_area.search(p['text'], current_search_start, stopindex=end_of_insertion, exact=True)
                if start_pos:
                    end_pos = f"{start_pos} + {len(p['text'])}c"
                    final_placeholders.append({'start': start_pos, 'end': end_pos})
                    current_search_start = end_pos
                else:
                    self._end_snippet_session()
                    return
            except tk.TclError:
                self._end_snippet_session()
                return
        
        self.snippet_exit_point = None
        if has_exit_point:
             self.snippet_exit_point = self.text_area.index(end_of_insertion)

        if final_placeholders:
            self.active_snippet_session = True
            self.snippet_placeholders = final_placeholders
            self.current_placeholder_index = -1
            self._jump_to_next_placeholder()

    def _jump_to_next_placeholder(self):
        """Jumps to the next placeholder in the active snippet session."""
        if not self.active_snippet_session:
            return

        self.current_placeholder_index += 1
        if self.current_placeholder_index < len(self.snippet_placeholders):
            placeholder = self.snippet_placeholders[self.current_placeholder_index]
            self.text_area.tag_remove("sel", "1.0", tk.END)
            self.text_area.tag_add("sel", placeholder['start'], placeholder['end'])
            self.text_area.mark_set(tk.INSERT, placeholder['start'])
            self.text_area.see(tk.INSERT)
            self.text_area.focus_set()
        else:
            self._end_snippet_session()

    def _end_snippet_session(self):
        """Ends the active snippet session and resets state."""
        if self.active_snippet_session:
            self.text_area.tag_remove("sel", "1.0", tk.END)
            if self.snippet_exit_point:
                self.text_area.mark_set(tk.INSERT, self.snippet_exit_point)
            elif self.snippet_placeholders:
                 last_placeholder = self.snippet_placeholders[-1]
                 self.text_area.mark_set(tk.INSERT, last_placeholder['end'])
        
        self.active_snippet_session = False
        self.snippet_placeholders = []
        self.current_placeholder_index = -1
        self.snippet_exit_point = None

    def _on_backspace(self, event):
        if self.active_snippet_session and self.text_area.tag_ranges("sel"):
            return
        self._end_snippet_session()
        
        if self.last_action_was_auto_feature and self.last_auto_action_details is None:
            try:
                cursor_index = self.text_area.index(tk.INSERT)
                line_start = self.text_area.index(f"{cursor_index} linestart")
                text_on_line_before_cursor = self.text_area.get(line_start, cursor_index)
                
                if text_on_line_before_cursor and text_on_line_before_cursor.isspace():
                    self.last_action_was_auto_feature = False
                    self.text_area.delete("insert-4c", "insert")
                    self.autocomplete_manager.hide()
                    return "break"
            except tk.TclError:
                pass

            self.last_action_was_auto_feature = False
            try:
                self.text_area.edit_undo()
                if self.last_cursor_pos_before_auto_action:
                    self.text_area.mark_set(tk.INSERT, self.last_cursor_pos_before_auto_action)
            except tk.TclError:
                pass
            self.autocomplete_manager.hide()
            return "break"

        self.last_action_was_auto_feature = False
        self.last_cursor_pos_before_auto_action = None
        
        self.after(50, self._update_autocomplete_display)
        return None
    
    def _on_ctrl_backspace(self, event):
        self._end_snippet_session()
        self.text_area.delete("insert-1c wordstart", "insert")
        self.autocomplete_manager.hide(); return "break"

    def _on_tab(self, event):
        # Consume the flag if it was set by the autocomplete manager
        if self.just_completed_with_tab:
            self.just_completed_with_tab = False
            return "break"

        if self.active_snippet_session:
            self._jump_to_next_placeholder()
            return "break"

        if self.autocomplete_manager.is_visible(): 
            # Manually tell the manager it was a Tab event
            self.autocomplete_manager.confirm_selection(event)
            return "break"
        
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    ")
        return "break"
    
    def _on_return_key(self, event):
        if self.active_snippet_session:
            self._end_snippet_session()
        
        if self.autocomplete_manager.is_visible():
            self.last_auto_action_details = None
            self.last_cursor_pos_before_auto_action = None
            return self.autocomplete_manager.confirm_selection()

        self.autocomplete_dismissed_word = None
        if self.autoindent_var and self.autoindent_var.get():
            self.last_cursor_pos_before_auto_action = self.text_area.index(tk.INSERT)
            self.last_auto_action_details = None
            try:
                cursor_index = self.text_area.index(tk.INSERT)
                char_before = self.text_area.get(f"{cursor_index}-1c")
                char_after = self.text_area.get(cursor_index)
                
                bracket_pairs = {'(': ')', '[': ']', '{': '}'}
                if char_before in bracket_pairs and bracket_pairs[char_before] == char_after:
                    self.text_area.edit_separator()
                    
                    line_start = self.text_area.index(f"{cursor_index} linestart")
                    current_line = self.text_area.get(line_start, f"{cursor_index} lineend")
                    indent_match = re.match(r'^(\s*)', current_line)
                    base_indent = indent_match.group(1) if indent_match else ""
                    
                    inserted_text = f"\n{base_indent}    \n{base_indent}"
                    self.text_area.insert(tk.INSERT, inserted_text)
                    
                    self.last_action_was_auto_feature = True

                    self.text_area.mark_set(tk.INSERT, f"{cursor_index}+{len(base_indent)+5}c")
                    self.after_idle(self._on_content_changed)
                    return "break"
            except tk.TclError:
                pass

            return self._auto_indent(event)
        else:
            self.text_area.insert(tk.INSERT, "\n")
            self.after_idle(self._on_content_changed)
            return "break"
            
    def update_line_numbers(self, event=None):
        self.linenumbers.config(state="normal"); self.linenumbers.delete("1.0", tk.END)
        num_lines_str = self.text_area.index("end-1c").split('.')[0]
        if not num_lines_str.isdigit(): return
        self.linenumbers.insert("1.0", "\n".join(str(i) for i in range(1, int(num_lines_str) + 1)))
        self.linenumbers.config(state="disabled")
        try: self.linenumbers.yview_moveto(self.text_area.yview()[0])
        except tk.TclError: pass

    def _on_content_changed(self, event=None):
        self.update_line_numbers()
        self.code_analyzer.analyze(self.text_area.get("1.0", tk.END))
        self.apply_syntax_highlighting()
        self._proactive_syntax_check()
        
    def _auto_complete_brackets(self, event, open_char, close_char, show_signature=False):
        self._end_snippet_session()
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.last_cursor_pos_before_auto_action = self.text_area.index(tk.INSERT)
        self.last_auto_action_details = None

        if self.text_area.tag_ranges("sel"):
            sel_start, sel_end = self.text_area.index("sel.first"), self.text_area.index("sel.last")
            selected_text = self.text_area.get(sel_start, sel_end)
            self.text_area.delete(sel_start, sel_end)
            self.text_area.insert(sel_start, open_char + selected_text + close_char)
            self.last_action_was_auto_feature = False
        else:
            self.text_area.insert(tk.INSERT, open_char + close_char)
            self.last_action_was_auto_feature = True
            self.text_area.mark_set(tk.INSERT, "insert-1c")

        if show_signature: self.after(20, self._show_signature_help)
        return "break"

    def _auto_indent(self, event):
        self.text_area.edit_separator()
        
        cursor_index = self.text_area.index(tk.INSERT)
        line_number = int(cursor_index.split('.')[0])
        current_line_content = self.text_area.get(f"{line_number}.0", f"{line_number}.end")
        stripped_line = current_line_content.strip()
        
        current_indent_str_match = re.match(r'^(\s*)', current_line_content)
        current_indent_str = current_indent_str_match.group(1) if current_indent_str_match else ""
        
        parent_indent_str = ""
        for i in range(line_number - 1, 0, -1):
            line = self.text_area.get(f"{i}.0", f"{i}.end")
            if line.strip():
                indent_match = re.match(r'^(\s*)', line)
                parent_indent_str = indent_match.group(1) if indent_match else ""
                break
        
        next_line_indent_str = current_indent_str

        # Rule 1: De-dent after a block-ending statement or on a blank line
        if not stripped_line or stripped_line in ('pass', 'break', 'continue') or stripped_line.startswith('return'):
            next_line_indent_str = parent_indent_str
        # Rule 2: Increase indent after a colon
        elif stripped_line.endswith(':'):
            next_line_indent_str += "    "
        
        self.text_area.insert(tk.INSERT, f'\n{next_line_indent_str}')
        
        self.last_action_was_auto_feature = True
        self.after_idle(self._on_content_changed)
        return "break"

    def _apply_error_highlight(self, line_number, error_message, tag):
        self.text_area.tag_add(tag, f"{line_number}.0", f"{line_number}.end")
        self.line_error_messages[line_number] = error_message

    def highlight_runtime_error(self, line_number, error_message):
        self.clear_error_highlight()
        self._apply_error_highlight(line_number, error_message, "reactive_error_line")

    def highlight_handled_exception(self, line_number, error_message):
        self.clear_error_highlight()
        self._apply_error_highlight(line_number, error_message, "handled_exception_line")

    def clear_error_highlight(self):
        for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]:
            self.text_area.tag_remove(tag, "1.0", tk.END)
        self.line_error_messages.clear()

    def apply_syntax_highlighting(self):
        preserved = ("sel", "insert", "current", "reactive_error_line", "proactive_error_line", "handled_exception_line", "context_highlight_line")
        for tag in self.text_area.tag_names():
            if tag not in preserved: self.text_area.tag_remove(tag, "1.0", tk.END)
        content = self.text_area.get("1.0", tk.END)
        for match in re.finditer(r"(#.*)", content): self._apply_tag("comment_tag", match.start(), match.end())
        for pattern in [r"f'''(.*?)'''", r'f"""(.*?)"""', r"'''(.*?)'''", r'"""(.*?)"""']:
            for match in re.finditer(pattern, content, re.DOTALL): 
                if not self._is_inside_tag(match.start(), ("comment_tag",)):
                    self._apply_tag("string_literal", match.start(), match.end())
                    if match.group(0).startswith('f'):
                        for expr in re.finditer(r"\{(.+?)\}", match.group(1)):
                            self._apply_tag("fstring_expression", match.start(1) + expr.start(0), match.start(1) + expr.end(0))
        string_regex = r"""(f?r?|r?f?)'[^'\\\n]*(?:\\.[^'\\\n]*)*'|(f?r?|r?f?)\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\""""
        for m in re.finditer(string_regex, content):
            if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")): self._apply_tag("string_literal", m.start(), m.end())
        self._parse_imports(content)
        
        for egg in self.easter_egg_tooltips.keys():
            if ' ' in egg:
                for m in re.finditer(re.escape(egg), content):
                    if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")):
                        self._apply_tag("easter_egg_import", m.start(), m.end())
            else:
                for m in re.finditer(r"\b" + re.escape(egg) + r"\b", content):
                    if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")):
                        self._apply_tag("easter_egg_import", m.start(), m.end())

        for alias, source in self.imported_aliases.items():
            tag = "standard_library_module" if source.split('.')[0] in self.standard_libraries else "custom_import"
            for m in re.finditer(r"\b" + re.escape(alias) + r"\b", content):
                if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal", "easter_egg_import")): 
                    self._apply_tag(tag, m.start(), m.end())
        
        static_patterns = { r"\bdef\b": "def_keyword", r"\bclass\b": "class_keyword", r"\b(if|else|elif)\b": "keyword_conditional", r"\b(for|while|break|continue)\b": "keyword_loop", r"\b(return|yield)\b": "keyword_return", r"\b(pass|global|nonlocal|del)\b": "keyword_structure", r"\b(import|from|as)\b": "keyword_import", r"\b(try|except|finally|raise|assert)\b": "keyword_exception", r"\b(True|False|None)\b": "keyword_boolean_null", r"\b(and|or|not|in|is)\b": "keyword_logical", r"\b(async|await)\b": "keyword_async", r"\b(with|lambda)\b": "keyword_context", r"\bPriesty\b": "priesty_keyword", r"\bself\b": "self_keyword", r"\b(" + "|".join(self.builtin_list) + r")\b": "builtin_function", r"\b(" + "|".join(self.exception_list) + r")\b": "exception_type", r"[(){}[\]]": "bracket_tag", r"\b(__init__|__str__|__repr__)\b": "dunder_method"}
        for pattern, tag in static_patterns.items():
            for m in re.finditer(pattern, content):
                if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal", "standard_library_module", "easter_egg_import")): self._apply_tag(tag, m.start(), m.end())

        for alias, source in self.imported_aliases.items():
            if source.split('.')[0] in self.standard_libraries:
                for m in re.finditer(r"\b" + re.escape(alias) + r"\.([\w]+)", content):
                    if not self._is_inside_tag(m.start(1), ("comment_tag", "string_literal")): self._apply_tag("standard_library_function", m.start(1), m.end(1))
        for m in re.finditer(r"\bself\.(\w+)\b", content):
            if not self._is_inside_tag(m.start(1), ("comment_tag", "string_literal")): self._apply_tag("self_method_call", m.start(1), m.end(1))
        defs = self.code_analyzer.get_definitions()
        if defs:
            for name, info in defs.items():
                def_tag, usage_tag = ("function_definition", "function_call") if info['type'] == 'function' else ("class_definition", "class_usage")
                for m in re.finditer(r"(?:class|def)\s+(" + re.escape(name) + r")\b", content):
                    if not self._is_inside_tag(m.start(1), ("comment_tag", "string_literal")): self._apply_tag(def_tag, m.start(1), m.end(1))
                for m in re.finditer(r"\b" + re.escape(name) + r"\b", content):
                    if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal", def_tag)): self._apply_tag(usage_tag, m.start(), m.end())
        for m in re.finditer(r'\b(0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|\d+(\.\d*)?([eE][+-]?\d+)?)\b', content):
            if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")): self._apply_tag("number_literal", m.start(), m.end())

    def _parse_imports(self, content):
        self.imported_aliases.clear()
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names: self.imported_aliases[alias.asname or alias.name] = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names: self.imported_aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        except SyntaxError: self._parse_imports_regex(content)

    def _parse_imports_regex(self, content):
        for m in re.finditer(r"^\s*import\s+([^\n]+)", content, re.MULTILINE):
            for part in re.split(r'\s*,\s*', m.group(1).split('#')[0].strip()):
                if ' as ' in part: real, alias = re.split(r'\s+as\s+', part, 1); self.imported_aliases[alias.strip()] = real.strip()
                else: self.imported_aliases[part.strip()] = part.strip()
        for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import\s+([^\n]+)", content, re.MULTILINE):
            source, names_str = m.group(1).strip(), m.group(2).strip().split('#')[0].strip().replace('\\', '')
            if names_str.startswith('(') and names_str.endswith(')'): names_str = names_str[1:-1]
            for part in re.split(r'\s*,\s*', names_str):
                part = part.strip()
                if not part: continue
                if ' as ' in part: real, alias = re.split(r'\s+as\s+', part, 1); self.imported_aliases[alias.strip()] = f"{source}.{real.strip()}"
                else: self.imported_aliases[part] = f"{source}.{part}"

    def _apply_tag(self, tag_name, start_offset, end_offset):
        try: self.text_area.tag_add(tag_name, f"1.0 + {start_offset} chars", f"1.0 + {end_offset} chars")
        except tk.TclError: pass

    def _is_inside_tag(self, offset, tag_names):
        try: return any(tag in self.text_area.tag_names(f"1.0 + {offset} chars") for tag in tag_names)
        except tk.TclError: return False

    def _proactive_syntax_check(self):
        if not self.proactive_errors_active:
            if self.error_console: self.error_console.clear()
            self.clear_error_highlight()
            return

        code_to_check = self.text_area.get("1.0", tk.END)
        self.clear_error_highlight()

        if not code_to_check.strip():
            if self.error_console and hasattr(self.error_console, 'clear'):
                self.error_console.clear(proactive_only=True)
            return

        collected_errors = []
        max_errors = 10
        
        for _ in range(max_errors):
            try:
                ast.parse(code_to_check)
                break 
            except SyntaxError as e:
                try: 
                    cursor_line = int(self.text_area.index(tk.INSERT).split('.')[0])
                    if e.lineno == cursor_line: break
                except (ValueError, IndexError): pass
                
                collected_errors.append(e)
                
                lines = code_to_check.splitlines()
                if e.lineno and e.lineno <= len(lines):
                    error_line = lines[e.lineno - 1]
                    indent = len(error_line) - len(error_line.lstrip())
                    lines[e.lineno - 1] = " " * indent + "pass"
                    code_to_check = "\n".join(lines)
                else: break
            except Exception: break

        if not collected_errors:
            if self.error_console and hasattr(self.error_console, 'clear'):
                self.error_console.clear(proactive_only=True)
            return

        error_list_for_console = []
        for error in collected_errors:
            line = error.lineno or 1
            col = error.offset or 1
            error_title = f"Syntax Error: {error.msg}"
            
            self._apply_error_highlight(line, error_title, "proactive_error_line")
            
            error_line_text = error.text.strip() if error.text else ""
            details = f"File: {self.file_path}\nLine {line}, Column {col}\n\n{error_line_text}\n{' ' * (col - 1)}^"
            
            error_list_for_console.append({
                'title': error_title,
                'details': details,
                'file_path': self.file_path,
                'line': line,
                'col': col
            })

        if self.error_console and hasattr(self.error_console, 'display_errors'):
            self.error_console.display_errors(error_list_for_console, proactive_only=True)

    def _configure_autocomplete_data(self):
        self.keyword_tooltips = {
            'if': "The 'if' keyword is used for conditional execution.", 'elif': "The 'elif' keyword is a contraction of 'else if'.", 'else': "The 'else' keyword catches anything which isn't caught by the preceding clauses.", 'for': "The 'for' keyword is used to iterate over the items of any sequence.", 'while': "The 'while' keyword is used to execute a block of code as long as a condition is true.", 'break': "The 'break' statement terminates the current 'for' or 'while' loop.", 'continue': "The 'continue' statement rejects all the remaining statements in the current iteration of the loop.", 'def': "The 'def' keyword is used to define a function.", 'class': "The 'class' keyword is used to create a new user-defined class.", 'return': "The 'return' statement exits a function, optionally passing back a value.", 'yield': "The 'yield' keyword is used in generator functions.", 'try': "The 'try' keyword starts a block of code that might raise an exception.", 'except': "The 'except' keyword catches exceptions raised in the 'try' block.", 'finally': "The 'finally' clause is always executed before leaving the 'try' statement.", 'with': "The 'with' statement is used to wrap the execution of a block with methods defined by a context manager.", 'as': "The 'as' keyword is used to create an alias.", 'import': "The 'import' statement is used to bring a module or members of a module into the current namespace.", 'from': "The 'from' keyword is used with 'import' to bring specific members of a module into the namespace.", 'pass': "The 'pass' statement is a null operation.", 'assert': "The 'assert' statement is a debugging aid that tests a condition.", 'lambda': "The 'lambda' keyword is used to create small anonymous functions.", 'global': "The 'global' keyword declares that a variable inside a function is global.", 'nonlocal': "The 'nonlocal' keyword is used to work with variables in the nearest enclosing scope.", 'del': "The 'del' statement is used to remove an object reference.", 'in': "The 'in' keyword is a membership operator.", 'is': "The 'is' keyword is an identity operator.", 'and': "Logical AND operator.", 'or': "Logical OR operator.", 'not': "Logical NOT operator.", 'async': "The 'async' keyword is used to declare an asynchronous function.", 'await': "The 'await' keyword is used to pause the execution of a coroutine.", 'self': "Refers to the instance of the class."
        }
        self.builtin_tooltips = {
            'abs': 'abs(x)\n\nReturn the absolute value of a number.', 'all': 'all(iterable)\n\nReturn True if all elements of the iterable are true.', 'any': 'any(iterable)\n\nReturn True if any element of the iterable is true.', 'ascii': 'ascii(object)\n\nReturn a string containing a printable representation of an object.', 'bin': 'bin(x)\n\nConvert an integer number to a binary string prefixed with "0b".', 'bool': 'bool([x])\n\nReturn a Boolean value, i.e., one of True or False.', 'breakpoint': 'breakpoint(*args, **kws)\n\nEnter the debugger at the call site.', 'bytearray': 'bytearray([source[, encoding[, errors]]])\n\nReturn a new array of bytes.', 'bytes': 'bytes([source[, encoding[, errors]]])\n\nReturn a new "bytes" object.', 'callable': 'callable(object)\n\nReturn True if the object argument appears callable, False if not.', 'chr': 'chr(i)\n\nReturn the string representing a character whose Unicode code point is the integer i.', 'classmethod': 'classmethod(function)\n\nTransform a method into a class method.', 'compile': 'compile(source, filename, mode, flags=0, ...)\n\nCompile the source into a code or AST object.', 'complex': 'complex([real[, imag]])\n\nCreate a complex number with the value real + imag*j.', 'delattr': 'delattr(object, name)\n\nDeletes the named attribute from the given object.', 'dict': "dict(**kwarg) -> new dictionary\n\nCreate a new dictionary.", 'dir': 'dir([object])\n\nReturn the list of names in the current local scope or a list of valid attributes for an object.', 'divmod': 'divmod(a, b)\n\nReturn a pair of numbers (a // b, a % b) consisting of their quotient and remainder.', 'enumerate': "enumerate(iterable, start=0)\n\nReturn an enumerate object.", 'eval': 'eval(expression, globals=None, locals=None)\n\nEvaluates the given expression as a Python expression.', 'exec': 'exec(object[, globals[, locals]])\n\nThis function supports dynamic execution of Python code.', 'filter': 'filter(function, iterable)\n\nConstruct an iterator from elements of iterable for which function returns true.', 'float': 'float([x])\n\nConvert a string or a number to a floating point number.', 'format': 'format(value[, format_spec])\n\nConvert a value to a "formatted" representation.', 'frozenset': 'frozenset([iterable])\n\nReturn a new frozenset object, optionally with elements taken from iterable.', 'getattr': 'getattr(object, name[, default])\n\nReturn the value of the named attribute of an object.', 'globals': 'globals()\n\nReturn a dictionary representing the current global symbol table.', 'hasattr': 'hasattr(object, name)\n\nReturn whether the object has an attribute with the given name.', 'hash': 'hash(object)\n\nReturn the hash value of the object (if it has one).', 'help': 'help([object])\n\nInvoke the built-in help system.', 'hex': 'hex(x)\n\nConvert an integer number to a lowercase hexadecimal string prefixed with "0x".', 'id': 'id(object)\n\nReturn the "identity" of an object.', 'input': "input(prompt=None, /)\n\nRead a string from standard input.", 'int': "int(x, base=10) -> integer\n\nConvert a number or string to an integer.", 'isinstance': 'isinstance(object, classinfo)\n\nReturn true if the object argument is an instance of the classinfo argument.', 'issubclass': 'issubclass(class, classinfo)\n\nReturn true if class is a subclass of classinfo.', 'iter': 'iter(object[, sentinel])\n\nReturn an iterator object.', 'len': "len(s)\n\nReturn the length (the number of items) of an object.", 'list': "list(iterable) -> new list\n\nReturn a list whose items are the same and in the same order as iterable's items.", 'locals': 'locals()\n\nReturn a dictionary representing the current local symbol table.', 'map': 'map(function, iterable, ...)\n\nReturn an iterator that applies function to every item of iterable, yielding the results.', 'max': 'max(iterable, *[, key, default])\n\nReturn the largest item in an iterable or the largest of two or more arguments.', 'memoryview': 'memoryview(object)\n\nReturn a "memory view" object created from the given argument.', 'min': 'min(iterable, *[, key, default])\n\nReturn the smallest item in an iterable or the smallest of two or more arguments.', 'next': 'next(iterator[, default])\n\nRetrieve the next item from the iterator by calling its __next__() method.', 'object': 'object()\n\nThe base for all classes.', 'oct': 'oct(x)\n\nConvert an integer number to an octal string prefixed with "0o".', 'open': "open(file, mode='r', ...)\n\nOpen file and return a corresponding file object.", 'ord': 'ord(c)\n\nGiven a string representing one Unicode character, return an integer representing the Unicode code point of that character.', 'pow': 'pow(base, exp[, mod])\n\nReturn base to the power exp; if mod is present, return base to the power exp, modulo mod.', 'print': "print(*objects, sep=' ', end='\\n', ...)\n\nPrints the values to a stream, or to sys.stdout by default.", 'property': 'property(fget=None, fset=None, fdel=None, doc=None)\n\nReturn a property attribute.', 'range': "range(stop) -> range object\n\nReturn an object that produces a sequence of integers from start (inclusive) to stop (exclusive) by step.", 'repr': 'repr(object)\n\nReturn a string containing a printable representation of an object.', 'reversed': 'reversed(seq)\n\nReturn a reverse iterator.', 'round': 'round(number[, ndigits])\n\nRound a number to a given precision in decimal digits.', 'set': 'set([iterable])\n\nReturn a new set object, optionally with elements taken from iterable.', 'setattr': 'setattr(object, name, value)\n\nAssigns the value to the attribute on the given object.', 'slice': 'slice(stop) or slice(start, stop, step)\n\nReturn a slice object representing the set of indices specified by range(start, stop, step).', 'sorted': "sorted(iterable, *, key=None, reverse=False)\n\nReturn a new sorted list from the items in iterable.", 'staticmethod': 'staticmethod(function)\n\nTransform a method into a static method.', 'str': "str(object='') -> str\n\nReturn a string version of object.", 'sum': 'sum(iterable[, start])\n\nSums the items of an iterable from left to right and returns the total.', 'super': 'super([type[, object-or-type]])\n\nReturn a proxy object that delegates method calls to a parent or sibling class of type.', 'tuple': 'tuple([iterable])\n\nReturn a tuple whose items are the same and in the same order as iterable’s items.', 'type': "type(object_or_name, bases, dict)\n\nWith one argument, return the type of an object.", 'vars': 'vars([object])\n\nReturn the __dict__ attribute for a module, class, instance, or any other object.', 'zip': "zip(*iterables)\n\nMake an iterator that aggregates elements from each of the iterables."
        }
        
        self.exception_list = ['Exception', 'BaseException', 'ArithmeticError', 'AssertionError', 'AttributeError', 'EOFError', 'ImportError', 'ModuleNotFoundError', 'IndexError', 'KeyError', 'KeyboardInterrupt', 'MemoryError', 'NameError', 'NotImplementedError', 'OSError', 'OverflowError', 'RecursionError', 'RuntimeError', 'SyntaxError', 'SystemError', 'TypeError', 'ValueError', 'ZeroDivisionError', 'FileNotFoundError', 'PermissionError', 'TimeoutError', 'ConnectionError']
        self.exception_tooltips = {k: "Exception type" for k in self.exception_list} 

        self.easter_egg_tooltips = { "this": "The Zen of Python...", "antigravity": "import antigravity...", "from __future__ import braces": "SyntaxError: not a chance" }
        
        self.standard_libraries = {k: {'tooltip': 'Standard library module.'} for k in ['os', 'sys', 're', 'json', 'datetime', 'math', 'random', 'subprocess', 'threading', 'collections', 'itertools', 'functools', 'pathlib', 'logging', 'tkinter', 'traceback', 'time']}
        self.standard_library_function_tooltips = { 'os.path.join': 'os.path.join(...)' }

        self.builtin_list = list(self.builtin_tooltips.keys())
        
        self.raw_keywords = []
        keyword_set = set(keyword.kwlist)
        all_keyword_like = keyword_set.union({'self'}) - {'break', 'continue'}

        for kw in all_keyword_like:
            detail = self.keyword_tooltips.get(kw, f'Python keyword: {kw}')
            if kw in ['True', 'False', 'None']:
                self.raw_keywords.append({'label': kw, 'type': 'constant', 'insert': kw, 'detail': detail, 'source': 'Built-in Constant'})
            else:
                insert_text = f'{kw} ' if kw not in ['pass', 'return', 'self'] else kw
                self.raw_keywords.append({'label': kw, 'type': 'keyword', 'insert': insert_text, 'detail': detail, 'source': 'Keyword'})

        for b_in in self.builtin_list:
            if b_in in keyword_set: continue
            detail = self.builtin_tooltips.get(b_in, f"Built-in function: {b_in}")
            insert_text = f'{b_in}()'
            if b_in in ['classmethod', 'staticmethod', 'property', 'object', 'super', 'type', 'list', 'dict', 'set', 'tuple', 'frozenset']:
                 insert_text = b_in
            self.raw_keywords.append({'label': b_in, 'type': 'function', 'insert': insert_text, 'detail': detail, 'source': 'Built-in Function'})

        # --- RESTORED SNIPPET DATA ---
        self.snippets = [
            {'label': 'if', 'match': 'if', 'type': 'snippet', 'insert': 'if ${1:condition}:\n    ${2:pass}\n$0', 'detail': 'A basic if statement.\n[code]if condition:\n    pass[/code]', 'source': 'Snippet'},
            {'label': 'if/else', 'match': 'ifelse', 'type': 'snippet', 'insert': 'if ${1:condition}:\n    ${2:pass}\nelse:\n    ${3:pass}\n$0', 'detail': 'An if-else block.\n[code]if condition:\n    pass\nelse:\n    pass[/code]', 'source': 'Snippet'},
            {'label': 'if/elif/else', 'match': 'ifelif', 'type': 'snippet', 'insert': 'if ${1:condition}:\n    ${2:pass}\nelif ${3:another_condition}:\n    ${4:pass}\nelse:\n    ${5:pass}\n$0', 'detail': 'A full conditional chain.\n[code]if x > 10:\n    ...\nelif x > 5:\n    ...\nelse:\n    ...[/code]', 'source': 'Snippet'},
            {'label': 'for loop (range)', 'match': 'forr', 'type': 'snippet', 'insert': 'for ${1:i} in range(${2:10}):\n    ${3:pass}\n$0', 'detail': 'A for loop over a numerical range.\n[code]for i in range(10):\n    print(i)[/code]', 'source': 'Snippet'},
            {'label': 'try/except', 'match': 'try', 'type': 'snippet', 'insert': 'try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}\n$0', 'detail': 'A block for handling potential exceptions.\n[code]try:\n    risky_op()\nexcept Exception as e:\n    handle(e)[/code]', 'source': 'Snippet'},
            {'label': 'try/except/finally', 'match': 'tryf', 'type': 'snippet', 'insert': 'try:\n    ${1:pass}\nexcept ${2:Exception} as ${3:e}:\n    ${4:pass}\nfinally:\n    ${5:pass}\n$0', 'detail': 'An exception block with a `finally` clause for cleanup.\n[code]try:\n    ...\nfinally:\n    cleanup()[/code]', 'source': 'Snippet'},
            {'label': 'with open (read)', 'match': 'witho', 'type': 'snippet', 'insert': "with open(${1:'file.txt'}, 'r') as ${2:f}:\n    ${3:content} = ${2:f}.read()\n$0", 'detail': 'Safely open a file for reading.\n[code]with open("data.txt", "r") as f:\n    data = f.read()[/code]', 'source': 'Snippet'},
            {'label': 'class (basic)', 'match': 'class', 'type': 'snippet', 'insert': 'class ${1:NewClass}:\n    """${2:Docstring for NewClass}"""\n    ${3:pass}\n$0', 'detail': 'Define a simple, empty class.\n[code]class MyClass:\n    pass[/code]', 'source': 'Snippet'},
            {'label': 'class (with __init__)', 'match': 'class', 'type': 'snippet', 'insert': 'class ${1:NewClass}:\n    """${2:Docstring for NewClass}"""\n    def __init__(self, ${3:arg}):\n        self.arg = arg\n    $0', 'detail': 'Define a class with a constructor.\n[code]class MyClass:\n    def __init__(self, arg):\n        self.arg = arg[/code]', 'source': 'Snippet'},
            {'label': 'def (function)', 'context': 'global_scope', 'match': 'def', 'type': 'snippet', 'insert': 'def ${1:function_name}(${2:params}):\n    """${3:Docstring for function_name}"""\n    ${4:pass}\n$0', 'detail': 'Define a new function in the global scope.\n[code]def my_func(p1, p2):\n    return p1 + p2[/code]', 'source': 'Snippet'},
            {'label': 'if __name__ == "__main__"', 'match': 'ifmain', 'type': 'snippet', 'insert': 'if __name__ == "__main__":\n    ${1:pass}\n$0', 'detail': 'Standard boilerplate for an executable script.\n[code]if __name__ == "__main__":\n    main()[/code]', 'source': 'Snippet'},
            
            # Context-Aware Snippets
            {'label': 'break', 'context': 'loop_body', 'type': 'keyword', 'insert': 'break', 'detail': 'CONTEXT: Inside a loop.\nExits the current loop immediately.', 'source': 'Context Snippet'},
            {'label': 'continue', 'context': 'loop_body', 'type': 'keyword', 'insert': 'continue', 'detail': 'CONTEXT: Inside a loop.\nSkips to the next iteration of the current loop.', 'source': 'Context Snippet'},
            {'label': 'def (__init__)', 'context': 'class', 'match': 'def', 'type': 'constructor', 'insert': 'def __init__(self, ${1:arg}):\n    ${2:pass}\n$0', 'detail': 'CONTEXT: Inside a class.\nThe constructor for the class.', 'source': 'Context Snippet'},
            {'label': 'def (method)', 'context': 'class', 'match': 'def', 'type': 'snippet', 'insert': 'def ${1:my_method}(self, ${2:arg1}):\n    ${3:pass}\n$0', 'detail': 'CONTEXT: Inside a class.\nDefine a method that operates on an instance.', 'source': 'Context Snippet'},
            {'label': '@classmethod', 'context': 'class', 'type': 'snippet', 'insert': '@classmethod\ndef ${1:my_class_method}(cls, ${2:arg1}):\n    ${3:pass}\n$0', 'detail': 'CONTEXT: Inside a class.\nDefine a method that operates on the class itself.', 'source': 'Context Snippet'},
            {'label': '@staticmethod', 'context': 'class', 'type': 'snippet', 'insert': '@staticmethod\ndef ${1:my_static_method}(${2:arg1}):\n    ${3:pass}\n$0', 'detail': 'CONTEXT: Inside a class.\nDefine a regular function namespaced within the class.', 'source': 'Context Snippet'},
            {'label': '@property', 'context': 'class', 'type': 'snippet', 'insert': '@property\ndef ${1:my_property}(self):\n    return self._${1:my_property}\n$0', 'detail': 'CONTEXT: Inside a class.\nCreate a read-only property.', 'source': 'Context Snippet'}
        ]
        
    def _configure_tags_and_tooltips(self):
        font_size_str = self.text_area.cget("font").split()[1]
        font_size = int(font_size_str) if font_size_str.isdigit() else 10
        bold_font = ("Consolas", font_size, "bold")
        
        tag_configs = { "context_highlight_line": {"background": "#3E3D32"}, "reactive_error_line": {"background": "#FF4C4C"}, "handled_exception_line": {"background": "#FFA500"}, "proactive_error_line": {"background": "#b3b300"}, "function_definition": {"foreground": "#DCDCAA"}, "class_definition": {"foreground": "#4EC9B0"}, "function_call": {"foreground": "#DCDCAA"}, "class_usage": {"foreground": "#4EC9B0"}, "fstring_expression": {"foreground": "#CE9178", "background": "#3a3a3a"}, "self_keyword": {"foreground": "#DA70D6"}, "self_method_call": {"foreground": "#9CDCFE"}, "priesty_keyword": {"foreground": "#DA70D6"}, "def_keyword": {"foreground": "#569CD6", "font": bold_font}, "class_keyword": {"foreground": "#569CD6", "font": bold_font}, "keyword_conditional": {"foreground": "#C586C0"}, "keyword_loop": {"foreground": "#C586C0"}, "keyword_return": {"foreground": "#C586C0"}, "keyword_structure": {"foreground": "#C586C0"}, "keyword_import": {"foreground": "#4EC9B0"}, "keyword_exception": {"foreground": "#D16969"}, "keyword_boolean_null": {"foreground": "#569CD6"}, "keyword_logical": {"foreground": "#DCDCAA"}, "keyword_async": {"foreground": "#FFD700"}, "keyword_context": {"foreground": "#CE9178"}, "string_literal": {"foreground": "#A3C78B"}, "number_literal": {"foreground": "#B5CEA8"}, "comment_tag": {"foreground": "#6A9955"}, "function_param": {"foreground": "#9CDCFE"}, "bracket_tag": {"foreground": "#FFD700"}, "builtin_function": {"foreground": "#DCDCAA"}, "exception_type": {"foreground": "#4EC9B0"}, "dunder_method": {"foreground": "#DA70D6"}, "standard_library_module": {"foreground": "#4EC9B0"}, "custom_import": {"foreground": "#9CDCFE"}, "standard_library_function": {"foreground": "#DCDCAA"}, "easter_egg_import": {"foreground": "#FF8C00"} }
        for tag, config in tag_configs.items(): self.text_area.tag_configure(tag, **config)
        
        self.dunder_tooltips = {'__init__': '__init__(self, ...)\n\nThe constructor method for a class.', '__str__': '__str__(self) -> str\n\nReturns the printable string representation of an object.'}

        keyword_tags_for_tooltips = [ "def_keyword", "class_keyword", "keyword_conditional", "keyword_loop", "keyword_return", "keyword_structure", "keyword_import", "keyword_exception", "keyword_logical", "keyword_async", "keyword_context", "self_keyword" ]
        for tag in keyword_tags_for_tooltips:
            self.text_area.tag_bind(tag, "<Enter>", self._on_hover_keyword)
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

        def create_word_hover_handler(tooltip_dict):
            return lambda event: self._on_hover_word(event, tooltip_dict) if not any(tag in self.text_area.tag_names(f"@{event.x},{event.y}") for tag in ["reactive_error_line", "proactive_error_line"]) else None
        
        for tag, t_dict in [("builtin_function", self.builtin_tooltips), ("exception_type", self.exception_tooltips), ("dunder_method", self.dunder_tooltips)]:
            self.text_area.tag_bind(tag, "<Enter>", create_word_hover_handler(t_dict)); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        
        for tag in ["function_call", "class_usage"]:
            self.text_area.tag_bind(tag, "<Enter>", self._on_hover_user_defined); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        
        for tag in ["standard_library_module", "easter_egg_import"]:
            self.text_area.tag_bind(tag, "<Enter>", self._on_hover_standard_lib_module)
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        
        for tag in ["standard_library_function"]:
            handler = self._on_hover_standard_lib_function
            self.text_area.tag_bind(tag, "<Enter>", handler); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        
        for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]:
            self.text_area.tag_bind(tag, "<Enter>", self._on_hover_error_line)
            self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

    def highlight_context_line(self, line_number: int):
        self.clear_context_highlight()
        tag = "context_highlight_line"
        self.text_area.tag_add(tag, f"{line_number}.0", f"{line_number}.end")
        self.text_area.tag_bind(tag, "<Enter>", 
            lambda e, ln=line_number: self._show_tooltip(e, f"Context-aware completions are active for this block (line {ln})."))
        self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

    def clear_context_highlight(self):
        tag = "context_highlight_line"
        self.text_area.tag_remove(tag, "1.0", tk.END)
        self.text_area.tag_unbind(tag, "<Enter>")
        self.text_area.tag_unbind(tag, "<Leave>")

    def _on_hover_user_defined(self, event):
        try:
            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            definitions = self.code_analyzer.get_definitions()
            if word in definitions: self._show_tooltip(event, definitions[word]['docstring'])
        except tk.TclError: pass

    def _on_hover_keyword(self, event):
        try:
            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            if word in self.keyword_tooltips:
                self._show_tooltip(event, self.keyword_tooltips[word])
        except tk.TclError:
            pass
            
    def _on_hover_error_line(self, event):
        try:
            index = self.text_area.index(f"@{event.x},{event.y}")
            line_number = int(index.split('.')[0])
            if line_number in self.line_error_messages:
                self._show_tooltip(event, self.line_error_messages[line_number])
        except (tk.TclError, ValueError):
            pass

    def _on_hover_standard_lib_module(self, event):
        try:
            line_start_index = self.text_area.index(f"@{event.x},{event.y} linestart")
            line_text = self.text_area.get(line_start_index, f"{line_start_index} lineend")
            braces_key = "from __future__ import braces"
            if braces_key in line_text:
                self._show_tooltip(event, self.easter_egg_tooltips[braces_key])
                return

            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            
            if word in self.easter_egg_tooltips:
                self._show_tooltip(event, self.easter_egg_tooltips[word])
                return

            real_module = self.imported_aliases.get(word)
            base_module = real_module.split('.')[0] if real_module else None
            if base_module and base_module in self.standard_libraries:
                self.text_area.config(cursor="hand2")
                self._show_tooltip(event, self.standard_libraries[base_module].get('tooltip', 'Standard library module.'))
        except tk.TclError:
            pass
        finally:
            self.text_area.tag_bind("standard_library_module", "<Leave>", lambda e: self.text_area.config(cursor="xterm"))

    def _on_hover_standard_lib_function(self, event):
        try:
            index = f"@{event.x},{event.y}"; current_word = self.text_area.get(f"{index} wordstart", f"{index} wordend")
            line_start = self.text_area.index(f"{index} linestart"); line_text = self.text_area.get(line_start, index + " wordend")
            match = re.search(r'\b([\w.]+)\.' + re.escape(current_word) + r'\b', line_text)
            if not match: return
            module_word = match.group(1).split('.')[0]; real_module = self.imported_aliases.get(module_word)
            base_module = real_module.split('.')[0] if real_module else None
            if base_module:
                full_name = f"{base_module}.{current_word}"
                self._show_tooltip(event, self.standard_library_function_tooltips.get(full_name, "Standard library member."))
        except tk.TclError: pass

    def _on_hover_word(self, event, tooltip_dict):
        try:
            index = self.text_area.index(f"@{event.x},{event.y}"); word = self.text_area.get(f"{index} wordstart", f"{index} wordend")
            if word in tooltip_dict: self._show_tooltip(event, tooltip_dict[word])
        except tk.TclError: pass

    def _on_dot_key(self, event):
        self._end_snippet_session()
        self.autocomplete_dismissed_word = None
        self.text_area.insert(tk.INSERT, ".")
        self.after(10, self._update_autocomplete_display)
        return "break"

    def _on_manual_autocomplete_trigger(self, event=None):
        self.manual_trigger_active = True 
        self.autocomplete_dismissed_word = None
        self._update_autocomplete_display(manual_trigger=True)
        return "break"
        
    def _show_tooltip(self, event, text, bbox=None):
        if not text or (self.tooltips_var and not self.tooltips_var.get()): return
        if event:
            x, y = self.winfo_rootx() + self.text_area.winfo_x() + event.x + 20, self.winfo_rooty() + self.text_area.winfo_y() + event.y + 20
        elif bbox:
            x, y = self.winfo_rootx() + self.text_area.winfo_x() + bbox[0], self.winfo_rooty() + self.text_area.winfo_y() + bbox[1] + bbox[3] + 5
        else: return
        self.tooltip_label.config(text=text)
        self.tooltip_window.wm_geometry(f"+{int(x)}+{int(y)}")
        self.tooltip_window.wm_deiconify()

    def _hide_tooltip(self, event=None):
        self.tooltip_window.wm_withdraw()
        
    def _show_signature_help(self):
        try:
            func_name_start = self.text_area.index("insert-1c wordstart")
            func_name = self.text_area.get(func_name_start, "insert-1c")
            if not func_name: return
            tooltip_text = None
            user_defs = self.code_analyzer.get_definitions()
            if func_name in user_defs: tooltip_text = user_defs[func_name]['docstring']
            elif func_name in self.builtin_tooltips: tooltip_text = self.builtin_tooltips[func_name]
            elif func_name in self.builtin_list:
                try:
                    builtins_obj = __builtins__
                    builtin_func = getattr(builtins_obj, func_name, None) if not isinstance(builtins_obj, dict) else builtins_obj.get(func_name)
                    if callable(builtin_func):
                        signature, doc = inspect.signature(builtin_func), inspect.getdoc(builtin_func)
                        tooltip_text = f"{func_name}{signature}" + (f"\n\n{doc}" if doc else "")
                    else: tooltip_text = f"{func_name}(...)"
                except (KeyError, TypeError, ValueError): tooltip_text = f"{func_name}(...)"
            if tooltip_text:
                bbox = self.text_area.bbox(tk.INSERT)
                if bbox: self._show_tooltip(None, tooltip_text, bbox=bbox)
        except Exception: pass

    def _on_escape(self, event=None):
        if self.active_snippet_session:
            self._end_snippet_session()
            return "break"
        if self.autocomplete_manager.is_visible():
            self.autocomplete_manager.hide()
            try: self.autocomplete_dismissed_word = self.text_area.get("insert wordstart", "insert")
            except tk.TclError: self.autocomplete_dismissed_word = None
            return "break"
        self._hide_tooltip(); return None

    def _on_key_release(self, event=None):
        if not event:
            return

        if self.manual_trigger_active:
            self.manual_trigger_active = False
            return

        ignored_keys = {"Up", "Down", "Return", "Tab", "Escape", "period", 
                        "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}
        if event.keysym in ignored_keys:
            return
        
        # The faulty logic that prematurely ended the snippet session has been removed from here.
        # The session is now correctly ended only by Tab (at the end), Escape, or clicking away.

        self.last_action_was_auto_feature = False
        self.last_auto_action_details = None

        if event.keysym != "parenleft":
             self._hide_tooltip()
        
        try:
            current_word = self.text_area.get("insert-1c wordstart", "insert")
            if current_word == "except":
                self.after(10, self._update_autocomplete_display)
                return
        except tk.TclError:
            pass
        
        if event.keysym == "space":
            line_before_cursor = self.text_area.get("insert linestart", "insert")
            if line_before_cursor.strip() in ("from", "import", "except"):
                self.after(10, self._update_autocomplete_display)
            return

        self.after(50, self._update_autocomplete_display)

    def _on_click(self, event=None):
        self._end_snippet_session()
        self.autocomplete_manager.hide()
        self._hide_tooltip()
        self.autocomplete_dismissed_word = None
        self.last_action_was_auto_feature = False
        self.last_auto_action_details = None

    def _on_arrow_up(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(-1)
        self._end_snippet_session()
        return None

    def _on_arrow_down(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(1)
        self._end_snippet_session()
        return None
        
    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            self.text_area.event_generate("<<Change>>")
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self._end_snippet_session()
        self.autocomplete_manager.hide()
        self.after(10, self.update_line_numbers)