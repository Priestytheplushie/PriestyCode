import tkinter as tk
from tkinter import ttk
import os

class FileExplorer(tk.Frame):
    def __init__(self, master, project_root, open_file_callback=None):
        super().__init__(master, bg="#2B2B2B")
        self.project_root = project_root
        self.open_file_callback = open_file_callback
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("Treeview",
                             background="#2B2B2B",
                             foreground="white",
                             fieldbackground="#2B2B2B",
                             borderwidth=0)
        self.style.map('Treeview', background=[('selected', '#555555')])

        self.tree = ttk.Treeview(self, show="tree headings", selectmode="browse")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure('folder', foreground='white')
        self.tree.tag_configure('file', foreground='white')

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
    def on_select(self, event):
        selected_item = self.tree.selection()[0]
        file_path = self.tree.item(selected_item, "values")[0]
        if os.path.isfile(file_path) and self.open_file_callback:
            self.open_file_callback(file_path)


    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.add_node("", self.project_root)

    def add_node(self, parent_node, path):
        for item in sorted(os.listdir(path)):
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                node = self.tree.insert(parent_node, "end", text=item, values=[full_path], open=False, tags=('folder',))
                self.add_node(node, full_path)
            else:
                self.tree.insert(parent_node, "end", text=item, values=[full_path], tags=('file',))
