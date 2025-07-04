# sandbox.py
import traceback

print("--- Welcome to the Sandbox ---")

# Example of a handled exception.
# This error will be caught, and its traceback will be printed.
try:
    # This line will cause a NameError
    print(hello)
except Exception:
    print("Caught an exception as expected!")
    # Use traceback.print_exc() to print the full details.
    # PriestyCode will detect this and highlight the line in orange.
    traceback.print_exc()


# Example of an unhandled exception (a crash).
# Uncomment the line below to see a runtime error (red highlight).
# print(10 / 0)

print("\n--- End of Sandbox Execution ---")
