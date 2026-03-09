import subprocess
import shutil
import struct
import logging
from pathlib import Path
import numpy as np

log = logging.getLogger("immostage.recon")

GPU_PROFILES = {
    "A100":    {"iterations": 5000, "resolution": 2},
    "A10G":    {"iterations": 3000, "resolution": 2},
    "RTX4090": {"iterations": 3000, "resolution": 2},
    "default": {"iterations": 1500, "resolution": 4},
}


def get_gpu_profile():
    """Detect GPU and return appropriate training profile."""
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            timeout=10,
        ).decode().strip()
        for key in GPU_PROFILES:
            if key in out:
                log.info(f"GPU detected: {out} → profile: {key}")
                return GPU_PROFILES[key]
        log.info(f"GPU detected: {out} → using default profile")
    except Exception as e:
        log.warning(f"Could not detect GPU: {e}")
    return GPU_PROFILES["default"]


def run_3dgs(photo_paths, work_dir):
    """
    Run COLMAP feature extraction + nerfstudio splatfacto training.
    Returns path to .splat file, or None if COLMAP fails.
    """
    img_dir = work_dir / "images"
    img_dir.mkdir(exist_ok=True)

    for i, p in enumerate(photo_paths):
        shutil.copy(p, img_dir / f"image_{str(i).zfill(4)}.jpg")

    log.info(f"3DGS: processing {len(photo_paths)} images from {img_dir}")

    ns_data = work_dir / "ns_processed"
    ns_out = work_dir / "ns_output"
    profile = get_gpu_profile()

    # Step 1: COLMAP via nerfstudio's ns-process-data
    try:
        result = subprocess.run(
            [
                "ns-process-data", "images",
                "--data", str(img_dir),
                "--output-dir", str(ns_data),
                "--num-downscales", "0",
                "--matching-method", "exhaustive",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        log.info(f"COLMAP complete: {ns_data}")
        log.debug(result.stdout[-1000:] if result.stdout else "")
    except subprocess.CalledProcessError as e:
        log.warning(f"COLMAP failed (exit {e.returncode}): {e.stderr[-500:]}")
        return None
    except subprocess.TimeoutExpired:
        log.warning("COLMAP timed out after 300s")
        return None

    # Step 2: nerfstudio splatfacto training
    try:
        result = subprocess.run(
            [
                "ns-train", "splatfacto",
                "--data", str(ns_data),
                "--output-dir", str(ns_out),
                "--max-num-iterations", str(profile['iterations']),
                f"--pipeline.model.num-downscales={profile['resolution']}",
                "--viewer.quit-on-train-completion", "True",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        log.info(f"splatfacto training complete in {ns_out}")
        log.debug(result.stdout[-1000:] if result.stdout else "")
    except subprocess.CalledProcessError as e:
        log.warning(f"splatfacto training failed (exit {e.returncode}): {e.stderr[-500:]}")
        return None
    except subprocess.TimeoutExpired:
        log.warning("splatfacto training timed out after 600s")
        return None

    # Step 3: Export gaussian splat
    config = next(ns_out.rglob("config.yml"), None)
    if not config:
        log.warning("No config.yml found in nerfstudio output")
        return None

    export_dir = work_dir / "export"
    try:
        subprocess.run(
            [
                "ns-export", "gaussian-splat",
                "--load-config", str(config),
                "--output-dir", str(export_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        log.warning(f"ns-export failed (exit {e.returncode}): {e.stderr[-500:]}")
        return None

    ply_files = list(export_dir.glob("*.ply"))
    if not ply_files:
        log.warning("No .ply file found after export")
        return None

    splat_path = str(work_dir / "scene.splat")
    ply_to_splat(str(ply_files[0]), splat_path)
    return splat_path


def ply_to_splat(ply_path, splat_path):
    """
    Convert nerfstudio .ply gaussian splat output to .splat binary format.
    Each gaussian: 3D position (xyz float32) + scale (float32x3) + RGBA (uint8x4) + rotation (uint8x4)
    = 32 bytes per gaussian.
    """
    try:
        from plyfile import PlyData
    except ImportError:
        subprocess.run(["pip", "install", "plyfile", "-q"], check=True)
        from plyfile import PlyData

    ply = PlyData.read(ply_path)
    v = ply['vertex']
    n = len(v['x'])
    names = set(v.data.dtype.names)

    log.info(f"ply_to_splat: converting {n:,} gaussians from {ply_path}")

    # XYZ positions
    xyz = np.stack([v['x'], v['y'], v['z']], axis=1).astype(np.float32)

    # Scale (exponentiated, as nerfstudio stores log-scale)
    def get_scale(field):
        if field in names:
            return np.exp(v.data[field]).astype(np.float32)
        return np.zeros(n, dtype=np.float32)

    scale = np.stack([get_scale('scale_0'), get_scale('scale_1'), get_scale('scale_2')], axis=1)

    # Opacity → alpha (sigmoid activation)
    op = v.data['opacity'] if 'opacity' in names else np.zeros(n, dtype=np.float32)
    alpha = (1.0 / (1.0 + np.exp(-op)) * 255).clip(0, 255).astype(np.uint8)

    # RGB from spherical harmonics DC component
    def sh_to_uint8(field):
        if field in names:
            return np.clip((v.data[field] * 0.2820947917 + 0.5) * 255, 0, 255).astype(np.uint8)
        return np.zeros(n, dtype=np.uint8)

    r = sh_to_uint8('f_dc_0')
    g = sh_to_uint8('f_dc_1')
    b = sh_to_uint8('f_dc_2')

    # Rotation quaternion → uint8 (packed as [0,255])
    rot_fields = ['rot_0', 'rot_1', 'rot_2', 'rot_3']
    if all(f in names for f in rot_fields):
        rot = np.stack([v.data[f] for f in rot_fields], axis=1).astype(np.float32)
    else:
        rot = np.tile([1.0, 0.0, 0.0, 0.0], (n, 1)).astype(np.float32)
    rot_b = (rot * 128 + 128).clip(0, 255).astype(np.uint8)

    # Sort by descending opacity for front-to-back rendering
    order = np.argsort(-alpha)

    with open(splat_path, 'wb') as f:
        for i in order:
            f.write(struct.pack('fff', *xyz[i]))
            f.write(struct.pack('fff', *scale[i]))
            f.write(struct.pack('BBBB', r[i], g[i], b[i], alpha[i]))
            f.write(struct.pack('BBBB', *rot_b[i]))

    size_mb = Path(splat_path).stat().st_size / 1e6
    log.info(f".splat written: {n:,} gaussians, {size_mb:.1f}MB → {splat_path}")
