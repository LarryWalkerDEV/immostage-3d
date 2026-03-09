import fal_client
import requests
import os
import base64
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

log = logging.getLogger("immostage.staging")

KIE_KEY = os.environ['KIE_API_KEY']

STYLE_PROMPTS = {
    "midcentury":   "mid-century modern interior, warm walnut wood, Eames chair, warm lighting",
    "coastal":      "coastal Hamptons interior, white linen sofa, rattan, ocean palette",
    "modern":       "contemporary minimalist, white walls, concrete accents, black fixtures",
    "luxury":       "luxury interior, marble surfaces, velvet sofa, gold accents, soft lighting",
    "scandinavian": "Scandinavian hygge, light pine wood, white walls, linen, plants",
    "industrial":   "industrial loft, exposed brick, iron pipes, leather sofa, Edison bulbs",
}

FURNITURE_PROMPTS = {
    "midcentury":   "Eames lounge chair, walnut sideboard, arc floor lamp, geometric rug",
    "coastal":      "white linen sofa, rattan chairs, driftwood coffee table, potted palm",
    "modern":       "low profile sofa, minimal coffee table, concrete planter, pendant light",
    "luxury":       "velvet sofa, marble coffee table, gold chandelier, silk curtains",
    "scandinavian": "cozy linen sofa, pine coffee table, sheepskin rug, monstera plant",
    "industrial":   "leather Chesterfield, metal coffee table, Edison floor lamp, exposed shelving",
}


def image_to_data_url(path):
    data = base64.b64encode(open(path, 'rb').read()).decode()
    return f"data:image/jpeg;base64,{data}"


def stage_single_photo(img_path, style, prompt, idx, work_dir):
    """Two-pass staging: fal.ai ControlNet depth (surfaces) + kie.ai (furniture)."""
    img_url = image_to_data_url(img_path)
    style_prompt = STYLE_PROMPTS.get(style, "contemporary minimalist, white walls, concrete accents, black fixtures")
    furniture_prompt = FURNITURE_PROMPTS.get(style, "low profile sofa, minimal coffee table, concrete planter, pendant light")
    extra = f", {prompt}" if prompt else ""

    log.info(f"Photo {idx}: pass 1A — depth map")

    # Pass 1A: generate depth map
    depth_result = fal_client.run(
        "fal-ai/imageutils/depth",
        arguments={"image_url": img_url},
    )
    depth_url = depth_result["image"]["url"]

    log.info(f"Photo {idx}: pass 1B — ControlNet style transfer ({style})")

    # Pass 1B: style transfer with ControlNet using depth as guidance
    fal_result = fal_client.run(
        "fal-ai/controlnet-sdxl",
        arguments={
            "image_url": img_url,
            "control_image_url": depth_url,
            "controlnet_conditioning_scale": 0.8,
            "prompt": (
                f"{style_prompt}{extra}, photorealistic interior photography, "
                "8k, professional real estate photo, no people, no text"
            ),
            "negative_prompt": (
                "cartoon, painting, illustration, blurry, distorted, unrealistic, "
                "people, text, watermark, low quality"
            ),
            "strength": 0.55,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "image_size": "landscape_16_9",
        },
    )
    styled_url = fal_result["images"][0]["url"]

    log.info(f"Photo {idx}: pass 2 — kie.ai furniture placement")

    # Pass 2: kie.ai furniture placement
    kie_resp = requests.post(
        "https://api.kie.ai/v1/virtual-staging",
        headers={
            "Authorization": f"Bearer {KIE_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "image_url": styled_url,
            "room_type": "living_room",
            "style": style,
            "prompt": furniture_prompt,
            "strength": 0.7,
        },
        timeout=120,
    )
    kie_resp.raise_for_status()
    kie_data = kie_resp.json()
    final_url = kie_data.get("result_url") or styled_url

    out_path = str(work_dir / f"staged_{str(idx).zfill(4)}.jpg")
    img_data = requests.get(final_url, timeout=60).content
    Path(out_path).write_bytes(img_data)

    log.info(f"Photo {idx}: staged → {out_path} ({len(img_data) / 1e6:.2f}MB)")
    return out_path


def stage_all_photos(img_paths, style, prompt, work_dir):
    """Stage all photos in parallel (max 4 workers). Falls back to original on failure."""
    staged = [None] * len(img_paths)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(stage_single_photo, p, style, prompt, i, work_dir): i
            for i, p in enumerate(img_paths)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                staged[idx] = future.result()
            except Exception as e:
                log.warning(f"Staging failed for photo {idx}: {e} — using original")
                staged[idx] = img_paths[idx]

    result = [s for s in staged if s is not None]
    log.info(f"Staging complete: {len(result)}/{len(img_paths)} photos staged")
    return result
