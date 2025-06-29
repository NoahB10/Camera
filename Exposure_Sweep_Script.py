import os
import time
from datetime import datetime
import numpy as np
import imageio
from picamera2 import Picamera2
import discorpy.post.postprocessing as post
import cv2

# === USER CONFIGURATION ===
exposure_start = 500     # in microseconds
exposure_end = 9000      # in microseconds
exposure_step = 200
save_tiff = True
output_base_folder = "RPI_ExposureSweep_NoGUI"

# === Processing Parameters ===
apply_cropping = True
enable_distortion_correction = True
enable_perspective_correction = True
apply_left_rotation = True
apply_right_rotation = False
left_rotation_angle = -1.3
right_rotation_angle = -0.5
left_top_padding = 170
left_bottom_padding = 35
right_top_padding = 200
right_bottom_padding = 50

crop_params = {
    'cam0': {'width': 2070, 'start_x': 1260, 'height': 2592},
    'cam1': {'width': 2050, 'start_x': 1400, 'height': 2592}
}

distortion_params = {
    'cam0': {
        'xcenter': 1114.2182151597553,
        'ycenter': 1262.5277844147154,
        'coeffs': [
            1.0014854456230917,
            5.509159612493664e-06,
            -1.1578814230907084e-07,
            2.5752820518855916e-11,
            4.193791691783126e-16
        ],
        'pers_coef': None
    },
    'cam1': {
        'xcenter': 926.3533299759179,
        'ycenter': 1252.919524105411,
        'coeffs': [
            1.0005567203819934,
            7.799070714933332e-06,
            -1.1242413914232819e-07,
            1.778601705763631e-11,
            3.2803258048180376e-15
        ],
        'pers_coef': None
    }
}

# === CAMERA SETUP ===
def configure_camera(cam_index):
    cam = Picamera2(cam_index)
    config = cam.create_still_configuration(
        raw={"size": (4608, 2592)},
        controls={"AnalogueGain": 1.0}  # Do not lock exposure time here
    )
    cam.configure(config)
    cam.start()
    time.sleep(1)
    return cam

def crop_image(image, cam_name):
    params = crop_params[cam_name]
    return image[:params['height'], params['start_x']:params['start_x'] + params['width']]

def apply_distortion_correction(image, cam_name):
    params = distortion_params[cam_name]
    xcenter = params['xcenter']
    ycenter = params['ycenter']
    coeffs = params['coeffs']

    top_padding = left_top_padding if cam_name == 'cam0' else right_top_padding
    bottom_padding = left_bottom_padding if cam_name == 'cam0' else right_bottom_padding

    h, w = image.shape[:2]
    new_image = np.pad(image, ((top_padding, bottom_padding), (0, 0), (0, 0)), mode='constant') if image.ndim == 3 else np.pad(image, ((top_padding, bottom_padding), (0, 0)), mode='constant')
    new_ycenter = ycenter + top_padding

    if image.ndim == 2:
        return post.unwarp_image_backward(new_image, xcenter, new_ycenter, coeffs)
    else:
        corrected_channels = [post.unwarp_image_backward(new_image[..., c], xcenter, new_ycenter, coeffs) for c in range(image.shape[2])]
        return np.stack(corrected_channels, axis=-1)

def apply_perspective_correction(image, cam_name):
    params = distortion_params[cam_name]
    coef = params['pers_coef']
    if coef is None:
        return image
    if image.ndim == 2:
        return post.correct_perspective_image(image, coef)
    else:
        return np.stack([post.correct_perspective_image(image[..., c], coef) for c in range(3)], axis=-1)

def rotate_image(image, angle):
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

def process_image(image, cam_name):
    if apply_cropping:
        image = crop_image(image, cam_name)
    if enable_distortion_correction:
        image = apply_distortion_correction(image, cam_name)
    if enable_perspective_correction:
        image = apply_perspective_correction(image, cam_name)
    if cam_name == 'cam0' and apply_left_rotation:
        image = rotate_image(image, left_rotation_angle)
    if cam_name == 'cam1' and apply_right_rotation:
        image = rotate_image(image, right_rotation_angle)
    return image

def capture_sweep():
    timestamp_base = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_folder = datetime.now().strftime("%Y-%m-%d")
    save_folder = os.path.join(output_base_folder, date_folder)
    os.makedirs(save_folder, exist_ok=True)

    exposures = range(exposure_start, exposure_end + 1, exposure_step)

    cam0 = cam1 = None
    try:
        print("[INFO] Initializing cameras...")
        cam0 = configure_camera(0)
        cam1 = configure_camera(1)

        for i, exp in enumerate(exposures):
            print(f"[INFO] Capturing at {exp} µs...")

            cam0.set_controls({"ExposureTime": exp})
            cam1.set_controls({"ExposureTime": exp})
            time.sleep(0.2)  # Allow hardware to apply changes

            req0 = cam0.capture_request()
            req1 = cam1.capture_request()

            img0 = req0.make_array("main")
            img1 = req1.make_array("main")

            img0 = process_image(img0, 'cam0')
            img1 = process_image(img1, 'cam1')

            h = min(img0.shape[0], img1.shape[0])
            combined = np.hstack((img0[:h], img1[:h]))

            tiff_path = os.path.join(save_folder, f"dual_{timestamp_base}_exp{i}_{exp}.tiff")
            imageio.imsave(tiff_path, combined)
            print(f"[✓] Saved {tiff_path}")

            req0.release()
            req1.release()

        print("[DONE] Exposure sweep complete.")
    finally:
        if cam0: cam0.stop()
        if cam1: cam1.stop()

if __name__ == "__main__":
    capture_sweep()
