# .github/scripts/run_test.py
import sys
import os
import tkinter as tk
import traceback

# This adds your project's main folder to Python's search path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, project_root)
print(f"INFO: Added '{project_root}' to Python path.")

TEST_DURATION_MS = 5000

print(f"--- GUI Test Runner ---")
print(f"Attempting to import and run the application for {TEST_DURATION_MS / 1000} seconds...")

try:
    import src.main

    root = tk._default_root #type: ignore
    if not root:
        raise RuntimeError("Could not find the main Tkinter root window after import.")

    print(f"Successfully imported 'src.main' and found the Tkinter root window.")
    
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