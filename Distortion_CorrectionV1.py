import numpy as np
import matplotlib.pyplot as plt
import discorpy.losa.loadersaver as losa
import discorpy.prep.preprocessing as prep
import discorpy.prep.linepattern as lprep
import discorpy.proc.processing as proc
import discorpy.post.postprocessing as post
from matplotlib.path import Path
from discorpy.prep.linepattern import _calc_index_range, get_tilted_profile

# Initial parameters
file_path   = r"C:\Users\NoahB\Documents\HebrewU Bioengineering\Equipment\Camera\RPI\Lensation_Calib_Photos\Left.jpg"
output_base = r"C:\Users\NoahB\Documents\HebrewU Bioengineering\Equipment\Camera\RPI\Lensation_Calib_Photos\Left_Calib"
num_coef = 3  # Number of polynomial coefficients - increased for better correction
apply_masking = 0  # Set to 1 to enable masking, 0 to disable
test_images = 0  # Set to 1 to test images, 0 to disable
debug_plots = 0  # Set to 1 to enable debug plots, 0 to disable
exclude_edge_lines = 0  # Set to 1 to exclude edge lines, 0 to disable

######################################NOTES################################################
# The lines are not perfectly parallel in this image even though the line fit seems accurate. 
# Either need higher dot resolution or a better polynomial fit. 
# Either way this will work for early tests but needs to be modfied for the final use.
#############################################################################################   



# Load the raw (grayscale) calibration image
mat0 = losa.load_image(file_path)      
height, width = mat0.shape

# Mask the image to the area which the chessboard is in
if apply_masking:
    fixed_polygon_verts = [
        (1439.5, 9.7),
        (3381.2, 9.7),
        (3529.8, 994.5),
        (3427.6, 2230.1),
        (3316.1, 2573.8),
        (1393.0, 2564.6),
        (1253.7, 1338.2),
        (1365.2, 334.9)
        ] 

    """
        (361.6, 366.6),
        (847.1, 245.2),
        (1621.7, 177.4),
        (2178.6, 170.3),
        (2756.9, 198.8),
        (3142.4, 248.8),
        (3149.5, 930.6),
        (3110.3, 1641.0),
        (3038.9, 2265.7),
        (3024.6, 2394.2),
        (2182.1, 2387.1),
        (1564.6, 2337.1),
        (1000.6, 2240.7),
        (507.9, 2101.5),
        (365.1, 2058.6),
        (297.3, 1409.0),
        (297.3, 891.4)
    """

    xv, yv = np.meshgrid(np.arange(width), np.arange(height))
    coords = np.vstack((xv.flatten(), yv.flatten())).T
    path = Path(fixed_polygon_verts)
    mask_flat = path.contains_points(coords)
    mask = mask_flat.reshape((height, width))

    # Apply mask
    image_masked = mat0.copy()
    image_masked[~mask] = 0  # zero out outside

    # Crop the image to the bounding box of the mask
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError("Mask does not cover any area!")
    ymin, ymax = ys.min(), ys.max()
    xmin, xmax = xs.min(), xs.max()
    image_cropped = image_masked[ymin:ymax+1, xmin:xmax+1]
    mask_cropped = mask[ymin:ymax+1, xmin:xmax+1]

    # Adjust polygon coordinates for cropping
    fixed_polygon_verts_cropped = [(x - xmin, y - ymin) for (x, y) in fixed_polygon_verts]
    
    # Use the masked and cropped image for processing
    processing_image = image_cropped
else:
    # No masking - use original image
    mask = np.ones((height, width), dtype=bool)  # Full mask for consistency
    processing_image = mat0

# ----------------------------
# 2) Convert to line-pattern
# ----------------------------
mat1 = lprep.convert_chessboard_to_linepattern(processing_image)
losa.save_image(f"{output_base}/01_linepattern.jpg", mat1)

# Calculate slope and distance between lines
slope_hor, dist_hor = lprep.calc_slope_distance_hor_lines(mat1, radius=15, sensitive=0.5)
slope_ver, dist_ver = lprep.calc_slope_distance_ver_lines(mat1, radius=15, sensitive=0.5)

if debug_plots:
    xc, yc = width/2, height/2

    # horizontal fit (dy/dx)
    x = np.array([0, width])
    y_h = slope_hor*(x - xc) + yc

    # vertical fit (dx/dy)
    y = np.array([0, height])
    x_v = slope_ver*(y - yc) + xc

    plt.figure(figsize=(8,8))
    plt.imshow(mat1, cmap='gray')

    # draw both
    plt.plot(x,   y_h, color='C0', linewidth=2,
            label=f'rows: dy/dx = {slope_hor:.3f}')
    plt.plot(x_v, y,   color='C1', linewidth=2,
            label=f'cols: dx/dy = {slope_ver:.3f}')

    plt.legend(loc='upper right')
    plt.title("Fitted row- and column-directions")
    plt.axis('off')
    plt.show()
    print(f"Horizontal slope: {slope_hor:.4f}, distance: {dist_hor:.1f}")
    print(f"Vertical   slope: {slope_ver:.4f}, distance: {dist_ver:.1f}")


# Extract reference-points
list_points_hor_lines = lprep.get_cross_points_hor_lines(mat1, slope_ver, 100,
                                                         ratio=0.2, norm=True, offset=100,
                                                         bgr="bright", radius=15,
                                                         sensitive=0.3, denoise=True,
                                                         subpixel=True)
list_points_ver_lines = lprep.get_cross_points_ver_lines(mat1, slope_hor, 100,
                                                         ratio=0.2, norm=True, offset=225,
                                                         bgr="bright", radius=15,
                                                         sensitive=0.2, denoise=True,
                                                         subpixel=True)
if len(list_points_hor_lines) == 0 or len(list_points_ver_lines) == 0:
    raise ValueError("No reference-points detected !!! Please adjust parameters !!!")
losa.save_plot_points(output_base + "/ref_points_horizontal.png", list_points_hor_lines,
                    height, width, color="red")
losa.save_plot_points(output_base + "/ref_points_vertical.png", list_points_ver_lines,
                    height, width, color="blue")

# Group points into lines
#Rules for picking the parameters:
#1. The accepted ratio should be low to include more lines
#2. The num_dot_miss should be high to include more lines
#3. The ratio is the amount variation there can be 
#4. The distance should be small as it is how close dots are to each other
list_hor_lines = prep.group_dots_hor_lines(list_points_hor_lines, slope_hor, 20,
                                           ratio=0.6, num_dot_miss=10, accepted_ratio=.7)
list_ver_lines = prep.group_dots_ver_lines(list_points_ver_lines, slope_ver, 40,
                                           ratio=0.5, num_dot_miss=10, accepted_ratio=.2) #Reduce the accepted ratio to 0.2 to include more lines
# Exclude the first and last vertical lines (edge lines)
if exclude_edge_lines:
    if len(list_ver_lines) > 2:
        list_ver_lines = list_ver_lines[1:-1]

# Remove residual dots
list_hor_lines = prep.remove_residual_dots_hor(list_hor_lines, slope_hor, 2.0)
list_ver_lines = prep.remove_residual_dots_ver(list_ver_lines, slope_ver, 10)

if debug_plots:
    # Debug: Plot grouped lines after removing residuals
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
    
    # Plot horizontal lines
    ax1.imshow(mat1, cmap='gray')
    for line in list_hor_lines:
        arr = np.array(line)
        if len(arr) > 0:
            ax1.plot(arr[:, 1], arr[:, 0], marker='o', label='Hor Line After Residual')
    # Overlay the estimated horizontal slope
    x = np.array([0, mat1.shape[1]])
    y_h = slope_hor*(x - xc) + yc
    ax1.plot(x, y_h, color='C0', linewidth=2, label='Estimated Hor Slope')
    ax1.legend()
    ax1.set_title("Horizontal Lines After Residual Removal")
    ax1.axis('off')
    
    # Plot vertical lines
    ax2.imshow(mat1, cmap='gray')
    for line in list_ver_lines:
        arr = np.array(line)
        if len(arr) > 0:
            ax2.plot(arr[:, 1], arr[:, 0], marker='o', label='Ver Line After Residual')
    # Overlay the estimated vertical slope
    for y in [0, mat1.shape[0]]:
        x = slope_ver*(y - yc) + xc
        ax2.plot(x, y, color='C1', linewidth=2, label='Estimated Ver Slope')
    ax2.legend()
    ax2.set_title("Vertical Lines After Residual Removal")
    ax2.axis('off')
    
    plt.tight_layout()
    plt.show()


# Save output for checking
losa.save_plot_image(output_base + "/horizontal_lines.png", list_hor_lines, height, width)
losa.save_plot_image(output_base + "/vertical_lines.png", list_ver_lines, height, width)
list_hor_data = post.calc_residual_hor(list_hor_lines, 0.0, 0.0)
list_ver_data = post.calc_residual_ver(list_ver_lines, 0.0, 0.0)
losa.save_residual_plot(output_base + "/hor_residual_before_correction.png",
                      list_hor_data, height, width)
losa.save_residual_plot(output_base + "/ver_residual_before_correction.png",
                      list_ver_data, height, width)

# Regenerate grid points after correcting the perspective effect.
list_hor_lines, list_ver_lines = proc.regenerate_grid_points_parabola(
    list_hor_lines, list_ver_lines, perspective=True)

# Calculate parameters of the radial correction model
(xcenter, ycenter) = proc.find_cod_coarse(list_hor_lines, list_ver_lines)
list_fact = proc.calc_coef_backward(list_hor_lines, list_ver_lines,
                                    xcenter, ycenter, num_coef)
losa.save_metadata_txt(output_base + "/coefficients_radial_distortion.txt",
                     xcenter, ycenter, list_fact)
print("X-center: {0}. Y-center: {1}".format(xcenter, ycenter))
print("Coefficients: {0}".format(list_fact))

# Check the correction results:
# Apply correction to the lines of points
list_uhor_lines = post.unwarp_line_backward(list_hor_lines, xcenter, ycenter,
                                            list_fact)
list_uver_lines = post.unwarp_line_backward(list_ver_lines, xcenter, ycenter,
                                            list_fact)
# Calculate the residual of the unwarpped points.
list_hor_data = post.calc_residual_hor(list_uhor_lines, xcenter, ycenter)
list_ver_data = post.calc_residual_ver(list_uver_lines, xcenter, ycenter)
# Save the results for checking
losa.save_plot_image(output_base + "/unwarpped_horizontal_lines.png",
                   list_uhor_lines, height, width)
losa.save_plot_image(output_base + "/unwarpped_vertical_lines.png",
                   list_uver_lines, height, width)
losa.save_residual_plot(output_base + "/hor_residual_after_correction.png",
                      list_hor_data, height, width)
losa.save_residual_plot(output_base + "/ver_residual_after_correction.png",
                      list_ver_data, height, width)

# Correct the image
corrected_mat = post.unwarp_image_backward(processing_image, xcenter, ycenter, list_fact)
# Apply mask to keep only the masked area
if apply_masking:
    corrected_mat[~mask] = 0  # zero out outside the mask
# Save results.
losa.save_image(output_base + "/corrected_image.jpg", corrected_mat)
losa.save_image(output_base + "/difference.jpg", corrected_mat - processing_image)

# ----------------------------------------
# Load original color image for correction
# ------------------------------------------

# Load coefficients from previous calculation if need to
# (xcenter, ycenter, list_fact) = losa.load_metadata_txt(
#     output_base + "/coefficients_radial_distortion.txt")

img = losa.load_image(file_path, average=False)
img_corrected = np.copy(img)
# Unwarp each color channel of the image
for i in range(img.shape[-1]):
    img_corrected[:, :, i] = post.unwarp_image_backward(img[:, :, i], xcenter,
                                                        ycenter, list_fact)
# Apply mask to each channel
if apply_masking:
    for i in range(img_corrected.shape[-1]):
        img_corrected[:, :, i][~mask] = 0
# Save the unwarped image.
losa.save_image(output_base + "/corrected_image_color.jpg", img_corrected)

# Load a test image and correct it. (Make true to run)
if test_images:
    img = losa.load_image(r"C:\Users\NoahB\Documents\HebrewU Bioengineering\Equipment\Camera\RPI\Cal_Retest\test_image_corrected2.jpg", average=False)
    img2 = losa.load_image(r"C:\Users\NoahB\Documents\HebrewU Bioengineering\Equipment\Camera\RPI\Cal_Retest\test_image_corrected2.jpg", average=False)
    img_corrected = np.copy(img)
    img2_corrected = np.copy(img)
    for i in range(img.shape[-1]):
        img_corrected[:, :, i] = post.unwarp_image_backward(img[:, :, i], xcenter,
                                                            ycenter, list_fact)
        img2_corrected[:, :, i] = post.unwarp_image_backward(img2[:, :, i], xcenter,
                                                            ycenter, list_fact)
    losa.save_image(output_base + "/test_image_corrected1.jpg", img_corrected)
    losa.save_image(output_base + "/test_image_corrected2.jpg", img2_corrected)