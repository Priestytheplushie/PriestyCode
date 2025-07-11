# file_explorer.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
import shutil
import sys
import subprocess


class FileExplorer(tk.Frame):
    def __init__(
        self,
        master,
        parent,
        project_root,
        open_file_callback,
        folder_icon=None,
        python_icon=None,
        git_icon=None,
        unknown_icon=None,
        txt_icon=None,
        md_icon=None,
    ):
        super().__init__(master, bg="#2B2B2B")
        self.parent = parent  # The main PriestyCode instance
        self.project_root = project_root
        self.open_file_callback = open_file_callback

        self.folder_icon = folder_icon
        self.python_icon = python_icon
        self.git_icon = git_icon
        self.unknown_icon = unknown_icon
        self.txt_icon = txt_icon
        self.md_icon = md_icon

        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        self.context_menu = tk.Menu(
            self.tree,
            tearoff=0,
            bg="#3C3C3C",
            fg="white",
            activebackground="#555555",
            activeforeground="white",
        )
        self.tree.bind("<Button-3>", self._show_context_menu)

        self.drag_data = {"item": None, "x": 0, "y": 0}
        self.tree.bind("<ButtonPress-1>", self._on_b1_press)
        self.tree.bind("<B1-Motion>", self._on_b1_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_b1_release)

        self.tree.bind("<Double-1>", self._on_double_click)

        self.style = ttk.Style()
        self.style.configure(
            "Treeview",
            background="#2B2B2B",
            foreground="white",
            fieldbackground="#2B2B2B",
            bordercolor="#2B2B2B",
            font=("Segoe UI", 9),
        )
        self.style.map(
            "Treeview",
            background=[("selected", "#555555")],
            foreground=[("selected", "white")],
        )
        self.style.configure(
            "Treeview.Heading",
            background="#3C3C3C",
            foreground="white",
            font=("Segoe UI", 9, "bold"),
        )
        self.style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def set_project_root(self, path):
        self.project_root = path
        self.populate_tree()

    def populate_tree(self):
        open_items = {
            item for item in self.tree.get_children("") if self.tree.item(item, "open")
        }

        for i in self.tree.get_children():
            self.tree.delete(i)

        root_name = os.path.basename(self.project_root) or self.project_root

        insert_kwargs = {
            "parent": "",
            "index": "end",
            "iid": self.project_root,
            "text": root_name,
            "tags": ("folder",),
        }
        if self.folder_icon:
            insert_kwargs["image"] = self.folder_icon

        root_node = self.tree.insert(**insert_kwargs)
        self.tree.item(root_node, open=True)
        self._add_nodes(root_node, self.project_root, open_items)

    def _add_nodes(self, parent_node, path, open_items):
        try:
            items = sorted(
                os.listdir(path),
                key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()),
            )
            for item in items:
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    insert_kwargs = {
                        "parent": parent_node,
                        "index": "end",
                        "iid": full_path,
                        "text": item,
                        "tags": ("folder",),
                    }
                    if self.folder_icon:
                        insert_kwargs["image"] = self.folder_icon

                    node = self.tree.insert(**insert_kwargs)
                    if full_path in open_items:
                        self.tree.item(node, open=True)
                    self._add_nodes(node, full_path, open_items)
                else:
                    file_extension = os.path.splitext(item)[1].lower()
                    icon = self.unknown_icon
                    if file_extension == ".py":
                        icon = self.python_icon
                    elif file_extension == ".txt":
                        icon = self.txt_icon
                    elif file_extension == ".md":
                        icon = self.md_icon
                    elif item.lower() in [
                        ".gitignore",
                        ".gitattributes",
                        ".gitmodules",
                        "readme.md",
                    ]:
                        icon = self.git_icon

                    insert_kwargs = {
                        "parent": parent_node,
                        "index": "end",
                        "iid": full_path,
                        "text": item,
                        "tags": ("file_item",),
                    }
                    if icon:
                        insert_kwargs["image"] = icon
                    self.tree.insert(**insert_kwargs)
        except Exception as e:
            print(f"Error reading directory {path}: {e}")

    def _show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)

        self.context_menu.delete(0, "end")

        is_file = item_id and os.path.isfile(item_id)
        is_dir = item_id and os.path.isdir(item_id)

        if is_file and item_id.endswith(".py"):
            self.context_menu.add_command(
                label="Run", command=lambda: self._run_item(item_id)
            )
            self.context_menu.add_separator()

        if is_file or is_dir:
            self.context_menu.add_command(
                label="Rename...", command=lambda: self._rename_item(item_id)
            )
            self.context_menu.add_command(
                label="Move...", command=lambda: self.move_item(item_id)
            )
            self.context_menu.add_command(
                label="Delete", command=lambda: self._delete_item(item_id)
            )
            self.context_menu.add_separator()
            self.context_menu.add_command(
                label="Reveal in File Explorer",
                command=lambda: self._open_in_explorer(item_id),
            )

        target_dir = None
        if is_dir:
            target_dir = item_id
        elif not item_id:  # Clicked on empty space
            target_dir = self.project_root

        if target_dir:
            if self.context_menu.index("end") is not None:
                self.context_menu.add_separator()

            new_menu = tk.Menu(
                self.context_menu,
                tearoff=0,
                bg="#3C3C3C",
                fg="white",
                activebackground="#555555",
                activeforeground="white",
            )
            new_menu.add_command(
                label="Python File (.py)",
                command=lambda: self._create_new_file(target_dir, ".py"),
            )
            new_menu.add_command(
                label="Markdown File (.md)",
                command=lambda: self._create_new_file(
                    target_dir, ".md", "# New Markdown File\n"
                ),
            )
            new_menu.add_command(
                label="Text File (.txt)",
                command=lambda: self._create_new_file(target_dir, ".txt"),
            )

            self.context_menu.add_cascade(label="New File...", menu=new_menu)
            self.context_menu.add_command(
                label="New Folder", command=lambda: self._create_new_folder(target_dir)
            )

        if self.context_menu.index("end") is not None:
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def _create_new_file(self, target_dir, extension, default_content=""):
        name = simpledialog.askstring(
            "New File", f"Enter name for new {extension} file:", parent=self
        )
        if not name:
            return

        if not name.endswith(extension):
            name += extension

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            messagebox.showerror(
                "Error", "A file with that name already exists.", parent=self
            )
            return

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(default_content)
            self.populate_tree()
            self.open_file_callback(new_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create file: {e}", parent=self)

    def _create_new_folder(self, target_dir):
        name = simpledialog.askstring(
            "New Folder", "Enter name for new folder:", parent=self
        )
        if not name:
            return

        new_path = os.path.join(target_dir, name)
        if os.path.exists(new_path):
            messagebox.showerror(
                "Error", "A folder with that name already exists.", parent=self
            )
            return

        try:
            os.makedirs(new_path)
            self.populate_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create folder: {e}", parent=self)

    def move_item(self, item_id):
        initial_dir = os.path.dirname(os.path.dirname(item_id))
        dest_dir = filedialog.askdirectory(
            title=f"Move '{os.path.basename(item_id)}' to...",
            initialdir=initial_dir,
            parent=self,
        )
        if not dest_dir:
            return

        if self._execute_move(item_id, dest_dir):
            self.populate_tree()

    def _rename_item(self, item_id):
        current_name = os.path.basename(item_id)
        new_name = simpledialog.askstring(
            "Rename", "Enter new name:", initialvalue=current_name, parent=self
        )
        if not new_name or new_name == current_name:
            return

        new_path = os.path.join(os.path.dirname(item_id), new_name)

        if os.path.exists(new_path):
            messagebox.showerror(
                "Error", f"An item named '{new_name}' already exists here."
            )
            return

        try:
            os.rename(item_id, new_path)
            self.parent.handle_file_rename(item_id, new_path)
            self.populate_tree()
        except OSError as e:
            messagebox.showerror("Rename Failed", f"Could not rename item: {e}")

    def _delete_item(self, item_id):
        item_name = os.path.basename(item_id)
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{item_name}'?",
        ):
            return

        try:
            if os.path.isfile(item_id):
                os.remove(item_id)
            elif os.path.isdir(item_id):
                shutil.rmtree(item_id)

            self.parent.handle_file_delete(item_id)
            self.populate_tree()
        except OSError as e:
            messagebox.showerror("Delete Failed", f"Could not delete item: {e}")

    def _run_item(self, item_id):
        self.parent.run_file_from_explorer(item_id)

    def _open_in_explorer(self, item_id):
        path = os.path.dirname(item_id) if os.path.isfile(item_id) else item_id
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file explorer: {e}")

    def _on_b1_press(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.drag_data["item"] = item
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

    def _on_b1_motion(self, event):
        if not self.drag_data["item"]:
            return

        drop_target = self.tree.identify_row(event.y)
        if drop_target:
            self.tree.selection_set(drop_target)

    def _on_b1_release(self, event):
        drag_item = self.drag_data["item"]
        self.drag_data["item"] = None
        if not drag_item:
            return

        drop_target_id = self.tree.identify_row(event.y)
        if not drop_target_id or drag_item == drop_target_id:
            return

        if self._execute_move(drag_item, drop_target_id):
            self.populate_tree()

    def _execute_move(self, source_path, dest_path):
        if not os.path.exists(source_path):
            return False

        if os.path.isfile(dest_path):
            dest_dir = os.path.dirname(dest_path)
        else:
            dest_dir = dest_path

        if os.path.dirname(source_path) == dest_dir:
            return False
        if os.path.isdir(source_path) and dest_dir.startswith(source_path):
            messagebox.showwarning(
                "Invalid Move", "Cannot move a folder into its own subdirectory."
            )
            return False

        try:
            base_name = os.path.basename(source_path)
            new_full_path = os.path.join(dest_dir, base_name)

            if os.path.exists(new_full_path):
                if not messagebox.askyesno(
                    "Confirm Overwrite",
                    f"'{base_name}' already exists in the destination. Overwrite?",
                ):
                    return False

            shutil.move(source_path, dest_dir)
            self.parent.handle_file_rename(source_path, new_full_path)
            return True
        except Exception as e:
            messagebox.showerror("Move Failed", f"Could not move item: {e}")
            return False

    def _on_double_click(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]

        if os.path.isfile(item_id):
            self.open_file_callback(item_id)
