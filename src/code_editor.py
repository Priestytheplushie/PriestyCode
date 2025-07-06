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
        """Determines context using a robust text-scanning method, now with more nuance for class bodies."""
        lines = code_text.splitlines()
        if not (0 < line_number <= len(lines)): return None, None
        try:
            current_indent = len(lines[line_number - 1]) - len(lines[line_number - 1].lstrip(' '))
        except IndexError: return None, None
        
        for i in range(line_number - 2, -1, -1):
            line = lines[i]
            line_indent = len(line) - len(line.lstrip(' '))
            
            if line_indent < current_indent:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith('#'):
                    continue

                if stripped_line.startswith(('for ', 'while ', 'async for ')):
                    return 'loop_body', i + 1
                
                if stripped_line.startswith('class '):
                    class_def_line_index = i
                    has_content_after_class_def = False
                    for j in range(class_def_line_index + 1, line_number - 1):
                        if lines[j].strip():
                            has_content_after_class_def = True
                            break
                    return ('class' if has_content_after_class_def else 'class_body_start'), i + 1

                if stripped_line.startswith(('def ', 'async def ')):
                    return 'function', i + 1
                
                if stripped_line.startswith('try:'):
                    return 'try', i + 1
                
                current_indent = line_indent

        return None, None

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
        self.autocomplete_active = True
        self.proactive_errors_active = True
        self.autocomplete_dismissed_word = None
        self.manual_trigger_active = False
        self.imported_aliases = {}
        self.code_analyzer = CodeAnalyzer()
        self.autoindent_var = autoindent_var
        self.tooltips_var = tooltips_var
        self.line_error_messages = {}

        self.CONTEXT_DISPLAY_NAMES = {
            "loop_body": "Loop",
            "class_body_start": "Class",
            "function": "Function"
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
                lib_members = self.standard_libraries[module_name].get('members', [])
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
                        for member_name in self.standard_libraries[base_module_name].get('members', []):
                            if member_name.lower().startswith(partial_member_lower):
                                completions.append({'label': member_name, 'type': 'function', 'insert': member_name, 'detail': self.standard_library_function_tooltips.get(f"{base_module_name}.{member_name}", "Standard library member."), 'source': 'Standard Library Member', 'priority': 1})
                completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
                self.autocomplete_manager.show(completions, partial_member)
                return
        except (tk.TclError, ValueError):
            self.autocomplete_manager.hide()
            return

        try:
            current_word = self.text_area.get("insert-1c wordstart", "insert")
            current_line_num = int(self.text_area.index(tk.INSERT).split('.')[0])
        except (tk.TclError, ValueError): self.autocomplete_manager.hide(); return
        
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

            match_text = item.get('match', label)

            should_add = False
            if manual_trigger:
                should_add = True
            elif match_text.lower().startswith(current_word_lower):
                should_add = True

            if should_add and label.lower() not in {l.lower() for l in labels_so_far}:
                item['priority'] = priority
                labels_so_far.add(label)
                completions.append(item)

        scope_context, context_line = self.code_analyzer.get_scope_context(current_line_num, all_text)

        # --- GATHERING LOGIC (Priority Order) ---

        # Priority 0: Context-Aware Snippets
        for s in self.snippets:
            s_context = s.get('context')
            if s_context and s_context == scope_context:
                if scope_context and context_line is not None:
                    block_type = self.CONTEXT_DISPLAY_NAMES.get(scope_context, "block")
                    context_message = f"Inside '{block_type}' on line {context_line}"
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

    def _on_dot_key(self, event):
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
        if self.autocomplete_manager.is_visible():
            self.autocomplete_manager.hide()
            try: self.autocomplete_dismissed_word = self.text_area.get("insert wordstart", "insert")
            except tk.TclError: self.autocomplete_dismissed_word = None
            return "break"
        self._hide_tooltip(); return None

    def _on_key_release(self, event=None):
        if not event:
            return

        # Always allow manual trigger state to be cleared
        if self.manual_trigger_active:
            self.manual_trigger_active = False
            return

        # Ignore key releases for navigation and action keys that have their own handlers.
        # This prevents the `last_action_was_auto_feature` flag from being cleared
        # by the release of the same key that set it (e.g., Return).
        ignored_keys = {"Up", "Down", "Return", "Tab", "Escape", "period", 
                        "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}
        if event.keysym in ignored_keys:
            return
        
        # If the key was not ignored, it's a normal character.
        # This means any previous auto-feature action is now 'committed' by the user's typing.
        self.last_action_was_auto_feature = False
        self.last_auto_action_details = None

        if event.keysym != "parenleft":
             self._hide_tooltip()
        
        # Proactive trigger for 'except' keyword completion
        try:
            current_word = self.text_area.get("insert-1c wordstart", "insert")
            if current_word == "except":
                self.after(10, self._update_autocomplete_display)
                return # Prevent slower, generic trigger
        except tk.TclError:
            pass
        
        # Trigger autocomplete for specific keys like space in certain contexts
        if event.keysym == "space":
            line_before_cursor = self.text_area.get("insert linestart", "insert")
            if line_before_cursor.strip() in ("from", "import", "except"):
                self.after(10, self._update_autocomplete_display)
            return

        # For all other character keys, trigger a delayed autocomplete
        self.after(50, self._update_autocomplete_display)

    def _on_click(self, event=None):
        self.autocomplete_manager.hide()
        self._hide_tooltip()
        self.autocomplete_dismissed_word = None
        self.last_action_was_auto_feature = False
        self.last_auto_action_details = None

    def _on_arrow_up(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(-1)
        return None

    def _on_arrow_down(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(1)
        return None
        
    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            self.text_area.event_generate("<<Change>>")
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self.autocomplete_manager.hide()
        self.after(10, self.update_line_numbers)

    def _configure_autocomplete_data(self):
        self.keyword_tooltips = {
            'if': "The 'if' keyword is used for conditional execution.\n\nExample:\nif x > 5:\n    print('x is greater than 5')", 'elif': "The 'elif' keyword is a contraction of 'else if'. It allows checking multiple expressions.\n\nExample:\nif x > 10:\n    print('x is large')\nelif x > 5:\n    print('x is medium')", 'else': "The 'else' keyword catches anything which isn't caught by the preceding 'if' or 'elif' clauses.\n\nExample:\nif x > 5:\n    print('x is greater than 5')\nelse:\n    print('x is 5 or less')", 'for': "The 'for' keyword is used to iterate over the items of any sequence.\n\nExample:\nfor i in range(3):\n    print(i)", 'while': "The 'while' keyword is used to execute a block of code as long as a condition is true.\n\nExample:\ncount = 0\nwhile count < 3:\n    print(count)\n    count += 1", 'break': "The 'break' statement terminates the current 'for' or 'while' loop.\n\nExample:\nfor i in range(10):\n    if i == 3:\n        break\n    print(i)", 'continue': "The 'continue' statement rejects all the remaining statements in the current iteration of the loop and moves the control back to the top of the loop.\n\nExample:\nfor i in range(5):\n    if i == 2:\n        continue\n    print(i)", 'def': "The 'def' keyword is used to define a function.\n\nExample:\ndef my_function(name):\n    print(f'Hello, {name}')", 'class': "The 'class' keyword is used to create a new user-defined class.\n\nExample:\nclass MyClass:\n    x = 5", 'return': "The 'return' statement exits a function, optionally passing back a value.\n\nExample:\ndef add(a, b):\n    return a + b", 'yield': "The 'yield' keyword is used in generator functions. It produces a value for the generator and pauses execution.\n\nExample:\ndef my_generator():\n    for i in range(3):\n        yield i", 'try': "The 'try' keyword starts a block of code that might raise an exception.\n\nExample:\ntry:\n    x = 1 / 0\nexcept ZeroDivisionError:\n    print('Cannot divide by zero!')", 'except': "The 'except' keyword catches exceptions raised in the 'try' block.\n\nExample:\ntry:\n    # ...\nexcept ValueError as e:\n    print(e)", 'finally': "The 'finally' clause is always executed before leaving the 'try' statement, whether an exception has occurred or not.\n\nExample:\nf = open('file.txt')\ntry:\n    # ...\nfinally:\n    f.close()", 'with': "The 'with' statement is used to wrap the execution of a block with methods defined by a context manager.\n\nExample:\nwith open('file.txt') as f:\n    content = f.read()", 'as': "The 'as' keyword is used to create an alias when importing modules, or in 'with' and 'except' statements.\n\nExample:\nimport numpy as np", 'import': "The 'import' statement is used to bring a module or members of a module into the current namespace.\n\nExample:\nimport math", 'from': "The 'from' keyword is used with 'import' to bring specific members of a module into the namespace.\n\nExample:\nfrom math import sqrt", 'pass': "The 'pass' statement is a null operation; nothing happens when it executes. It is useful as a placeholder.", 'assert': "The 'assert' statement is a debugging aid that tests a condition. If the condition is false, it raises an AssertionError.\n\nExample:\nassert x > 0, 'x must be positive'", 'lambda': "The 'lambda' keyword is used to create small anonymous functions.\n\nExample:\nadd = lambda a, b: a + b", 'global': "The 'global' keyword declares that a variable inside a function is global (belongs to the global scope).\n\nExample:\ndef my_func():\n    global x\n    x = 10", 'nonlocal': "The 'nonlocal' keyword is used to work with variables in the nearest enclosing scope that are not global.\n\nExample:\ndef outer():\n    x = 'local'\n    def inner():\n        nonlocal x\n        x = 'nonlocal'\n    inner()", 'del': "The 'del' statement is used to remove an object reference.\n\nExample:\na = [1, 2, 3]\ndel a[1]", 'in': "The 'in' keyword is a membership operator, testing if a sequence contains a value.\n\nExample:\nif 2 in [1, 2, 3]:\n    print('Found')", 'is': "The 'is' keyword is an identity operator, testing if two variables point to the same object.\n\nExample:\nif a is b:\n    print('a and b are the same object')", 'and': "Logical AND operator.", 'or': "Logical OR operator.", 'not': "Logical NOT operator.", 'async': "The 'async' keyword is used to declare an asynchronous function (coroutine).\n\nExample:\nasync def my_coroutine():\n    await asyncio.sleep(1)", 'await': "The 'await' keyword is used to pause the execution of a coroutine until an awaitable object completes.\n\nExample:\nresult = await some_coroutine()", 'self': "Refers to the instance of the class."
        }
        self.builtin_tooltips = {
            'print': "print(*objects, sep=' ', end='\\n', ...)\n\nPrints the values to a stream, or to sys.stdout by default.", 'len': "len(s)\n\nReturn the length (the number of items) of an object.", 'str': "str(object='') -> str\n\nReturn a string version of object.", 'int': "int(x, base=10) -> integer\n\nConvert a number or string to an integer.", 'list': "list(iterable) -> new list\n\nReturn a list whose items are the same and in the same order as iterable's items.", 'dict': "dict(**kwarg) -> new dictionary\n\nCreate a new dictionary.", 'range': "range(stop) -> range object\nrange(start, stop[, step]) -> range object\n\nReturn an object that produces a sequence of integers from start (inclusive) to stop (exclusive) by step.", 'open': "open(file, mode='r', ...)\n\nOpen file and return a corresponding file object.", 'type': "type(object_or_name, bases, dict)\n\nWith one argument, return the type of an object. With three arguments, return a new type object.", 'enumerate': "enumerate(iterable, start=0)\n\nReturn an enumerate object. iterable must be a sequence, an iterator, or some other object which supports iteration.", 'zip': "zip(*iterables)\n\nMake an iterator that aggregates elements from each of the iterables.", 'sorted': "sorted(iterable, *, key=None, reverse=False)\n\nReturn a new sorted list from the items in iterable.", 'input': "input(prompt=None, /)\n\nRead a string from standard input. The trailing newline is stripped."
        }
        
        self.exception_list = ['Exception', 'BaseException', 'ArithmeticError', 'AssertionError', 'AttributeError', 'EOFError', 'ImportError', 'ModuleNotFoundError', 'IndexError', 'KeyError', 'KeyboardInterrupt', 'MemoryError', 'NameError', 'NotImplementedError', 'OSError', 'OverflowError', 'RecursionError', 'RuntimeError', 'SyntaxError', 'SystemError', 'TypeError', 'ValueError', 'ZeroDivisionError', 'FileNotFoundError', 'PermissionError', 'TimeoutError', 'ConnectionError']
        self.exception_tooltips = {'Exception': 'Common base class for all non-exit exceptions.', 'BaseException': 'The base class for all built-in exceptions.', 'ArithmeticError': 'Base class for arithmetic errors.', 'AssertionError': 'Raised when an assert statement fails.', 'AttributeError': 'Raised when an attribute reference or assignment fails.', 'EOFError': 'Raised when input() hits an end-of-file condition (EOF).', 'ImportError': 'Raised when an import statement has trouble trying to load a module.', 'ModuleNotFoundError': 'A subclass of ImportError; raised when a module could not be found.', 'IndexError': 'Raised when a sequence subscript is out of range.', 'KeyError': 'Raised when a mapping (dictionary) key is not found.', 'KeyboardInterrupt': 'Raised when the user hits the interrupt key (normally Ctrl+C).', 'MemoryError': 'Raised when an operation runs out of memory.', 'NameError': 'Raised when a local or global name is not found.', 'NotImplementedError': 'Raised by abstract methods.', 'OSError': 'Raised for system-related errors.', 'OverflowError': 'Raised when the result of an arithmetic operation is too large to be represented.', 'RecursionError': 'Raised when the maximum recursion depth is exceeded.', 'RuntimeError': 'Raised when an error is detected that doesn’t fall in any of the other categories.', 'SyntaxError': 'Raised when the parser encounters a syntax error.', 'SystemError': 'Raised for interpreter-level errors.', 'TypeError': 'Raised when an operation or function is applied to an object of inappropriate type.', 'ValueError': 'Raised when a function receives an argument of the correct type but an inappropriate value.', 'ZeroDivisionError': 'Raised when the second argument of a division or modulo operation is zero.', 'FileNotFoundError': 'Raised when a file or directory is requested but doesn’t exist.', 'PermissionError': 'Raised when trying to run an operation without the adequate access rights.', 'TimeoutError': 'Raised when a system function timed out at the system level.', 'ConnectionError': 'A base class for connection-related issues.'}
        
        self.easter_egg_tooltips = {
            "this": "The Zen of Python, by Tim Peters\n\nBeautiful is better than ugly.\nExplicit is better than implicit.\nSimple is better than complex.\nComplex is better than complicated.\nFlat is better than nested.\nSparse is better than dense.\nReadability counts.\nSpecial cases aren't special enough to break the rules.\nAlthough practicality beats purity.\nErrors should never pass silently.\nUnless explicitly silenced.\nIn the face of ambiguity, refuse the temptation to guess.\nThere should be one-- and preferably only one --obvious way to do it.\nAlthough that way may not be obvious at first unless you're Dutch.\nNow is better than never.\nAlthough never is often better than *right* now.\nIf the implementation is hard to explain, it's a bad idea.\nIf the implementation is easy to explain, it may be a good idea.\nNamespaces are one honking great idea -- let's do more of those!",
            "antigravity": "import antigravity\n\nOpens a web browser to the classic xkcd comic about Python.",
            "from __future__ import braces": "SyntaxError: not a chance"
        }

        self.standard_libraries = {
            'os': {'members': ['path', 'name', 'environ', 'getcwd', 'listdir', 'mkdir', 'makedirs', 'remove', 'removedirs', 'rename', 'rmdir', 'stat', 'system', 'unlink', 'sep'], 'tooltip': 'Provides a way of using operating system dependent functionality. Includes tools for file and directory manipulation, process management, and environment variables. For modern, object-oriented path handling, consider `pathlib`.'}, 
            'sys': {'members': ['argv', 'exit', 'path', 'platform', 'stdin', 'stdout', 'stderr', 'version', 'version_info'], 'tooltip': 'Access to system-specific parameters and functions. Provides information about the Python interpreter, such as `sys.argv` (command-line args), `sys.path` (module search path), and `sys.exit()`.'}, 
            're': {'members': ['search', 'match', 'fullmatch', 'split', 'findall', 'finditer', 'sub', 'compile', 'escape', 'IGNORECASE', 'MULTILINE'], 'tooltip': 'Provides regular expression matching operations. Key functions: `search()`, `match()`, `findall()`, `sub()`.'}, 
            'json': {'members': ['dump', 'dumps', 'load', 'loads'], 'tooltip': 'Encoder and decoder for JSON. Use `json.loads()` to parse JSON strings into Python objects and `json.dumps()` to serialize Python objects to JSON strings.'}, 
            'datetime': {'members': ['datetime', 'date', 'time', 'timedelta', 'timezone', 'now', 'utcnow'], 'tooltip': 'Supplies classes for manipulating dates and times. Create and work with `datetime`, `date`, `time`, and `timedelta` objects.'}, 
            'math': {'members': ['ceil', 'floor', 'sqrt', 'pi', 'e', 'sin', 'cos', 'tan', 'log', 'log10', 'pow', 'fabs', 'fsum', 'gcd', 'isinf', 'isnan'], 'tooltip': 'Provides access to mathematical functions for floating-point numbers, such as trigonometric, logarithmic, and power functions.'}, 
            'random': {'members': ['random', 'randint', 'choice', 'choices', 'shuffle', 'uniform', 'sample', 'seed'], 'tooltip': 'Implements pseudo-random number generators for various distributions. Includes functions like `randint()`, `choice()`, and `shuffle()`.'}, 
            'subprocess': {'members': ['run', 'Popen', 'call', 'check_call', 'check_output', 'PIPE', 'STDOUT', 'DEVNULL'], 'tooltip': 'A module to spawn new processes, connect to their input/output/error pipes, and obtain their return codes. The modern way to run external commands.'}, 
            'threading': {'members': ['Thread', 'Lock', 'Event', 'Semaphore', 'current_thread', 'active_count', 'Timer'], 'tooltip': 'Higher-level threading interface. Use it to run code concurrently in separate threads of execution. Includes `Thread`, `Lock`, and `Event` classes.'}, 
            'collections': {'members': ['defaultdict', 'Counter', 'deque', 'namedtuple', 'OrderedDict', 'ChainMap'], 'tooltip': 'Implements specialized container datatypes, providing alternatives to Python’s general-purpose built-ins. Includes `defaultdict`, `Counter`, `deque`, and `namedtuple`.'}, 
            'itertools': {'members': ['count', 'cycle', 'repeat', 'accumulate', 'chain', 'compress', 'islice', 'permutations', 'combinations', 'product'], 'tooltip': 'A collection of tools for handling iterators. Used for creating complex and efficient loops and data processing pipelines.'},
            'functools': {'members': ['lru_cache', 'partial', 'reduce', 'wraps', 'cached_property'], 'tooltip': 'Higher-order functions and operations on callable objects. Provides tools like `partial` for freezing function arguments and `lru_cache` for memoization.'},
            'pathlib': {'members': ['Path', 'PurePath', 'PureWindowsPath', 'PurePosixPath'], 'tooltip': 'Offers classes representing filesystem paths with semantics appropriate for the operating system. The modern, object-oriented way to handle file paths.'},
            'logging': {'members': ['basicConfig', 'getLogger', 'debug', 'info', 'warning', 'error', 'critical', 'FileHandler', 'StreamHandler'], 'tooltip': 'A flexible event logging system for applications. Use it to record status, error, and informational messages during program execution.'},
            'tkinter': {'members': ['Tk', 'Frame', 'Button', 'Label', 'Entry', 'Text', 'ttk', 'filedialog', 'messagebox', 'Canvas', 'Menu'], 'tooltip': 'The standard Python interface to the Tcl/Tk GUI toolkit. Used for creating desktop applications with graphical user interfaces.'}, 
            'traceback': {'members': ['print_exc', 'format_exc', 'extract_stack', 'format_exception'], 'tooltip': 'Provides a standard interface to extract, format, and print stack traces of Python programs, which is useful for error reporting.'}, 
            'time': {'members': ['time', 'sleep', 'asctime', 'perf_counter', 'monotonic', 'strftime'], 'tooltip': 'Provides various time-related functions, such as `time.sleep()` to pause execution and `time.time()` to get the current Unix timestamp.'}
        }

        self.standard_library_function_tooltips = { 'os.path': 'Submodule for common, legacy pathname manipulations. For a modern, object-oriented approach, use the `pathlib` module instead.', 'os.path.join': 'os.path.join(*paths) -> str\n\nJoin path components, inserting the correct separator for the OS.\n[code]os.path.join("data", "files", "report.txt")[/code]', 'os.path.exists': 'os.path.exists(path) -> bool\n\nReturn True if path refers to an existing file or directory.', 'os.path.isdir': 'os.path.isdir(path) -> bool\n\nReturn True if path is an existing directory.', 'os.path.isfile': 'os.path.isfile(path) -> bool\n\nReturn True if path is an existing regular file.', 'os.getcwd': 'os.getcwd() -> str\n\nReturn a string representing the current working directory (CWD).', 'os.listdir': 'os.listdir(path=".") -> list\n\nReturn a list of the names of the entries in the directory given by path.', 'sys.exit': 'sys.exit(status=0)\n\nExit from Python. This is implemented by raising the `SystemExit` exception.', 'sys.argv': 'A list of command-line arguments passed to a Python script. `sys.argv[0]` is the script name itself.', 're.search': 're.search(pattern, string) -> Match or None\n\nScan through a string, looking for the first location where the pattern produces a match.', 're.match': 're.match(pattern, string) -> Match or None\n\nTry to apply the pattern at the start of the string. Returns a match object only if the pattern matches at the beginning.', 're.findall': 're.findall(pattern, string) -> list\n\nReturn all non-overlapping matches of a pattern in a string, as a list of strings.', 're.sub': 're.sub(pattern, repl, string) -> str\n\nReturn the string obtained by replacing the leftmost non-overlapping occurrences of a pattern in a string by the replacement `repl`.', 'json.loads': 'json.loads(s) -> object\n\nDeserialize a JSON-formatted `str` to a Python object (e.g., a `dict` or `list`).\n[code]data = json.loads(\'{"key": "value"}\')[/code]', 'json.dumps': 'json.dumps(obj) -> str\n\nSerialize a Python object to a JSON-formatted `str`.\n[code]json_string = json.dumps({"key": "value"})[/code]', 'json.load': 'json.load(fp) -> object\n\nDeserialize a file-like object (e.g., from `open()`) containing a JSON document to a Python object.', 'json.dump': 'json.dump(obj, fp)\n\nSerialize a Python object as a JSON-formatted stream to a file-like object.', 'datetime.datetime.now': 'datetime.datetime.now(tz=None) -> datetime\n\nReturn the current local date and time. If `tz` is None, the returned object is naive (no timezone info).', 'random.randint': 'random.randint(a, b) -> int\n\nReturn a random integer N such that a <= N <= b (inclusive).', 'random.choice': 'random.choice(seq)\n\nReturn a random element from a non-empty sequence (like a list or tuple).', 'threading.Thread': 'A class that represents a thread of control. Create a subclass or pass a `target` callable to the constructor to specify the code to be run.', 'pathlib.Path': 'Path(*pathsegments)\n\nCreate a concrete path for the current OS. Paths can be joined with the `/` operator.\n[code]p = Path("/etc") / "hosts"[/code]', 'logging.basicConfig': 'logging.basicConfig(**kwargs)\n\nDoes basic configuration for the logging system. Should be called only once, before any calls to `logging.info`, etc.', 'tkinter.ttk': 'Themed widget set for Tkinter, providing modern-looking widgets that adapt to the native platform\'s style.', 'tkinter.filedialog': 'Module containing classes and functions for creating file/directory selection dialogs.', 'traceback.print_exc': 'traceback.print_exc()\n\nPrints exception information and a stack trace to standard error. Commonly used inside an `except` block.' }
        self.builtin_list = list(self.builtin_tooltips.keys()) + ['abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dir', 'divmod', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'isinstance', 'issubclass', 'iter', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct', 'ord', 'pow', 'property', 'repr', 'reversed', 'round', 'setattr', 'slice', 'staticmethod', 'sum', 'super', 'tuple', 'vars']
        
        self.raw_keywords = []
        
        # Process Keywords and built-in constants that are also keywords
        keyword_set = set(keyword.kwlist)
        all_keyword_like = keyword_set.union({'self'}) - {'break', 'continue'}

        for kw in all_keyword_like:
            detail = self.keyword_tooltips.get(kw, f'Python keyword: {kw}')
            if kw in ['True', 'False', 'None']:
                self.raw_keywords.append({'label': kw, 'type': 'constant', 'insert': kw, 'detail': detail, 'source': 'Built-in Constant'})
            else:
                insert_text = f'{kw} ' if kw not in ['pass', 'return', 'self'] else kw
                self.raw_keywords.append({'label': kw, 'type': 'keyword', 'insert': insert_text, 'detail': detail, 'source': 'Keyword'})

        # Process all other built-in functions
        for b_in in self.builtin_list:
            if b_in in keyword_set:
                continue # Avoid duplicating True, False, None
            
            detail = self.builtin_tooltips.get(b_in, f"Built-in function: {b_in}")
            self.raw_keywords.append({'label': b_in, 'type': 'function', 'insert': f'{b_in}()', 'detail': detail, 'source': 'Built-in Function'})

        self.snippets = [
            {'label': 'class (basic)', 'match': 'class', 'type': 'snippet', 'insert': 'class NewClass:\n    pass', 'detail': 'Define a simple, empty class.\n[code]class NewClass:\n    pass[/code]', 'source': 'Snippet'},
            {'label': 'class (with __init__)', 'match': 'class', 'type': 'snippet', 'insert': 'class NewClass:\n    """Docstring for NewClass."""\n\n    def __init__(self, arg):\n        super(NewClass, self).__init__()\n        self.arg = arg\n    ', 'detail': 'Define a new class with a constructor.\n[code]class NewClass:\n    def __init__(self, arg):\n        self.arg = arg[/code]', 'source': 'Snippet'},
            {'label': 'def (function)', 'match': 'def', 'type': 'snippet', 'insert': 'def function_name(params):\n    """Docstring for function_name."""\n    pass', 'detail': 'Define a new function.\n[code]def name(params):\n    """Docstring..."""\n    pass[/code]', 'source': 'Snippet'},
            {'label': 'for loop (for i in ...)', 'match': 'fori', 'type': 'snippet', 'insert': 'for i, item in enumerate(iterable):\n    pass', 'detail': 'Iterate over a sequence with index and value.', 'source': 'Snippet'},
            {'label': 'while True loop', 'match': 'while', 'type': 'snippet', 'insert': 'while True:\n    if condition:\n        break', 'detail': 'Creates an infinite loop with a break condition.', 'source': 'Snippet'},
            {'label': 'List Comprehension', 'match': 'lcomp', 'type': 'snippet', 'insert': '[x for x in iterable]', 'detail': 'Creates a list comprehension.\n[code][x for x in iterable if condition][/code]', 'source': 'Snippet'},
            {'label': 'Dict Comprehension', 'match': 'dcomp', 'type': 'snippet', 'insert': '{k: v for k, v in items}', 'detail': 'Creates a dictionary comprehension.\n[code]{key: value for item in iterable}[/code]', 'source': 'Snippet'},
            {'label': 'Logging Setup', 'match': 'logsetup', 'type': 'snippet', 'insert': 'import logging\nlogging.basicConfig(level=logging.INFO)', 'detail': 'Basic setup for the logging module.', 'source': 'Snippet'},
            {'label': 'if __name__ == "__main__"', 'match': 'ifmain', 'type': 'snippet', 'insert': 'if __name__ == "__main__":\n    pass', 'detail': 'Standard boilerplate for making a script executable.\n[code]if __name__ == "__main__":\n    # main execution logic[/code]', 'source': 'Snippet'},
            {'label': 'break', 'match': 'break', 'context': 'loop_body', 'type': 'keyword', 'insert': 'break', 'detail': 'Exit the current loop immediately.', 'source': 'Context Snippet'},
            {'label': 'continue', 'match': 'continue', 'context': 'loop_body', 'type': 'keyword', 'insert': 'continue', 'detail': 'Skip to the next iteration of the loop.', 'source': 'Context Snippet'},
            {'label': 'def (__init__)', 'match': 'def', 'context': 'class_body_start', 'type': 'constructor', 'insert': 'def __init__(self):\n    pass', 'detail': 'The constructor for a class.\n[code]def __init__(self):\n    pass[/code]', 'source': 'Context Snippet'},
            {'label': 'def (method)', 'match': 'def', 'context': 'class', 'type': 'snippet', 'insert': 'def my_method(self, arg1):\n    pass', 'detail': 'Define a method within a class.\n[code]def my_method(self, arg1):\n    pass[/code]', 'source': 'Context Snippet'}
        ]

    def _on_hover_custom_import(self, event):
        """Shows a generic tooltip for user-defined imports."""
        self._show_tooltip(event, "User-defined module or class import.")

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
        """Applies a subtle highlight and a tooltip to the line that provides context."""
        self.clear_context_highlight()
        tag = "context_highlight_line"
        self.text_area.tag_add(tag, f"{line_number}.0", f"{line_number}.end")
        self.text_area.tag_bind(tag, "<Enter>", 
            lambda e, ln=line_number: self._show_tooltip(e, f"Context-aware completions are active for this block (line {ln})."))
        self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

    def clear_context_highlight(self):
        """Removes the context highlight and unbinds the tooltip from all lines."""
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
        """Shows a tooltip specific to the error on the hovered line."""
        try:
            index = self.text_area.index(f"@{event.x},{event.y}")
            line_number = int(index.split('.')[0])
            if line_number in self.line_error_messages:
                self._show_tooltip(event, self.line_error_messages[line_number])
        except (tk.TclError, ValueError):
            pass

    def _on_hover_standard_lib_module(self, event):
        try:
            # Check for multi-word easter egg first
            line_start_index = self.text_area.index(f"@{event.x},{event.y} linestart")
            line_text = self.text_area.get(line_start_index, f"{line_start_index} lineend")
            braces_key = "from __future__ import braces"
            if braces_key in line_text:
                self._show_tooltip(event, self.easter_egg_tooltips[braces_key])
                return

            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            
            # Check for single-word easter eggs
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

    def perform_autocomplete(self, item):
        self.text_area.edit_separator()
        
        current_line = self.text_area.get("insert linestart", "insert")
        stripped_line = current_line.strip()
        
        if stripped_line.startswith("from ") and " import " in stripped_line:
            parts = current_line.split(" import ")
            base = parts[0] + " import "
            members_part = parts[1].lstrip()
            
            start_index = self.text_area.index("insert linestart")
            if members_part.strip():
                members = [m.strip() for m in members_part.split(',')]
                members[-1] = item['insert']
                new_line = base + ", ".join(members)
            else:
                new_line = base + item['insert']
            
            self.text_area.delete(start_index, "insert lineend")
            self.text_area.insert(start_index, new_line)
            end_index = self.text_area.index(tk.INSERT)

        elif stripped_line.startswith(("import ", "from ")):
             start_index = self.text_area.index("insert linestart")
             words = current_line.split()
             words[-1] = item['insert']
             new_line = " ".join(words)
             self.text_area.delete(start_index, "insert lineend")
             self.text_area.insert(start_index, new_line)
             end_index = self.text_area.index(tk.INSERT)

        else:
            text_to_insert = item['insert']
            word_before_cursor = ""
            try:
                word_before_cursor = self.text_area.get("insert-1c wordstart", "insert")
            except tk.TclError: pass

            # Special case for completing right after the 'except' keyword.
            if item.get('source') in ('Exception', 'Exception Snippet') and word_before_cursor == 'except':
                start_index = self.text_area.index("insert")
                self.text_area.insert(start_index, " " + text_to_insert)
                end_index = self.text_area.index(tk.INSERT)
            else:
                # Default replacement logic for all other scenarios.
                replace_start_index = "insert-1c wordstart"
                try:
                    text_before_cursor = self.text_area.get("insert linestart", "insert")
                    dot_match = re.search(r'\.([\w_]*)$', text_before_cursor)
                    if dot_match:
                        start_offset = dot_match.start(1)
                        line_start_index = self.text_area.index("insert linestart")
                        replace_start_index = f"{line_start_index} + {start_offset} chars"
                except (tk.TclError, IndexError):
                     pass

                start_index = self.text_area.index(replace_start_index)
                self.text_area.delete(start_index, "insert")
                self.text_area.insert(start_index, text_to_insert)
                end_index = self.text_area.index(tk.INSERT)
        
        self.last_auto_action_details = {'start': start_index, 'end': end_index}
        self.last_action_was_auto_feature = True
        self.text_area.focus_set()
        self.after_idle(self._on_content_changed)

    def _on_backspace(self, event):
        # Handle custom undo for auto-features before default backspace behavior.
        if self.last_action_was_auto_feature and self.last_auto_action_details is None:
            
            # Check for the specific case of undoing an auto-indent on an empty line.
            try:
                cursor_index = self.text_area.index(tk.INSERT)
                line_start = self.text_area.index(f"{cursor_index} linestart")
                text_on_line_before_cursor = self.text_area.get(line_start, cursor_index)
                
                # Condition: The line up to the cursor contains only whitespace, and is not empty.
                # This identifies a line that was just auto-indented.
                if text_on_line_before_cursor and text_on_line_before_cursor.isspace():
                    self.last_action_was_auto_feature = False # Consume the flag
                    
                    # Manually delete one level of indentation (4 spaces) without removing the newline.
                    self.text_area.delete("insert-4c", "insert")
                    
                    self.autocomplete_manager.hide()
                    return "break" # Prevent default backspace behavior.
            except tk.TclError:
                # If an error occurs (e.g., trying to delete past the start of the line),
                # fall through to the generic undo which is safer for other cases like auto-brackets.
                pass

            # If it wasn't an auto-indent (or the check failed), it's likely another
            # auto-feature like bracketing. Use the original, broad undo logic for that.
            self.last_action_was_auto_feature = False
            try:
                self.text_area.edit_undo()
                if self.last_cursor_pos_before_auto_action:
                    self.text_area.mark_set(tk.INSERT, self.last_cursor_pos_before_auto_action)
            except tk.TclError:
                pass # Ignore errors if undo stack is empty.
            self.autocomplete_manager.hide()
            return "break"

        # Reset the flag if a normal backspace occurs outside of the auto-feature undo logic.
        self.last_action_was_auto_feature = False
        self.last_cursor_pos_before_auto_action = None
        
        self.after(50, self._update_autocomplete_display)
        return None # Allow default backspace behavior to proceed.
    
    def _on_ctrl_backspace(self, event):
        self.text_area.delete("insert-1c wordstart", "insert")
        self.autocomplete_manager.hide(); return "break"

    def _on_tab(self, event):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.confirm_selection()
        self.autocomplete_dismissed_word = None; self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    "); return "break"
    
    def _on_return_key(self, event):
        if self.autocomplete_manager.is_visible():
            self.last_auto_action_details = None
            self.last_cursor_pos_before_auto_action = None
            return self.autocomplete_manager.confirm_selection()

        self.autocomplete_dismissed_word = None
        if self.autoindent_var and self.autoindent_var.get():
            self.last_cursor_pos_before_auto_action = self.text_area.index(tk.INSERT)
            self.last_auto_action_details = None # Ensure this is cleared for indent actions
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
        self.autocomplete_dismissed_word = None
        self.text_area.edit_separator()
        self.last_cursor_pos_before_auto_action = self.text_area.index(tk.INSERT)
        self.last_auto_action_details = None # Clear this for bracket completion

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
        """Helper method to apply an error highlight and store the message."""
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
        
        # Handle Easter Egg highlighting first
        for egg in self.easter_egg_tooltips.keys():
            if ' ' in egg: # Special case for 'from __future__ import braces'
                for m in re.finditer(re.escape(egg), content):
                    if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")):
                        self._apply_tag("easter_egg_import", m.start(), m.end())
            else: # Handle single-word easter eggs
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