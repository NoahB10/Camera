#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import time

class MinimalGUI:
    def __init__(self):
        print("Creating GUI window...")
        self.root = tk.Tk()
        self.root.title("Minimal Test GUI")
        self.root.geometry("400x300")
        
        # Add some basic widgets
        ttk.Label(self.root, text="GUI Test - Cameras detected!").pack(pady=20)
        ttk.Button(self.root, text="Test Button").pack(pady=10)
        
        print("GUI window created successfully")
        
    def run(self):
        print("Starting main loop...")
        self.root.mainloop()
        print("Main loop exited")

if __name__ == "__main__":
    try:
        print("Starting minimal GUI test...")
        gui = MinimalGUI()
        gui.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()