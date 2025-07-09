# .github/scripts/run_test.py
import sys
import os
import tkinter as tk
import traceback

# Add the project's root directory to Python's search path.
# This ensures that when we run `src.main`, it can find other top-level modules if needed.
project_root = os.getcwd()
sys.path.insert(0, project_root)
print(f"INFO: Added '{project_root}' to Python path.")

TEST_DURATION_MS = 5000

print(f"--- GUI Test Runner ---")
print(f"Attempting to run 'src.main' as a module for {TEST_DURATION_MS / 1000} seconds...")

try:
    # We now run your code as a module, which is the standard way.
    # The try/except block in your main.py will handle this correctly.
    import src.main

    root = tk._default_root #type: ignore
    if not root:
        raise RuntimeError("Could not find the main Tkinter root window after import.")

    print(f"Successfully imported and found the Tkinter root window.")
    
    root.after(TEST_DURATION_MS, root.destroy)
    root.mainloop()

    print("--- Test Result: SUCCESS ---")
    print("Application started and exited gracefully without errors.")
    sys.exit(0)

except Exception:
    print("--- Test Result: FAILURE ---", file=sys.stderr)
    print("An exception occurred while trying to import or run the application:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)