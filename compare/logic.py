import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

def compare_images(ideal_path, test_path):
    ideal = cv2.imread(ideal_path)
    test = cv2.imread(test_path)

    if ideal is None or test is None:
        raise Exception("Image not found")

    # resize to same size
    h, w = 600, 600
    ideal = cv2.resize(ideal, (w, h))
    test = cv2.resize(test, (w, h))

    grayA = cv2.cvtColor(ideal, cv2.COLOR_BGR2GRAY)
    grayB = cv2.cvtColor(test, cv2.COLOR_BGR2GRAY)

    score, diff = ssim(grayA, grayB, full=True)
    diff = (diff * 255).astype("uint8")

    thresh = cv2.threshold(diff, 160, 255, cv2.THRESH_BINARY_INV)[1]

    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []

    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area > 500:  # ignore noise
            boxes.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h)})

    return {
        "similarity_score": float(score),
        "defect_boxes": boxes
    }
