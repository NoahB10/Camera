#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import time

class TestGUINoPreview:
    def __init__(self):
        print("Creating GUI window...")
        self.root = tk.Tk()
        self.root.title("GUI Test - No Camera Preview")
        self.root.geometry("800x600")
        
        # Camera status (simulated)
        self.cam0_connected = True
        self.cam1_connected = True
        
        # Default parameters
        self.params = {
            'ExposureTime': {'value': 10000, 'min': 100, 'max': 100000},
            'AnalogueGain': {'value': 1.0, 'min': 1.0, 'max': 20.0},
            'Brightness': {'value': 0.0, 'min': -1.0, 'max': 1.0},
        }
        
        self.setup_gui()
        print("GUI window created successfully")
        
    def setup_gui(self):
        # Main control frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        
        # Camera status
        status_frame = ttk.LabelFrame(control_frame, text="Camera Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(status_frame, text=f"Camera 0: {'Connected' if self.cam0_connected else 'Disconnected'}").pack(anchor=tk.W, padx=5)
        ttk.Label(status_frame, text=f"Camera 1: {'Connected' if self.cam1_connected else 'Disconnected'}").pack(anchor=tk.W, padx=5)
        
        # Parameter controls
        self.entries = {}
        self.scales = {}
        
        for param_name, param_data in self.params.items():
            frame = ttk.LabelFrame(control_frame, text=param_name)
            frame.pack(fill=tk.X, padx=5, pady=5)
            
            scale = ttk.Scale(
                frame,
                from_=param_data['min'],
                to=param_data['max'],
                value=param_data['value'],
                orient=tk.HORIZONTAL
            )
            scale.pack(fill=tk.X, padx=5)
            self.scales[param_name] = scale
            
            entry_frame = ttk.Frame(frame)
            entry_frame.pack(fill=tk.X, padx=5)
            
            entry = ttk.Entry(entry_frame, width=10)
            entry.insert(0, str(param_data['value']))
            entry.pack(side=tk.LEFT, padx=2)
            self.entries[param_name] = entry
            
            ttk.Button(entry_frame, text="Set", command=lambda p=param_name: self.update_param(p)).pack(side=tk.LEFT, padx=2)
        
        # Action buttons
        ttk.Button(control_frame, text="Test Save", command=self.test_save).pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(control_frame, text="Show Status", command=self.show_status).pack(fill=tk.X, padx=5)
        
        # Preview placeholder
        preview_frame = ttk.Frame(self.root)
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(preview_frame, text="Camera Preview Would Appear Here", 
                 font=('TkDefaultFont', 16)).pack(expand=True)
        ttk.Label(preview_frame, text="(Preview disabled for testing)", 
                 font=('TkDefaultFont', 10), foreground='gray').pack()
        
    def update_param(self, param_name):
        try:
            value = float(self.entries[param_name].get())
            self.params[param_name]['value'] = value
            self.scales[param_name].set(value)
            print(f"Updated {param_name} to {value}")
        except ValueError:
            messagebox.showerror("Error", f"Invalid value for {param_name}")
            
    def test_save(self):
        messagebox.showinfo("Test Save", "Save function would capture and process images here")
        print("Test save clicked")
        
    def show_status(self):
        status = "Camera Status:\\n"
        status += f"Camera 0: {'Connected' if self.cam0_connected else 'Disconnected'}\\n"
        status += f"Camera 1: {'Connected' if self.cam1_connected else 'Disconnected'}\\n\\n"
        status += "Current Parameters:\\n"
        for param, data in self.params.items():
            status += f"{param}: {data['value']}\\n"
        messagebox.showinfo("Status", status)
        
    def run(self):
        print("Starting main loop...")
        self.root.mainloop()
        print("Main loop exited")

if __name__ == "__main__":
    try:
        print("Starting GUI test without camera preview...")
        gui = TestGUINoPreview()
        gui.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()