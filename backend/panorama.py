import cv2
import numpy as np
import base64
import logging
import requests
from pathlib import Path

log = logging.getLogger("immostage.panorama")


def stitch_panorama(img_paths, work_dir):
    """
    Stitch multiple room photos into a panorama using OpenCV.
    Falls back to the highest-quality single image if stitching fails.
    """
    images = []
    for p in img_paths:
        img = cv2.imread(p)
        if img is not None:
            images.append(img)
        else:
            log.warning(f"Could not read image: {p}")

    out_path = str(work_dir / "panorama.jpg")

    if not images:
        raise ValueError("No valid images available for panorama stitching")

    if len(images) == 1:
        log.info("Single image — skipping stitching")
        cv2.imwrite(out_path, images[0], [cv2.IMWRITE_JPEG_QUALITY, 90])
        return out_path

    log.info(f"Stitching {len(images)} images into panorama")
    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    status, pano = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        cv2.imwrite(out_path, pano, [cv2.IMWRITE_JPEG_QUALITY, 90])
        h, w = pano.shape[:2]
        log.info(f"Panorama stitched: {w}x{h}px → {out_path}")
    else:
        status_names = {
            cv2.Stitcher_ERR_NEED_MORE_IMGS: "ERR_NEED_MORE_IMGS",
            cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "ERR_HOMOGRAPHY_EST_FAIL",
            cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "ERR_CAMERA_PARAMS_ADJUST_FAIL",
        }
        status_name = status_names.get(status, f"UNKNOWN({status})")
        log.warning(f"Stitching failed: {status_name} — falling back to best single image")

        # Pick the image with the most SIFT features as the best representative
        sift = cv2.SIFT_create()
        best = max(
            images,
            key=lambda img: len(sift.detect(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))),
        )
        cv2.imwrite(out_path, best, [cv2.IMWRITE_JPEG_QUALITY, 90])
        h, w = best.shape[:2]
        log.info(f"Fallback panorama: {w}x{h}px → {out_path}")

    return out_path


def generate_depth_map(pano_path, work_dir):
    """
    Generate a depth map for the panorama using fal.ai depth estimation.
    Returns path to the local depth map JPEG.
    """
    import fal_client

    log.info(f"Generating depth map for: {pano_path}")

    with open(pano_path, 'rb') as f:
        data_url = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"

    result = fal_client.run(
        "fal-ai/imageutils/depth",
        arguments={"image_url": data_url},
    )
    depth_url = result["image"]["url"]

    depth_data = requests.get(depth_url, timeout=60).content
    depth_path = str(work_dir / "depth_map.jpg")
    Path(depth_path).write_bytes(depth_data)

    log.info(f"Depth map saved: {len(depth_data) / 1e6:.2f}MB → {depth_path}")
    return depth_path
