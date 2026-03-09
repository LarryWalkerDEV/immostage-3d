import logging
import os
from pathlib import Path

log = logging.getLogger("immostage.storage")

BUCKET = "scans"


def get_room_folder(room_id: str) -> str:
    """Return the canonical Supabase Storage folder path for a room's outputs."""
    return f"scans/{room_id}/"


def get_input_folder(tour_id: str, room_id: str) -> str:
    """Return the canonical input folder path for raw photo uploads."""
    return f"uploads/{tour_id}/{room_id}/"


def upload_file(sb, room_id: str, local_path: str, filename: str, content_type: str) -> str:
    """
    Upload a local file to Supabase Storage under scans/{room_id}/{filename}.
    Returns the public URL.
    """
    key = f"scans/{room_id}/{filename}"
    data = Path(local_path).read_bytes()

    sb.storage.from_(BUCKET).upload(
        key,
        data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    url = sb.storage.from_(BUCKET).get_public_url(key)
    log.info(f"Uploaded {filename} ({len(data) / 1e6:.2f}MB) → {url}")
    return url


def download_folder(sb, folder: str, dest_dir: str) -> list[str]:
    """
    Download all .jpg files from a Supabase Storage folder to dest_dir.
    Returns sorted list of local file paths.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    files = sb.storage.from_(BUCKET).list(folder)
    paths = []
    for f in sorted(files, key=lambda x: x['name']):
        if not f['name'].lower().endswith('.jpg'):
            continue
        data = sb.storage.from_(BUCKET).download(f"{folder}{f['name']}")
        p = dest / f['name']
        p.write_bytes(data)
        paths.append(str(p))
        log.debug(f"Downloaded: {f['name']} ({len(data)} bytes)")

    log.info(f"Downloaded {len(paths)} images from {folder}")
    return paths


def delete_room_outputs(sb, room_id: str) -> None:
    """Delete all processed outputs for a room (not the original uploads)."""
    prefix = f"scans/{room_id}/"
    files = sb.storage.from_(BUCKET).list(f"scans/{room_id}")
    keys = [f"{prefix}{f['name']}" for f in files]
    if keys:
        sb.storage.from_(BUCKET).remove(keys)
        log.info(f"Deleted {len(keys)} files for room {room_id}")
