import cv2

# Open the first UVC camera (0 is usually the first USB camera)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("❌ Could not open camera.")
    exit()

# Set a resolution (optional, depends on your camera)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Capture one frame
ret, frame = cap.read()

if ret:
    # Show the frame in a window
    cv2.imshow("Captured Frame", frame)

    # Save it to file
    cv2.imwrite("captured_image.jpg", frame)
    print("✅ Image saved as captured_image.jpg")

    # Wait for a key press to close window
    cv2.waitKey(0)
else:
    print("❌ Failed to capture image.")

# Release camera and close window
cap.release()
cv2.destroyAllWindows()
