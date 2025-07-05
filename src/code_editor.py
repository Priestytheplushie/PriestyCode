# code_editor.py

import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import re
import ast
import os
import inspect

class LocalVariableVisitor(ast.NodeVisitor):
    """An AST visitor specifically for finding variables within a single function's scope."""
    def __init__(self):
        self.variables = set()

    def visit_arg(self, node: ast.arg):
        self.variables.add(node.arg)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables.add(target.id)
        self.generic_visit(node)
    
    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self.variables.add(name)
        self.generic_visit(node)

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
        self.definitions.clear()
        try:
            self.tree = ast.parse(code)
            self._traverse(self.tree)
        except (SyntaxError, ValueError):
            self.tree = None

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
        if not (0 < line_number <= len(lines)): return None
        try:
            current_indent = len(lines[line_number - 1]) - len(lines[line_number - 1].lstrip(' '))
        except IndexError: return None

        for i in range(line_number - 2, -1, -1):
            line = lines[i]
            line_indent = len(line) - len(line.lstrip(' '))
            if line_indent < current_indent:
                stripped_line = line.strip()
                if stripped_line.startswith('class '):
                    class_def_line_index = i
                    has_content_after_class_def = False
                    for j in range(class_def_line_index + 1, line_number - 1):
                        if lines[j].strip():
                            has_content_after_class_def = True
                            break
                    return 'class' if has_content_after_class_def else 'class_body_start'
        
        for i in range(line_number - 2, -1, -1):
            line = lines[i]
            line_indent = len(line) - len(line.lstrip(' '))
            if line_indent < current_indent:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith('#'): continue
                if stripped_line.startswith(('def ', 'async def ')): return 'function'
                if stripped_line.startswith('try:'): return 'try'
                return None
        return None

    def get_definitions(self):
        return self.definitions

    def get_scope_completions(self, line_number):
        if not self.tree: return []
        visitor = ScopeVisitor(line_number)
        visitor.visit(self.tree)
        return list(visitor.variables_in_scope)


class ScopeVisitor(ast.NodeVisitor):
    def __init__(self, target_line):
        self.target_line = target_line
        self.variables_in_scope = set()
        self._current_scope_node = None

    def visit(self, node):
        if (hasattr(node, 'lineno') and node.lineno <= self.target_line and #type: ignore
            hasattr(node, 'end_lineno') and node.end_lineno >= self.target_line): #type: ignore
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                self._current_scope_node = node
        
        if self._current_scope_node and hasattr(node, 'lineno') and node.lineno < self.target_line: # type: ignore
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
                self.variables_in_scope.add(node.id)
            elif isinstance(node, ast.arg):
                self.variables_in_scope.add(node.arg)
        super().generic_visit(node)


class AutocompleteManager:
    def __init__(self, editor_instance, icons=None):
        self.editor = editor_instance
        self.text_area = editor_instance.text_area
        self.icons = icons if icons is not None else {}
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
        self.preview_text = tk.Text(preview_frame, wrap="word", bg="#2B2B2B", fg="white",font=("Consolas", 9), state="disabled", borderwidth=0,highlightthickness=0)
        self.preview_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.preview_text.tag_config("type", foreground="#AAAAAA")
        self.preview_text.tag_config("label", foreground="white", font=("Consolas", 9, "bold"))
        self.preview_text.tag_config("detail", foreground="#AAAAAA")
        paned_window.add(preview_frame, weight=3)
        self.completions = []
        self._configure_treeview()

    def _configure_treeview(self):
        self.style.configure('Autocomplete.TPanedwindow', sashwidth=2, background="#3C3C3C")
        # Use a font that is likely to support the Unicode symbols
        font_name = "Segoe UI Symbol" if os.name == 'nt' else "Arial"
        self.style.configure("Custom.Treeview", background="#3C3C3C", foreground="white",
                             fieldbackground="#3C3C3C", borderwidth=0, rowheight=22,
                             font=(font_name, 10))
        self.style.map('Custom.Treeview', background=[('selected', '#555555')])
        self.style.layout("Custom.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        self.tree.config(style="Custom.Treeview")
        self.tree.heading('#0', text='')
        # New tag colors based on spec
        self.tree.tag_configure('variable', foreground='#80D0FF') # Light Blue
        self.tree.tag_configure('snippet', foreground='#80D0FF') # Cyan
        self.tree.tag_configure('keyword', foreground='#FFFFFF') # White
        self.tree.tag_configure('constant', foreground='#FFA500') # Orange
        self.tree.tag_configure('function', foreground='#A3E8A3') # Light Green
        self.tree.tag_configure('method', foreground='#A3E8A3') # Light Green
        self.tree.tag_configure('constructor', foreground='#C586C0') # Light Purple
        self.tree.tag_configure('class', foreground='#4EC9B0') # Teal (default)
        self.tree.tag_configure('module', foreground='#FFD700') # Gold
        self.tree.bind('<<TreeviewSelect>>', self.update_preview)
        self.tree.bind('<Return>', self.confirm_selection)
        self.tree.bind('<Tab>', self.confirm_selection)
        self.tree.bind('<Double-1>', self.confirm_selection)
        
    def show(self, completions, bbox):
        if not completions or not bbox: self.hide(); return
        self.completions = completions
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(completions):
            item_type = item.get('type', 'variable')
            symbol = self.icons.get(item_type, ' ')
            self.tree.insert('', 'end', iid=i, text=f" {symbol} {item['label']}", tags=(item_type,))
            
        num_items = len(completions)
        new_height = min(num_items, 10) * 22 + 6
        if not self.window.winfo_viewable():
            x, y, _, h = bbox
            x += self.text_area.winfo_rootx(); y += self.text_area.winfo_rooty() + h
            self.window.geometry(f"550x{new_height}+{x}+{y}")
            self.window.deiconify(); self.window.lift()
        else:
            current_x, current_y = self.window.winfo_x(), self.window.winfo_y()
            self.window.geometry(f"550x{new_height}+{current_x}+{current_y}")
        if self.tree.get_children():
            self.tree.selection_set('0'); self.tree.focus('0')

    def hide(self): self.window.withdraw()
    def is_visible(self): return self.window.winfo_viewable()
    
    def update_preview(self, event=None):
        selected_ids = self.tree.selection()
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        if selected_ids:
            selected_index = int(selected_ids[0])
            item = self.completions[selected_index]
            source_text = item.get('type', 'suggestion').capitalize()
            detail = item.get('detail', '')
            self.preview_text.insert("end", f"({source_text}) ", "type")
            self.preview_text.insert("end", f"{item.get('label')}\n", "label")
            if detail:
                self.preview_text.insert("end", "-----------------\n", "detail")
                self.preview_text.insert("end", detail, "detail")
        self.preview_text.config(state="disabled")

    def confirm_selection(self, event=None):
        if not self.is_visible(): return 'break'
        selected_ids = self.tree.selection()
        if not selected_ids: return 'break'
        selected_index = int(selected_ids[0])
        item = self.completions[selected_index]
        self.editor.perform_autocomplete(item)
        self.hide(); return 'break'
        
    def navigate(self, direction):
        if not self.is_visible(): return
        current_focus = self.tree.focus()
        if not current_focus: return
        next_item = self.tree.next(current_focus) if direction > 0 else self.tree.prev(current_focus)
        if next_item:
            self.tree.selection_set(next_item); self.tree.focus(next_item); self.tree.see(next_item)
        return 'break'

class CodeEditor(tk.Frame):
    def __init__(self, master=None, error_console=None, autocomplete_icons=None, 
                 autoindent_var=None, tooltips_var=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config(bg="#2B2B2B")
        self.error_console = error_console
        self.last_action_was_auto_feature = False
        self.autocomplete_active = True
        self.proactive_errors_active = True
        self.autocomplete_dismissed_word = None
        self.manual_trigger_active = False
        self.imported_aliases = {}
        self.code_analyzer = CodeAnalyzer()
        self.autoindent_var = autoindent_var
        self.tooltips_var = tooltips_var
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
        self.error_tooltip_text = ""
        # Use a map of unicode symbols instead of image icons now
        self.autocomplete_icons = {
            'snippet': '▶', 'keyword': '🝰', 'function': 'ƒ', 'method': '𝘮',
            'constructor': '⊕', 'constant': 'π', 'variable': 'ⓥ', 'module': '📦',
            'class': '🅒' # Default for classes
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
        self.autocomplete_manager.preview_text.config(font=ac_preview_font)
        tooltip_font = ("Consolas", max(8, size - 1))
        self.tooltip_label.config(font=tooltip_font)
        self.update_line_numbers()
        
    def set_file_path(self, path: str):
        self.file_path = path

    def set_proactive_error_checking(self, is_active: bool):
        self.proactive_errors_active = is_active
        if not is_active: self.clear_error_highlight()
        else: self._proactive_syntax_check()
    
    def _get_local_completions(self, line_num: int, all_text: str):
        lines = all_text.splitlines()
        if not (0 < line_num <= len(lines)): return set()

        start_line_index, func_indent = -1, -1
        try:
            current_line_indent = len(lines[line_num - 1]) - len(lines[line_num - 1].lstrip(' '))
        except IndexError:
            return set()

        for i in range(line_num - 1, -1, -1):
            line = lines[i]
            indent = len(line) - len(line.lstrip(' '))
            if line.strip().startswith(('def ', 'async def ')) and indent < current_line_indent:
                func_indent, start_line_index = indent, i; break
        
        if start_line_index == -1: return set()

        func_lines = []
        for i in range(start_line_index, len(lines)):
            line = lines[i]
            if i > start_line_index:
                indent = len(line) - len(line.lstrip(' '))
                if line.strip() and indent <= func_indent: break
            func_lines.append(line)
        
        func_code_block = "\n".join(func_lines)
        
        try:
            unindented_code = re.sub(r'^\s{' + str(func_indent) + '}', '', func_code_block, flags=re.MULTILINE)
            tree = ast.parse(unindented_code)
            visitor = LocalVariableVisitor(); visitor.visit(tree)
            return visitor.variables
        except SyntaxError: return set()
    
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
                item_type = 'method' if is_method else 'variable'
                if attr == '__init__':
                    item_type = 'constructor'
                detail = f"{'Method' if is_method else 'Attribute'} of the current class."
                completions.append({'label': attr, 'type': item_type, 'insert': attr, 'detail': detail, 'source': 'Class Member'})
        except SyntaxError: 
            pass 
        return completions

    def _update_autocomplete_display(self, manual_trigger=False):
        # Priority Mapping:
        # 0: Context-Aware (Locals, self, context snippets)
        # 1: General-purpose Snippets
        # 2: Raw Structural Keywords
        # 3: Common Built-in Functions
        # 4: Raw Constants
        # 5: Project-Wide Symbols
        # 6: Standard Library
        # 7: "Found in Document" words
        
        if not self.autocomplete_active: self.autocomplete_manager.hide(); return
        try:
            insert_index = self.text_area.index(tk.INSERT)
            line_start_index = self.text_area.index(f"{insert_index} linestart")
            text_before_cursor = self.text_area.get(line_start_index, insert_index)
            dot_match = re.search(r'(\b[\w_]+)\.([\w_]*)$', text_before_cursor)

            if dot_match:
                base_word, partial_member = dot_match.group(1), dot_match.group(2)
                completions = []
                partial_member_lower = partial_member.lower()

                if base_word == 'self':
                    all_self_members = self._get_self_completions()
                    for member in all_self_members:
                        if member['label'].lower().startswith(partial_member_lower):
                            member['priority'] = 0
                            completions.append(member)
                else:
                    real_module = self.imported_aliases.get(base_word)
                    base_module_name = real_module.split('.')[0] if real_module else None
                    if base_module_name and base_module_name in self.standard_libraries:
                        for member_name in self.standard_libraries[base_module_name].get('members', []):
                            if member_name.lower().startswith(partial_member_lower):
                                completions.append({
                                    'label': member_name, 'type': 'function', 'insert': member_name,
                                    'detail': self.standard_library_function_tooltips.get(f"{base_module_name}.{member_name}", "Standard library member."),
                                    'source': 'Standard Library', 'priority': 6
                                })

                completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
                bbox = self.text_area.bbox(tk.INSERT)
                if completions and bbox: self.autocomplete_manager.show(completions, bbox)
                else: self.autocomplete_manager.hide()
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

        def add_completion(item, priority):
            if item.get('label') and item['label'] not in labels_so_far:
                item['priority'] = priority; labels_so_far.add(item['label']); completions.append(item)

        scope_context = self.code_analyzer.get_scope_context(current_line_num, all_text)

        # A single loop over snippets ensures context is handled correctly.
        for s in self.snippets:
            is_prefix_match = manual_trigger or s['match'].lower().startswith(current_word_lower)
            if not is_prefix_match: continue
            
            s_context = s.get('context')
            # If a snippet has a context, it's a high-priority context-aware item (Priority 0)
            if s_context:
                # Check for context match. `class_body_start` is a special case for `class` context.
                if s_context == scope_context or (s_context == 'class' and scope_context == 'class_body_start'):
                    add_completion({**s, 'source': 'Context Snippet'}, 0)
            # If a snippet has NO context, it's a general-purpose item (Priority 1)
            else:
                add_completion({**s, 'source': 'Snippet'}, 1)

        # Priority 0: Local variables
        local_vars = self._get_local_completions(current_line_num, all_text)
        for var in local_vars:
            if var.lower().startswith(current_word_lower): add_completion({'label': var, 'type': 'variable', 'insert': var, 'detail': 'Local variable or parameter.', 'source': 'Local Scope'}, 0)

        # Priority 2: Raw structural keywords
        for k in self.raw_keywords:
            if k['type'] == 'keyword':
                is_prefix_match = manual_trigger or k['label'].lower().startswith(current_word_lower)
                if is_prefix_match:
                    add_completion(k, 2)
        
        # Priority 3: Common built-in functions
        for k in self.raw_keywords:
            if k['type'] == 'function':
                is_prefix_match = manual_trigger or k['label'].lower().startswith(current_word_lower)
                if is_prefix_match:
                    add_completion(k, 3)

        # Priority 4: Raw constants
        for k in self.raw_keywords:
            if k['type'] == 'constant':
                is_prefix_match = manual_trigger or k['label'].lower().startswith(current_word_lower)
                if is_prefix_match:
                    add_completion(k, 4)

        # Priority 5: Project-wide symbols
        user_defs = self.code_analyzer.get_definitions()
        for name, info in user_defs.items():
            if name.lower().startswith(current_word_lower): 
                item_type = info['type']
                if item_type == 'function':
                    for i in range(info['lineno'] - 2, -1, -1):
                        line = all_text.splitlines()[i]
                        if line.strip().startswith('class '):
                            item_type = 'method'; break
                if name == '__init__': item_type = 'constructor'
                add_completion({'label': name, 'type': item_type, 'insert': name, 'detail': info['docstring'], 'source': 'User-defined'}, 5)
        
        # Priority 6: Standard library modules
        for m in self.standard_libraries:
            if m.lower().startswith(current_word_lower): add_completion({'label': m, 'type': 'module', 'insert': m, 'detail': self.standard_libraries[m].get('tooltip', 'Standard library module.'), 'source': 'Standard Library'}, 6)
        
        # Priority 7: "Found in Document" words
        if current_word:
            words_in_doc = set(re.findall(r'\b[a-z_][a-z0-9_]{2,}\b', all_text, re.IGNORECASE))
            for w in sorted(list(words_in_doc)):
                if w.lower().startswith(current_word_lower) and w not in labels_so_far: add_completion({'label': w, 'type': 'variable', 'insert': w, 'detail': 'Word found elsewhere in the document.', 'source': 'From Document'}, 7)
        
        completions.sort(key=lambda x: (x.get('priority', 99), x['label']))
        if completions:
            bbox = self.text_area.bbox(tk.INSERT)
            if bbox: self.autocomplete_manager.show(completions, bbox)
        else: self.autocomplete_manager.hide()

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
        if not event: return

        if self.manual_trigger_active:
            self.manual_trigger_active = False
            return

        self.last_action_was_auto_feature = False
        if event.keysym not in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "parenleft"):
            self._hide_tooltip()
        
        if event.keysym in ("Up", "Down", "Return", "Tab", "Escape", "period", "Control_L", "Control_R"): return
        
        self.after(50, self._update_autocomplete_display)

    def _on_click(self, event=None):
        self.autocomplete_manager.hide()
        self._hide_tooltip()
        self.autocomplete_dismissed_word = None
        self.last_action_was_auto_feature = False

    def _on_arrow_up(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(-1)
        return None

    def _on_arrow_down(self, event=None):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.navigate(1)
        return None
        
    def _on_text_modified(self, event=None):
        if self.text_area.edit_modified():
            if not self.last_action_was_auto_feature:
                 self.last_action_was_auto_feature = False

            self.text_area.event_generate("<<Change>>")
            self._on_content_changed()
            self.text_area.edit_modified(False)

    def _on_mouse_scroll(self, event):
        self.autocomplete_manager.hide()
        self.after(10, self.update_line_numbers)

    def _configure_autocomplete_data(self):
        # NEW: Separate list for raw keywords to avoid conflicts with snippets
        self.raw_keywords = [
            # Keywords
            {'label': 'and', 'type': 'keyword', 'insert': 'and '}, {'label': 'as', 'type': 'keyword', 'insert': 'as '},
            {'label': 'assert', 'type': 'keyword', 'insert': 'assert '}, {'label': 'async', 'type': 'keyword', 'insert': 'async '},
            {'label': 'await', 'type': 'keyword', 'insert': 'await '}, {'label': 'break', 'type': 'keyword', 'insert': 'break'},
            {'label': 'class', 'type': 'keyword', 'insert': 'class '}, {'label': 'continue', 'type': 'keyword', 'insert': 'continue'},
            {'label': 'def', 'type': 'keyword', 'insert': 'def '}, {'label': 'del', 'type': 'keyword', 'insert': 'del '},
            {'label': 'elif', 'type': 'keyword', 'insert': 'elif '}, {'label': 'else', 'type': 'keyword', 'insert': 'else'},
            {'label': 'except', 'type': 'keyword', 'insert': 'except '}, {'label': 'finally', 'type': 'keyword', 'insert': 'finally'},
            {'label': 'for', 'type': 'keyword', 'insert': 'for '}, {'label': 'from', 'type': 'keyword', 'insert': 'from '},
            {'label': 'global', 'type': 'keyword', 'insert': 'global '}, {'label': 'if', 'type': 'keyword', 'insert': 'if '},
            {'label': 'import', 'type': 'keyword', 'insert': 'import '}, {'label': 'in', 'type': 'keyword', 'insert': 'in '},
            {'label': 'is', 'type': 'keyword', 'insert': 'is '}, {'label': 'lambda', 'type': 'keyword', 'insert': 'lambda '},
            {'label': 'nonlocal', 'type': 'keyword', 'insert': 'nonlocal '}, {'label': 'not', 'type': 'keyword', 'insert': 'not '},
            {'label': 'or', 'type': 'keyword', 'insert': 'or '}, {'label': 'pass', 'type': 'keyword', 'insert': 'pass'},
            {'label': 'raise', 'type': 'keyword', 'insert': 'raise '}, {'label': 'return', 'type': 'keyword', 'insert': 'return'},
            {'label': 'try', 'type': 'keyword', 'insert': 'try'}, {'label': 'while', 'type': 'keyword', 'insert': 'while '},
            {'label': 'with', 'type': 'keyword', 'insert': 'with '}, {'label': 'yield', 'type': 'keyword', 'insert': 'yield '},
            {'label': 'self', 'type': 'keyword', 'insert': 'self'},
            # Constants
            {'label': 'True', 'type': 'constant', 'insert': 'True'}, {'label': 'False', 'type': 'constant', 'insert': 'False'},
            {'label': 'None', 'type': 'constant', 'insert': 'None'},
            # Common built-in functions
            {'label': 'print', 'type': 'function', 'insert': 'print()'}, {'label': 'len', 'type': 'function', 'insert': 'len()'},
            {'label': 'range', 'type': 'function', 'insert': 'range()'}, {'label': 'str', 'type': 'function', 'insert': 'str()'},
            {'label': 'int', 'type': 'function', 'insert': 'int()'}, {'label': 'list', 'type': 'function', 'insert': 'list()'},
            {'label': 'dict', 'type': 'function', 'insert': 'dict()'}, {'label': 'set', 'type': 'function', 'insert': 'set()'},
            {'label': 'open', 'type': 'function', 'insert': 'open()'}, {'label': 'type', 'type': 'function', 'insert': 'type()'}
        ]

        # FIX: Snippet for __init__ now matches 'def' and has a better label and context.
        self.snippets = [
            {'label': 'def (function)', 'match': 'def', 'type': 'snippet', 'insert': 'def function_name(params):\n    pass', 'detail': 'Define a new function.'},
            {'label': 'class (definition)', 'match': 'class', 'type': 'snippet', 'insert': 'class NewClass:\n    pass', 'detail': 'Define a new class.'},
            {'label': 'if (statement)', 'match': 'if', 'type': 'snippet', 'insert': 'if condition:\n    pass', 'detail': 'If statement.'},
            {'label': 'for (loop)', 'match': 'for', 'type': 'snippet', 'insert': 'for item in iterable:\n    pass', 'detail': 'For loop.'},
            {'label': 'while (loop)', 'match': 'while', 'type': 'snippet', 'insert': 'while condition:\n    pass', 'detail': 'While loop.'},
            {'label': 'with (context)', 'match': 'with', 'type': 'snippet', 'insert': 'with open("file.txt") as f:\n    ', 'detail': 'Context manager.'},
            {'label': 'try/except (block)', 'match': 'try', 'type': 'snippet', 'insert': 'try:\n    pass\nexcept Exception as e:\n    print(e)', 'detail': 'Exception handling block.'},
            {'label': 'if __name__ == "__main__"', 'match': 'ifmain', 'type': 'snippet', 'insert': 'if __name__ == "__main__":\n    pass', 'detail': 'Standard boilerplate for making a script executable.'},
            # Context-specific snippets
            {'label': 'def (__init__)', 'match': 'def', 'context': 'class_body_start', 'type': 'constructor', 'insert': 'def __init__(self):\n    pass', 'detail': 'Class constructor method.'},
            {'label': 'def (method)', 'match': 'def', 'context': 'class', 'type': 'snippet', 'insert': 'def my_method(self, arg1):\n    pass', 'detail': 'Define a new class method.'}
        ]
        
        self.builtin_list = ['abs', 'all', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip']
        self.exception_list = ['Exception', 'BaseException', 'ArithmeticError', 'AssertionError', 'AttributeError', 'EOFError', 'ImportError', 'ModuleNotFoundError', 'IndexError', 'KeyError', 'KeyboardInterrupt', 'MemoryError', 'NameError', 'NotImplementedError', 'OSError', 'OverflowError', 'RecursionError', 'RuntimeError', 'SyntaxError', 'SystemError', 'TypeError', 'ValueError', 'ZeroDivisionError', 'FileNotFoundError', 'PermissionError', 'TimeoutError', 'ConnectionError']
        self.exception_tooltips = {'Exception': 'Common base class for all non-exit exceptions.', 'BaseException': 'The base class for all built-in exceptions.', 'ArithmeticError': 'Base class for arithmetic errors.', 'AssertionError': 'Raised when an assert statement fails.', 'AttributeError': 'Raised when an attribute reference or assignment fails.', 'EOFError': 'Raised when input() hits an end-of-file condition (EOF).', 'ImportError': 'Raised when an import statement has trouble trying to load a module.', 'ModuleNotFoundError': 'A subclass of ImportError; raised when a module could not be found.', 'IndexError': 'Raised when a sequence subscript is out of range.', 'KeyError': 'Raised when a mapping (dictionary) key is not found.', 'KeyboardInterrupt': 'Raised when the user hits the interrupt key (normally Ctrl+C).', 'MemoryError': 'Raised when an operation runs out of memory.', 'NameError': 'Raised when a local or global name is not found.', 'NotImplementedError': 'Raised by abstract methods.', 'OSError': 'Raised for system-related errors.', 'OverflowError': 'Raised when the result of an arithmetic operation is too large to be represented.', 'RecursionError': 'Raised when the maximum recursion depth is exceeded.', 'RuntimeError': 'Raised when an error is detected that doesn’t fall in any of the other categories.', 'SyntaxError': 'Raised when the parser encounters a syntax error.', 'SystemError': 'Raised for interpreter-level errors.', 'TypeError': 'Raised when an operation or function is applied to an object of inappropriate type.', 'ValueError': 'Raised when a function receives an argument of the correct type but an inappropriate value.', 'ZeroDivisionError': 'Raised when the second argument of a division or modulo operation is zero.', 'FileNotFoundError': 'Raised when a file or directory is requested but doesn’t exist.', 'PermissionError': 'Raised when trying to run an operation without the adequate access rights.', 'TimeoutError': 'Raised when a system function timed out at the system level.', 'ConnectionError': 'A base class for connection-related issues.'}
        self.standard_libraries = {'os': {'members': ['path', 'name', 'environ', 'getcwd', 'listdir', 'mkdir', 'makedirs', 'remove', 'removedirs', 'rename', 'rmdir', 'stat', 'system'], 'tooltip': 'Operating system interfaces.'}, 'sys': {'members': ['argv', 'exit', 'path', 'platform', 'stdin', 'stdout', 'stderr', 'version'], 'tooltip': 'System-specific parameters and functions.'}, 're': {'members': ['search', 'match', 'fullmatch', 'split', 'findall', 'finditer', 'sub', 'compile', 'escape'], 'tooltip': 'Regular expression operations.'}, 'json': {'members': ['dump', 'dumps', 'load', 'loads'], 'tooltip': 'JSON encoder and decoder.'}, 'datetime': {'members': ['datetime', 'date', 'time', 'timedelta', 'timezone', 'now', 'utcnow'], 'tooltip': 'Classes for manipulating dates and times.'}, 'math': {'members': ['ceil', 'floor', 'sqrt', 'pi', 'e', 'sin', 'cos', 'tan', 'log', 'log10', 'pow', 'fabs'], 'tooltip': 'Mathematical functions.'}, 'random': {'members': ['random', 'randint', 'choice', 'choices', 'shuffle', 'uniform'], 'tooltip': 'Generate pseudo-random numbers.'}, 'subprocess': {'members': ['run', 'Popen', 'call', 'check_call', 'check_output', 'PIPE', 'STDOUT'], 'tooltip': 'Subprocess management.'}, 'threading': {'members': ['Thread', 'Lock', 'Event', 'Semaphore', 'current_thread'], 'tooltip': 'Thread-based parallelism.'}, 'collections': {'members': ['defaultdict', 'Counter', 'deque', 'namedtuple', 'OrderedDict'], 'tooltip': 'High-performance container datatypes.'}, 'tkinter': {'members': ['Tk', 'Frame', 'Button', 'Label', 'Entry', 'Text', 'ttk', 'filedialog', 'messagebox'], 'tooltip': 'The standard Python interface to the Tcl/Tk GUI toolkit.'}, 'traceback': {'members': ['print_exc', 'format_exc', 'extract_stack'], 'tooltip': 'Print or retrieve a stack traceback.'}, 'time': {'members': ['time', 'sleep', 'asctime'], 'tooltip': 'Time access and conversions.'}}
        self.standard_library_function_tooltips = {'os.path': 'Common pathname manipulations.', 'os.path.join': 'os.path.join(*paths) -> str\nJoin one or more path components intelligently.', 'os.path.exists': 'os.path.exists(path) -> bool\nReturn True if path refers to an existing path.', 'os.path.isdir': 'os.path.isdir(path) -> bool\nReturn True if path is an existing directory.', 'os.path.isfile': 'os.path.isfile(path) -> bool\nReturn True if path is an existing regular file.', 'os.getcwd': 'os.getcwd() -> str\nReturn a string representing the current working directory.', 'os.listdir': 'os.listdir(path=".") -> list\nReturn a list of entry names in the directory.', 'sys.exit': 'sys.exit(status=0)\nExit from Python by raising SystemExit.', 'sys.argv': 'A list of command-line arguments passed to a script.', 're.search': 're.search(pattern, string) -> Match or None\nScan string for a match to the pattern.', 're.match': 're.match(pattern, string) -> Match or None\nTry to apply the pattern at the start of the string.', 're.findall': 're.findall(pattern, string) -> list\nReturn all non-overlapping matches of pattern in string.', 're.sub': 're.sub(pattern, repl, string) -> str\nReturn string obtained by replacing occurrences of pattern.', 'json.loads': 'json.loads(s) -> object\nDeserialize a JSON formatted str to a Python object.', 'json.dumps': 'json.dumps(obj) -> str\nSerialize a Python object to a JSON formatted str.', 'json.load': 'json.load(fp) -> object\nDeserialize a file-like object with a JSON document.', 'json.dump': 'json.dump(obj, fp)\nSerialize a Python object to a JSON formatted stream.', 'datetime.datetime.now': 'datetime.datetime.now(tz=None) -> datetime\nReturn the current local date and time.', 'random.randint': 'random.randint(a, b) -> int\nReturn a random integer N such that a <= N <= b.', 'random.choice': 'random.choice(seq)\nReturn a random element from the non-empty sequence.', 'threading.Thread': 'A class that represents a thread of control.', 'tkinter.ttk': 'Themed widget set for Tkinter.', 'tkinter.filedialog': 'Dialogs for file/directory selection.', 'traceback.print_exc': 'traceback.print_exc()\nPrint exception information and stack trace to stderr.'}
        self.builtin_tooltips = {'print': 'print(*objects, sep=\' \', end=\'\\n\')\nPrints objects to the text stream.', 'len': 'len(obj)\nReturns the number of items in an object.', 'str': 'str(object=\'\') -> str\nReturns a string version of an object.', 'int': 'int(x, base=10) -> integer\nConverts a value to an integer.', 'list': 'list(iterable) -> new list\nCreates a new list from an iterable.', 'dict': 'dict(**kwarg) -> new dictionary\nCreates a new dictionary.', 'range': 'range(start, stop[, step])\nReturns an immutable sequence of numbers.', 'open': 'open(file, mode=\'r\', ...) -> file object\nOpens a file.'}

    def _configure_tags_and_tooltips(self):
        font_size_str = self.text_area.cget("font").split()[1]
        font_size = int(font_size_str) if font_size_str.isdigit() else 10
        bold_font = ("Consolas", font_size, "bold")
        tag_configs = {"reactive_error_line": {"background": "#FF4C4C"}, "handled_exception_line": {"background": "#FFA500"},"proactive_error_line": {"background": "#b3b300"},"function_definition": {"foreground": "#DCDCAA"},"class_definition": {"foreground": "#4EC9B0"},"function_call": {"foreground": "#DCDCAA"}, "class_usage": {"foreground": "#4EC9B0"}, "fstring_expression": {"foreground": "#CE9178", "background": "#3a3a3a"}, "self_keyword": {"foreground": "#DA70D6"}, "self_method_call": {"foreground": "#9CDCFE"},"priesty_keyword": {"foreground": "#DA70D6"}, "def_keyword": {"foreground": "#569CD6", "font": bold_font},"class_keyword": {"foreground": "#569CD6", "font": bold_font}, "keyword_control": {"foreground": "#C586C0"},"keyword_import": {"foreground": "#4EC9B0"},"keyword_exception": {"foreground": "#D16969"}, "keyword_boolean_null": {"foreground": "#569CD6"},"keyword_logical": {"foreground": "#DCDCAA"}, "keyword_async": {"foreground": "#FFD700"},"keyword_context": {"foreground": "#CE9178"}, "string_literal": {"foreground": "#A3C78B"}, "number_literal": {"foreground": "#B5CEA8"},"comment_tag": {"foreground": "#6A9955"}, "function_param": {"foreground": "#9CDCFE"},"bracket_tag": {"foreground": "#FFD700"}, "builtin_function": {"foreground": "#DCDCAA"},"exception_type": {"foreground": "#4EC9B0"}, "dunder_method": {"foreground": "#DA70D6"},"standard_library_module": {"foreground": "#4EC9B0"}, "custom_import": {"foreground": "#9CDCFE"},"standard_library_function": {"foreground": "#DCDCAA"}}
        for tag, config in tag_configs.items(): self.text_area.tag_configure(tag, **config)
        tag_tooltips = {"def_keyword": "def function_name(params):\n    ...\n\nDefines a function.", "class_keyword": "class ClassName(ParentClass):\n    ...\n\nDefines a class.", "keyword_control": "A control flow keyword (e.g., if, for, return, global).", "keyword_import": "import module\n\nBrings a module into the current scope.", "keyword_exception": "try:\n    ...\n\nStarts a block to test for errors, or handles one.", "custom_import": "A user-defined or third-party import.", "self_keyword": "Refers to the instance of the class."}
        self.dunder_tooltips = {'__init__': '__init__(self, ...)\n\nThe constructor method for a class.', '__str__': '__str__(self) -> str\n\nReturns the printable string representation of an object.'}
        def create_tooltip_handler(tooltip_text):
            return lambda event: self._show_tooltip(event, tooltip_text) if not any(tag in self.text_area.tag_names(f"@{event.x},{event.y}") for tag in ["reactive_error_line", "proactive_error_line"]) else None
        for tag, text in tag_tooltips.items():
            self.text_area.tag_bind(tag, "<Enter>", create_tooltip_handler(text)); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        def create_word_hover_handler(tooltip_dict):
            return lambda event: self._on_hover_word(event, tooltip_dict) if not any(tag in self.text_area.tag_names(f"@{event.x},{event.y}") for tag in ["reactive_error_line", "proactive_error_line"]) else None
        for tag, t_dict in [("builtin_function", self.builtin_tooltips), ("exception_type", self.exception_tooltips), ("dunder_method", self.dunder_tooltips)]:
            self.text_area.tag_bind(tag, "<Enter>", create_word_hover_handler(t_dict)); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        for tag in ["function_call", "class_usage"]:
            self.text_area.tag_bind(tag, "<Enter>", self._on_hover_user_defined); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        for tag in ["standard_library_module", "standard_library_function"]:
            handler = self._on_hover_standard_lib_module if 'module' in tag else self._on_hover_standard_lib_function
            self.text_area.tag_bind(tag, "<Enter>", handler); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)
        for tag in ["reactive_error_line", "proactive_error_line", "handled_exception_line"]:
            self.text_area.tag_bind(tag, "<Enter>", lambda e: self._show_tooltip(e, self.error_tooltip_text)); self.text_area.tag_bind(tag, "<Leave>", self._hide_tooltip)

    def _on_hover_user_defined(self, event):
        try:
            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            definitions = self.code_analyzer.get_definitions()
            if word in definitions: self._show_tooltip(event, definitions[word]['docstring'])
        except tk.TclError: pass

    def _on_hover_standard_lib_module(self, event):
        try:
            word = self.text_area.get(f"@{event.x},{event.y} wordstart", f"@{event.x},{event.y} wordend")
            real_module = self.imported_aliases.get(word)
            base_module = real_module.split('.')[0] if real_module else None
            if base_module and base_module in self.standard_libraries:
                self._show_tooltip(event, self.standard_libraries[base_module].get('tooltip', 'Standard library module.'))
        except tk.TclError: pass

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
        text_to_insert = item['insert']
        
        replace_start_index = "insert-1c wordstart"
        try:
            text_before_cursor = self.text_area.get("insert linestart", "insert")
            dot_match = re.search(r'\.([\w_]*)$', text_before_cursor)
            if dot_match:
                start_offset = dot_match.start(1)
                line_start_index = self.text_area.index("insert linestart")
                replace_start_index = f"{line_start_index} + {start_offset} chars"
        except tk.TclError:
             pass

        current_word_start = self.text_area.index(replace_start_index)
        
        if '\n' in text_to_insert:
            try:
                line_start = self.text_area.index(f"{current_word_start} linestart")
                line_text = self.text_area.get(line_start, current_word_start)
                indent_match = re.match(r'^(\s*)', line_text)
                current_indent = indent_match.group(1) if indent_match else ""
                lines = text_to_insert.split('\n')
                processed_text = lines[0] + '\n' + '\n'.join([current_indent + l for l in lines[1:]])
                text_to_insert = processed_text
            except tk.TclError: pass 

        self.text_area.delete(current_word_start, "insert")
        self.text_area.insert(current_word_start, text_to_insert)
        self.last_action_was_auto_feature = True
        self.text_area.focus_set(); self.after_idle(self._on_content_changed)

    def _on_backspace(self, event):
        if self.last_action_was_auto_feature:
            self.last_action_was_auto_feature = False
            try:
                self.text_area.edit_undo()
            except tk.TclError:
                pass
            self.autocomplete_manager.hide()
            return "break"
        
        self.after(50, self._update_autocomplete_display)
        return None
    
    def _on_ctrl_backspace(self, event):
        self.text_area.delete("insert-1c wordstart", "insert")
        self.autocomplete_manager.hide(); return "break"

    def _on_tab(self, event):
        if self.autocomplete_manager.is_visible(): return self.autocomplete_manager.confirm_selection()
        self.autocomplete_dismissed_word = None; self.text_area.edit_separator()
        self.text_area.insert(tk.INSERT, "    "); return "break"
    
    def _on_return_key(self, event):
        if self.autocomplete_manager.is_visible():
            return self.autocomplete_manager.confirm_selection()

        self.autocomplete_dismissed_word = None
        if self.autoindent_var and self.autoindent_var.get():
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
                    
                    self.text_area.insert(tk.INSERT, f"\n{base_indent}    \n{base_indent}")
                    self.text_area.mark_set(tk.INSERT, f"{cursor_index}+{len(base_indent)+5}c")
                    self.last_action_was_auto_feature = True
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
        if self.text_area.tag_ranges("sel"):
            sel_start, sel_end = self.text_area.index("sel.first"), self.text_area.index("sel.last")
            selected_text = self.text_area.get(sel_start, sel_end)
            self.text_area.delete(sel_start, sel_end)
            self.text_area.insert(sel_start, open_char + selected_text + close_char)
        else:
            self.text_area.insert(tk.INSERT, open_char + close_char)
            self.text_area.mark_set(tk.INSERT, "insert-1c")
        if show_signature: self.after(20, self._show_signature_help)
        self.last_action_was_auto_feature = True
        return "break"

    def _auto_indent(self, event):
        self.text_area.edit_separator()

        cursor_index = self.text_area.index(tk.INSERT)
        line_number = int(cursor_index.split('.')[0])
        current_line_content = self.text_area.get(f"{line_number}.0", f"{line_number}.end")
        stripped_line = current_line_content.strip()
        
        parent_indent_str = ""
        for i in range(line_number - 1, 0, -1):
            line = self.text_area.get(f"{i}.0", f"{i}.end")
            if line.strip():
                indent_match = re.match(r'^(\s*)', line)
                parent_indent_str = indent_match.group(1) if indent_match else ""
                break
        
        dedent_and_indent_keywords = ('elif', 'else:', 'except', 'finally:')
        
        current_indent_str_match = re.match(r'^(\s*)', current_line_content)
        current_indent_str = current_indent_str_match.group(1) if current_indent_str_match else ""
        
        next_line_indent_str = current_indent_str
        
        if stripped_line.endswith(':'):
            next_line_indent_str += "    "
            
        if any(stripped_line.startswith(k) for k in dedent_and_indent_keywords):
            self.text_area.delete(f"{line_number}.0", f"{line_number}.{len(current_indent_str)}")
            self.text_area.insert(f"{line_number}.0", parent_indent_str)
            
            next_line_indent_str = parent_indent_str
            if stripped_line.endswith(':'):
                next_line_indent_str += "    "

        self.text_area.insert(tk.INSERT, f'\n{next_line_indent_str}')
        
        self.last_action_was_auto_feature = True
        self.after_idle(self._on_content_changed)
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
        preserved = ("sel", "insert", "current", "reactive_error_line", "proactive_error_line", "handled_exception_line")
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
        for alias, source in self.imported_aliases.items():
            tag = "standard_library_module" if source.split('.')[0] in self.standard_libraries else "custom_import"
            for m in re.finditer(r"\b" + re.escape(alias) + r"\b", content):
                if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal")): self._apply_tag(tag, m.start(), m.end())
        
        static_patterns = { 
            r"\bdef\b": "def_keyword", r"\bclass\b": "class_keyword", 
            r"\b(if|else|elif|for|while|return|break|continue|yield|pass|global|nonlocal|del)\b": "keyword_control",
            r"\b(import|from|as)\b": "keyword_import", 
            r"\b(try|except|finally|raise|assert)\b": "keyword_exception", 
            r"\b(True|False|None)\b": "keyword_boolean_null", 
            r"\b(and|or|not|in|is)\b": "keyword_logical", 
            r"\b(async|await)\b": "keyword_async", r"\b(with|lambda)\b": "keyword_context",
            r"\bPriesty\b": "priesty_keyword", r"\bself\b": "self_keyword",
            r"\b(" + "|".join(self.builtin_list) + r")\b": "builtin_function", 
            r"\b(" + "|".join(self.exception_list) + r")\b": "exception_type", 
            r"[(){}[\]]": "bracket_tag", 
            r"\b(__init__|__str__|__repr__)\b": "dunder_method"}
        for pattern, tag in static_patterns.items():
            for m in re.finditer(pattern, content):
                if not self._is_inside_tag(m.start(), ("comment_tag", "string_literal", "standard_library_module")): self._apply_tag(tag, m.start(), m.end())

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
            self.clear_error_highlight(); return
        code_content = self.text_area.get("1.0", tk.END)
        self.text_area.tag_remove("proactive_error_line", "1.0", tk.END)
        if not code_content.strip():
            if self.error_console: self.error_console.clear()
            return
        try:
            ast.parse(code_content)
            if self.error_console: self.error_console.clear()
            self.clear_error_highlight()
        except SyntaxError as e:
            try:
                cursor_line = int(self.text_area.index(tk.INSERT).split('.')[0])
                if e.lineno == cursor_line: return
            except (ValueError, IndexError): pass
            error_title = f"Syntax Error: {e.msg}"
            self.highlight_syntax_error(e.lineno or 1, error_title)
            if self.error_console:
                fname = os.path.basename(self.file_path) if self.file_path else "<current editor>"
                offset, text = e.offset or 1, e.text or ""
                details = f"File: {fname}\nLine {e.lineno}, Column {offset}\n\n{text.strip()}\n{' ' * (offset - 1)}^"
                self.error_console.display_error(error_title, details)
        except Exception as e:
            if self.error_console: self.error_console.display_error(f"Proactive Check Error: {type(e).__name__}", str(e))