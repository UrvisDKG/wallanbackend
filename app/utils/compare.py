import cv2
from skimage.metrics import structural_similarity as ssim

def compare_images(ideal_path, test_path):
    ideal = cv2.imread(ideal_path, cv2.IMREAD_GRAYSCALE)
    test = cv2.imread(test_path, cv2.IMREAD_GRAYSCALE)

    if ideal is None or test is None:
        return 0.0

    # Resize test to ideal size
    test = cv2.resize(test, (ideal.shape[1], ideal.shape[0]))
    score, _ = ssim(ideal, test, full=True)
    return float(score)
