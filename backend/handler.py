import runpod
import os
import shutil
import tempfile
import logging
import time
from pathlib import Path
from supabase import create_client

log = logging.getLogger("immostage")

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_KEY']


def handler(job):
    inp = job['input']
    room_id = inp['room_id']
    tour_id = inp['tour_id']
    mode = inp['mode']          # 'staged' or 'real'
    style = inp.get('style', 'modern')
    prompt = inp.get('prompt', '')
    folder = inp['input_folder']

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    work_dir = Path(tempfile.mkdtemp(prefix=f"immostage_{room_id}_"))
    start_ms = int(time.time() * 1000)

    try:
        # 1. Download input photos
        yield _status(sb, room_id, 'processing', "Downloading photos")
        img_paths = download_photos(sb, folder, work_dir)

        if not img_paths:
            raise ValueError(f"No .jpg files found in folder: {folder}")

        log.info(f"Room {room_id}: downloaded {len(img_paths)} photos, mode={mode}, style={style}")

        # 2. Stage (staged mode) or skip (real mode)
        if mode == 'staged':
            yield _status(sb, room_id, 'staging', f"AI staging: {style}")
            from staging import stage_all_photos
            staged_paths = stage_all_photos(img_paths, style, prompt, work_dir)
        else:
            staged_paths = img_paths
            yield _status(sb, room_id, 'staging', "Real mode — skipping AI staging")

        # 3. Stitch panorama
        yield _status(sb, room_id, 'stitching', "Stitching panorama")
        from panorama import stitch_panorama
        pano_path = stitch_panorama(staged_paths, work_dir)
        pano_url = upload(sb, room_id, pano_path, "panorama_staged.jpg", "image/jpeg")
        update_room(sb, room_id, panorama_url=pano_url)

        # 4. Depth map → fast 3D ready
        yield _status(sb, room_id, 'depth', "Generating depth map")
        from panorama import generate_depth_map
        depth_path = generate_depth_map(pano_path, work_dir)
        depth_url = upload(sb, room_id, depth_path, "depth_map.jpg", "image/jpeg")
        update_room(sb, room_id, status='fast_ready', depth_url=depth_url)

        # 5. COLMAP + nerfstudio 3DGS (optional — requires GPU image)
        splat_path = None
        try:
            yield _status(sb, room_id, 'colmap', "3D reconstruction (COLMAP + 3DGS)")
            from reconstruction import run_3dgs
            splat_path = run_3dgs(staged_paths, work_dir)
        except ImportError as e:
            log.warning(f"3DGS not available (slim image): {e}")
        except Exception as e:
            log.warning(f"3DGS failed: {e}")
        splat_url = (
            upload(sb, room_id, splat_path, "scene.splat", "application/octet-stream")
            if splat_path else None
        )

        # 6. Mark complete
        elapsed = int(time.time() * 1000) - start_ms
        cost = estimate_cost(mode, len(img_paths))
        error_msg = None if splat_url else "COLMAP failed — fast 3D available"
        update_room(
            sb, room_id,
            status='complete',
            splat_url=splat_url,
            cost_usd=cost,
            processing_ms=elapsed,
            error_msg=error_msg,
        )

        log.info(f"Room {room_id}: complete in {elapsed}ms, cost=${cost}, splat={'yes' if splat_url else 'no'}")

        return {
            'stage': 'complete',
            'room_id': room_id,
            'panorama_url': pano_url,
            'depth_url': depth_url,
            'splat_url': splat_url,
        }

    except Exception as e:
        log.exception(f"Room {room_id} failed")
        update_room(sb, room_id, status='failed', error_msg=str(e))
        return {'error': str(e)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _status(sb, room_id, status_str, msg):
    """Update room status and yield a progress event."""
    update_room(sb, room_id, status=status_str)
    log.info(f"Room {room_id} [{status_str}]: {msg}")
    return {'stage': status_str, 'msg': msg}


def update_room(sb, room_id, **kwargs):
    """Update room record fields. Skips None values."""
    payload = {k: v for k, v in kwargs.items() if v is not None}
    if payload:
        try:
            sb.table('tour_rooms').update(payload).eq('id', room_id).execute()
        except Exception as e:
            log.warning(f"Failed to update room {room_id}: {e}")


def download_photos(sb, folder, work_dir):
    """Download all .jpg files from a Supabase Storage folder."""
    img_dir = work_dir / "images"
    img_dir.mkdir(exist_ok=True)

    files = sb.storage.from_('scans').list(folder)
    paths = []
    for f in sorted(files, key=lambda x: x['name']):
        if not f['name'].lower().endswith('.jpg'):
            continue
        data = sb.storage.from_('scans').download(f"{folder}{f['name']}")
        p = img_dir / f['name']
        p.write_bytes(data)
        paths.append(str(p))
        log.debug(f"Downloaded: {f['name']} ({len(data)} bytes)")

    return paths


def upload(sb, room_id, local_path, filename, content_type):
    """Upload a file to Supabase Storage and return its public URL."""
    key = f"scans/{room_id}/{filename}"
    with open(local_path, 'rb') as f:
        data = f.read()

    sb.storage.from_('scans').upload(
        key,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    url = sb.storage.from_('scans').get_public_url(key)
    log.info(f"Uploaded {filename} ({len(data) / 1e6:.2f}MB) → {url}")
    return url


def estimate_cost(mode, n_photos):
    """Rough cost estimate in USD: $0.08/image for staging + $0.48 GPU base."""
    if mode == 'staged':
        return round(n_photos * 0.08 + 0.48, 4)
    return round(0.48, 4)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
