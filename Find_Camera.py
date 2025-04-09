import cv2

def find_cameras(max_tested=5):
    print("🔍 Scanning for connected cameras...")
    for i in range(max_tested):
        cap = cv2.VideoCapture(i)
        if cap.read()[0]:
            print(f"✅ Camera found at index {i}")
            cap.release()
        else:
            print(f"❌ No camera at index {i}")

find_cameras()
