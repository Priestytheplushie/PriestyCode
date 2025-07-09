# .github/scripts/run_test.py
import sys
import os
import traceback

print("--- Code Integrity Smoke Test ---")

# Add the project's root directory to Python's search path to find 'src'.
project_root = os.getcwd()
sys.path.insert(0, project_root)
print(f"INFO: Added '{project_root}' to Python path.")

try:
    print("Attempting to import 'src.main'...")
    # The test is simply to see if the main module can be imported
    # without any syntax or import errors.
    import src.main
    
    print("\n--- Test Result: SUCCESS ---")
    print("Code is structurally sound. All modules imported successfully.")
    sys.exit(0)

except Exception:
    print("\n--- Test Result: FAILURE ---", file=sys.stderr)
    print("A critical error (likely SyntaxError or ImportError) was found:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)