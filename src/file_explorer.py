import tkinter as tk
from tkinter import ttk
import os

class FileExplorer(tk.Frame):
    def __init__(self, master, project_root, open_file_callback,
                 folder_icon=None, python_icon=None, git_icon=None, unknown_icon=None, txt_icon=None):
        super().__init__(master, bg="#2B2B2B")
        self.project_root = project_root
        self.open_file_callback = open_file_callback

        # Store icon references
        self.folder_icon = folder_icon
        self.python_icon = python_icon
        self.git_icon = git_icon
        self.unknown_icon = unknown_icon

        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.tree.bind("<Double-1>", self._on_double_click)

        # Configure Treeview style
        self.style = ttk.Style()
        self.style.configure("Treeview",
                             background="#2B2B2B",
                             foreground="white",
                             fieldbackground="#2B2B2B",
                             bordercolor="#2B2B2B",
                             font=("Segoe UI", 9))
        self.style.map('Treeview',
                       background=[('selected', '#555555')],
                       foreground=[('selected', 'white')])
        self.style.configure("Treeview.Heading",
                             background="#3C3C3C",
                             foreground="white",
                             font=("Segoe UI", 9, "bold"))
        self.style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})]) # Remove border

    def populate_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        # Insert the root directory
        root_name = os.path.basename(self.project_root)
        if not root_name: # For cases like C:/ or /
            root_name = self.project_root
        
        insert_kwargs = {
            "parent": "",
            "index": "end",
            "iid": self.project_root,
            "text": root_name,
            "open": True,
            "tags": ('folder',)
        }
        if self.folder_icon is not None:
            insert_kwargs["image"] = self.folder_icon
        root_node = self.tree.insert(**insert_kwargs)
        self.tree.item(root_node, open=True) # Ensure root is open
        self._add_nodes(root_node, self.project_root)

    def _add_nodes(self, parent_node, path):
        try:
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    insert_kwargs = {
                        "parent": parent_node,
                        "index": "end",
                        "iid": full_path,
                        "text": item,
                        "tags": ('folder',)
                    }
                    if self.folder_icon is not None:
                        insert_kwargs["image"] = self.folder_icon
                    node = self.tree.insert(**insert_kwargs)
                    self._add_nodes(node, full_path)
                else:
                    file_extension = os.path.splitext(item)[1].lower()
                    file_name_lower = item.lower()
                    
                    selected_icon = self.unknown_icon
                    if file_extension == '.py':
                        selected_icon = self.python_icon
                    elif file_name_lower in ['.gitignore', '.gitattributes', '.gitmodules', 'readme.md']:
                        selected_icon = self.git_icon
                    
                    insert_kwargs = {'parent': parent_node, 'index': "end", 'iid': full_path, 'text': item, 'tags': ('file',)}
                    if selected_icon is not None:
                        insert_kwargs['image'] = selected_icon
                    self.tree.insert(**insert_kwargs)
        except Exception as e:
            print(f"Error reading directory {path}: {e}")

    def _on_double_click(self, event):
        item_id = self.tree.selection()[0]
        # The iid of the item is already the full path
        full_path = item_id 
        
        if os.path.isfile(full_path):
            self.open_file_callback(full_path)