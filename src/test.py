# Create a new file: src/temp_test.py
import sys, os # Flake8 Error: multiple imports on one line
import numbers
import tkinter 

def bad_function () : # Black Error: bad formatting
    unused_variable = "hello" # Flake8 Error: unused variable
    return True

def another_bad_function():
    dumb_variable = 100
    stupid_variable = 500
    return False