from picamera2 import Picamera2
from datetime import datetime
import time

# Initialize camera
picam2 = Picamera2()

# Create high-res still config with autofocus in macro mode
config = picam2.create_still_configuration(
    main={"size": (4608, 2592)},
    raw={"size": (4608, 2592)},
    controls={
    "AfMode": 0,              # Manual focus mode
    "LensPosition": .1 

    }
)

picam2.configure(config)
picam2.start()

print("Camera started with autofocus in macro mode.")
print("Press Enter to capture a photo, or Ctrl+C to exit.")


try:
    while True:
        input("📸 Press Enter to capture: ")
        filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        picam2.capture_file(filename)
        print(f"Saved {filename}")
except KeyboardInterrupt:
    print("\nExiting.")
finally:
    picam2.stop()
