import cv2
from ArducamCamera import ArducamCamera
from arducam_config_parser import load_config
import numpy as np

# --- Setup Camera ---
cfg = load_config("config/USB3/64MP_Quad_Linear.json")  # Replace with correct path/config
cam = ArducamCamera()
cam.initCamera(cfg)
cam.setResolution(1920, 1080)  # Set lower resolution for smoother preview
cam.start()

# --- Focus Settings ---
focus_position = 512  # Midpoint
cam.set_control(0x01, focus_position)  # Initial focus

print("📷 Press ↑ / ↓ to adjust focus")
print("💾 Press 's' to save image, 'q' to quit")

# --- Main Loop ---
while True:
    ret, data, cfg = cam.read()
    if not ret or data is None:
        continue

    frame = np.frombuffer(data, dtype=np.uint8).reshape((cfg["uHeight"], cfg["uWidth"], cfg["uByteLength"]))
    cv2.imshow("Arducam Live", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('s'):
        cv2.imwrite("captured_image.jpg", frame)
        print("💾 Image saved as captured_image.jpg")
    elif key == 82:  # ↑ arrow key
        focus_position = min(focus_position + 20, 1023)
        cam.set_control(0x01, focus_position)
        print(f"🔍 Focus increased to {focus_position}")
    elif key == 84:  # ↓ arrow key
        focus_position = max(focus_position - 20, 0)
        cam.set_control(0x01, focus_position)
        print(f"🔍 Focus decreased to {focus_position}")

# --- Cleanup ---
cam.stop()
cam.closeCamera()
cv2.destroyAllWindows()
