import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk

class ImageCropperTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Image Cropper & Resizer - Mouse wheel=zoom, Ctrl+click=pan, ()=resize crop, Arrows=fine resize")
        self.root.geometry("800x600")
        
        # Variables
        self.original_image = None
        self.display_image = None
        self.canvas = None
        self.scale_factor = 1.0
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        # UI Setup
        self.setup_ui()
        
    def setup_ui(self):
        # Frame for buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        # Buttons
        tk.Button(button_frame, text="Open Image", command=self.open_image).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Set Target Size", command=self.set_target_size).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Reset Zoom", command=self.reset_zoom).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Crop & Resize", command=self.crop_and_resize).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save Result", command=self.save_image).pack(side=tk.LEFT, padx=5)
        
        # Canvas for image display
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray90')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables for cropping
        self.crop_width = 512
        self.crop_height = 512
        self.target_size = (512, 512)
        
        # Crop rectangle variables
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        # Bind mouse events for cropping and panning
        self.canvas.bind("<Button-1>", self.mouse_click)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.mouse_release)
        
        # Bind mouse events for panning (right mouse button)
        self.canvas.bind("<Button-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.pan_image)
        
        # Variables for mouse state
        self.is_panning = False
        self.is_cropping = False
        
        # Bind mouse wheel for zooming
        self.canvas.bind("<MouseWheel>", self.zoom_image)
        self.canvas.bind("<Button-4>", self.zoom_image)  # Linux
        self.canvas.bind("<Button-5>", self.zoom_image)  # Linux
        
        # Bind keyboard events
        self.canvas.focus_set()  # Allow canvas to receive focus
        self.root.bind("<Key>", self.handle_keypress)
        self.root.bind("<KeyPress-Control_L>", self.ctrl_pressed)
        self.root.bind("<KeyPress-Control_R>", self.ctrl_pressed)
        self.root.bind("<KeyRelease-Control_L>", self.ctrl_released)
        self.root.bind("<KeyRelease-Control_R>", self.ctrl_released)
        
        # Status label
        self.status_label = tk.Label(self.root, text="Open an image to start. Controls: Mouse wheel/+-=zoom, Ctrl+click/Right click=pan, Left click=position crop, ()=resize crop, Arrows=fine resize", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)
        
    def open_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff *.gif"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.original_image = Image.open(file_path)
                self.display_image_on_canvas()
                self.update_status()
                self.status_label.config(text=f"Loaded: {os.path.basename(file_path)} ({self.original_image.size[0]}x{self.original_image.size[1]}) | " + self.status_label.cget("text"))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open image: {str(e)}")
    
    def display_image_on_canvas(self):
        if not self.original_image:
            return
            
        # Calculate scale to fit canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after(100, self.display_image_on_canvas)
            return
            
        img_width, img_height = self.original_image.size
        
        # Base scale to fit canvas
        scale_x = canvas_width / img_width
        scale_y = canvas_height / img_height
        base_scale = min(scale_x, scale_y, 1.0)  # Don't scale up initially
        
        # Apply zoom factor
        self.scale_factor = base_scale * self.zoom_factor
        
        # Resize image for display
        display_width = int(img_width * self.scale_factor)
        display_height = int(img_height * self.scale_factor)
        
        self.display_image = self.original_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(self.display_image)
        
        # Clear canvas and display image with pan offset
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width//2 + self.pan_x, canvas_height//2 + self.pan_y, image=self.photo)
        
        # Redraw crop rectangle if it exists
        if hasattr(self, 'rect_id') and self.rect_id and self.start_x is not None:
            self.update_crop_display()
        
    def set_target_size(self):
        # Ask for target size only (crop size is controlled dynamically)
        target_w = simpledialog.askinteger("Target Width", "Enter target width:", initialvalue=self.target_size[0], minvalue=1)
        if target_w:
            target_h = simpledialog.askinteger("Target Height", "Enter target height:", initialvalue=self.target_size[1], minvalue=1)
            if target_h:
                self.target_size = (target_w, target_h)
        
        self.update_status()
    
    def update_status(self):
        zoom_percent = int(self.zoom_factor * 100)
        self.status_label.config(text=f"Crop size: {self.crop_width}x{self.crop_height}, Target size: {self.target_size[0]}x{self.target_size[1]}, Zoom: {zoom_percent}%")
    
    def reset_zoom(self):
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        if self.original_image:
            self.display_image_on_canvas()
        self.update_status()
    
    def zoom_image(self, event):
        if not self.original_image:
            return
            
        # Determine zoom direction
        if event.num == 4 or event.delta > 0:  # Zoom in
            zoom_factor = 1.1
        elif event.num == 5 or event.delta < 0:  # Zoom out
            zoom_factor = 0.9
        else:
            return
            
        # Apply zoom
        self.zoom_factor *= zoom_factor
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))  # Limit zoom range
        
        self.display_image_on_canvas()
        self.update_status()
    
    def start_pan(self, event):
        self.last_x = event.x
        self.last_y = event.y
    
    def pan_image(self, event):
        if not self.original_image:
            return
            
        # Calculate pan offset
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        self.pan_x += dx
        self.pan_y += dy
        
        self.last_x = event.x
        self.last_y = event.y
        
        self.display_image_on_canvas()
    
    def ctrl_pressed(self, event):
        if not self.is_panning and not self.is_cropping:
            self.canvas.config(cursor="fleur")  # Show pan cursor when Ctrl is held
    
    def ctrl_released(self, event):
        if not self.is_panning and not self.is_cropping:
            self.canvas.config(cursor="")  # Reset to default cursor
    
    def handle_keypress(self, event):
        if not self.original_image:
            return
            
        key = event.keysym
        
        # Zoom with +/- keys
        if key == 'plus' or key == 'equal':
            self.zoom_factor *= 1.1
            self.zoom_factor = min(10.0, self.zoom_factor)
            self.display_image_on_canvas()
            self.update_status()
        elif key == 'minus':
            self.zoom_factor *= 0.9
            self.zoom_factor = max(0.1, self.zoom_factor)
            self.display_image_on_canvas()
            self.update_status()
        
        # Resize crop with parentheses
        elif key == 'parenleft':  # ( key - make crop smaller
            self.crop_width = max(10, self.crop_width - 10)
            self.crop_height = max(10, self.crop_height - 10)
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
        elif key == 'parenright':  # ) key - make crop larger
            self.crop_width += 10
            self.crop_height += 10
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
        
        # Arrow keys for fine crop resizing
        elif key == 'Up':
            self.crop_height = max(10, self.crop_height - 5)
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
        elif key == 'Down':
            self.crop_height += 5
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
        elif key == 'Left':
            self.crop_width = max(10, self.crop_width - 5)
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
        elif key == 'Right':
            self.crop_width += 5
            if hasattr(self, 'rect_id') and self.rect_id:
                self.update_crop_display()
            self.update_status()
    
    def update_crop_display(self):
        if not self.original_image or self.start_x is None or self.start_y is None:
            return
            
        # Delete old rectangle
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            
        # Calculate rectangle size based on current crop dimensions and zoom
        crop_w_scaled = self.crop_width * self.scale_factor
        crop_h_scaled = self.crop_height * self.scale_factor
        
        # Draw new rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, 
            self.start_x + crop_w_scaled, self.start_y + crop_h_scaled,
            outline='red', width=2, tags="crop_rect"
        )
    
    def mouse_click(self, event):
        if not self.original_image:
            return
            
        # Check if Ctrl is pressed for panning
        if event.state & 0x4:  # Ctrl key pressed
            self.canvas.config(cursor="fleur")  # Hand cursor for panning
            self.start_pan(event)
            self.is_panning = True
            self.is_cropping = False
        else:
            self.canvas.config(cursor="crosshair")  # Crosshair for cropping
            # Start cropping - center the crop rectangle on the click point
            self.start_crop(event)
            self.is_panning = False
            self.is_cropping = True
    
    def mouse_drag(self, event):
        if not self.original_image:
            return
            
        if self.is_panning:
            self.pan_image(event)
        elif self.is_cropping:
            self.update_crop(event)
    
    def mouse_release(self, event):
        self.is_panning = False
        self.is_cropping = False
        self.canvas.config(cursor="")  # Reset cursor to default
    
    def start_crop(self, event):
        # Center the crop rectangle on the click point
        crop_w_scaled = self.crop_width * self.scale_factor
        crop_h_scaled = self.crop_height * self.scale_factor
        
        # Calculate centered position
        self.start_x = event.x - crop_w_scaled // 2
        self.start_y = event.y - crop_h_scaled // 2
        
        # Get canvas bounds for boundary checking
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Keep crop rectangle within canvas bounds
        self.start_x = max(0, min(self.start_x, canvas_width - crop_w_scaled))
        self.start_y = max(0, min(self.start_y, canvas_height - crop_h_scaled))
        
        # Delete existing rectangle
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            
        # Draw initial rectangle
        self.update_crop_display()
    
    def update_crop(self, event):
        if not self.original_image:
            return
            
        # Center the crop rectangle on the current mouse position
        crop_w_scaled = self.crop_width * self.scale_factor
        crop_h_scaled = self.crop_height * self.scale_factor
        
        # Calculate centered position
        self.start_x = event.x - crop_w_scaled // 2
        self.start_y = event.y - crop_h_scaled // 2
        
        # Get canvas bounds for boundary checking
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Keep crop rectangle within canvas bounds
        self.start_x = max(0, min(self.start_x, canvas_width - crop_w_scaled))
        self.start_y = max(0, min(self.start_y, canvas_height - crop_h_scaled))
        
        # Update the display
        self.update_crop_display()
    
    def crop_and_resize(self):
        if not self.original_image or self.start_x is None:
            messagebox.showwarning("Warning", "Please select a crop area first by clicking on the image.")
            return
            
        try:
            # Convert canvas coordinates to image coordinates with zoom and pan
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Calculate image position on canvas with pan offset
            img_width, img_height = self.original_image.size
            display_width = int(img_width * self.scale_factor)
            display_height = int(img_height * self.scale_factor)
            
            img_x = (canvas_width - display_width) // 2 + self.pan_x
            img_y = (canvas_height - display_height) // 2 + self.pan_y
            
            # Convert crop coordinates from canvas to original image coordinates
            # start_x and start_y represent the top-left corner of the crop rectangle
            crop_x = int((self.start_x - img_x) / self.scale_factor)
            crop_y = int((self.start_y - img_y) / self.scale_factor)
            
            # Ensure crop coordinates are within image bounds
            crop_x = max(0, min(crop_x, img_width - self.crop_width))
            crop_y = max(0, min(crop_y, img_height - self.crop_height))
            
            # Ensure crop size doesn't exceed image bounds
            actual_crop_width = min(self.crop_width, img_width - crop_x)
            actual_crop_height = min(self.crop_height, img_height - crop_y)
            
            # Crop the image
            crop_box = (crop_x, crop_y, crop_x + actual_crop_width, crop_y + actual_crop_height)
            cropped_image = self.original_image.crop(crop_box)
            
            # Create target size image with white background
            result_image = Image.new('RGB', self.target_size, 'white')
            
            # Calculate position to center the cropped image
            paste_x = (self.target_size[0] - actual_crop_width) // 2
            paste_y = (self.target_size[1] - actual_crop_height) // 2
            
            # Paste the cropped image onto the white background
            result_image.paste(cropped_image, (paste_x, paste_y))
            
            # Store result
            self.result_image = result_image
            
            # Reset zoom and pan for result display
            self.zoom_factor = 1.0
            self.pan_x = 0
            self.pan_y = 0
            
            # Update display to show result
            self.original_image = result_image
            self.display_image_on_canvas()
            
            self.status_label.config(text=f"Cropped and resized! Final size: {self.target_size[0]}x{self.target_size[1]}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not crop image: {str(e)}")
    
    def save_image(self):
        if not hasattr(self, 'result_image'):
            messagebox.showwarning("Warning", "No processed image to save. Please crop and resize first.")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=".jpg",
            filetypes=[
                ("JPEG files", "*.jpg"),
                ("PNG files", "*.png"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                # Convert to RGB if saving as JPEG
                if file_path.lower().endswith(('.jpg', '.jpeg')):
                    save_image = self.result_image.convert('RGB')
                    save_image.save(file_path, 'JPEG', quality=95)
                else:
                    self.result_image.save(file_path)
                    
                self.status_label.config(text=f"Saved: {os.path.basename(file_path)}")
                messagebox.showinfo("Success", f"Image saved successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Could not save image: {str(e)}")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ImageCropperTool()
    app.run() 