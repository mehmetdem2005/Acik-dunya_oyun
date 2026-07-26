#!/usr/bin/env python3
"""Generate deterministic glTF-compatible PBR textures for the dragon asset."""
from __future__ import annotations

import argparse
from pathlib import Path
import math

import numpy as np
from PIL import Image, ImageFilter


def value_noise(size: int, seed: int, octaves: int = 6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.linspace(0.0, math.tau, size, dtype=np.float32)[:, None]
    x = np.linspace(0.0, math.tau, size, dtype=np.float32)[None, :]
    result = np.zeros((size, size), dtype=np.float32)
    amplitude = 1.0
    norm = 0.0
    for octave in range(octaves):
        frequency = float(2 ** octave)
        phase_x, phase_y, phase_m = rng.random(3) * math.tau
        layer = (
            np.sin(x * frequency * (0.73 + rng.random() * 0.55) + phase_x)
            + np.cos(y * frequency * (0.81 + rng.random() * 0.48) + phase_y)
            + np.sin((x + y) * frequency * 0.47 + phase_m)
        ) / 3.0
        result += layer * amplitude
        norm += amplitude
        amplitude *= 0.53
    result = result / max(norm, 1e-6)
    return np.clip(result * 0.5 + 0.5, 0.0, 1.0)


def scale_pattern(size: int, density: float, seed: int) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size]
    u = xx / size
    v = yy / size
    rows = max(8, int(density))
    row = np.floor(v * rows)
    offset = (row % 2) * 0.5
    cell_x = np.mod(u * rows * 1.45 + offset, 1.0) - 0.5
    cell_y = np.mod(v * rows, 1.0) - 0.5
    dist = np.sqrt((cell_x / 0.48) ** 2 + ((cell_y + 0.05) / 0.58) ** 2)
    ridge = np.clip(1.0 - dist, 0.0, 1.0)
    ridge = ridge ** 1.7
    noise = value_noise(size, seed, 4)
    return np.clip(ridge * 0.72 + noise * 0.28, 0.0, 1.0)


def height_to_normal(height: np.ndarray, strength: float = 6.0) -> np.ndarray:
    gy, gx = np.gradient(height.astype(np.float32))
    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx /= length
    ny /= length
    nz /= length
    normal = np.stack((nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5), axis=-1)
    return np.uint8(np.clip(normal * 255.0, 0, 255))


def save_rgb(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.uint8(np.clip(array, 0, 255)), mode="RGB").save(path)


def body_set(out: Path, size: int) -> None:
    macro = value_noise(size, 101, 7)
    micro = value_noise(size, 102, 5)
    scales = scale_pattern(size, 38.0, 103)
    cracks = np.clip(value_noise(size, 104, 6) - 0.58, 0, 1) * 2.0

    base = np.zeros((size, size, 3), dtype=np.float32)
    base[..., 0] = 38 + macro * 38 + scales * 20 + cracks * 14
    base[..., 1] = 31 + macro * 29 + scales * 16
    base[..., 2] = 28 + macro * 25 + scales * 13
    rust = np.clip(value_noise(size, 105, 4) - 0.6, 0, 1)
    base[..., 0] += rust * 55
    base[..., 1] += rust * 20
    base[..., 2] += rust * 8
    cavity = 1.0 - scales
    base *= (0.72 + cavity[..., None] * 0.28)

    height = np.clip(scales * 0.72 + micro * 0.2 - cracks * 0.15, 0, 1)
    normal = height_to_normal(height, 9.0)
    ao = np.uint8(np.clip((0.48 + scales * 0.5 - cracks * 0.2) * 255, 0, 255))
    rough = np.uint8(np.clip((0.62 + macro * 0.24 - scales * 0.08) * 255, 0, 255))
    metallic = np.zeros_like(ao, dtype=np.uint8)
    orm = np.stack((ao, rough, metallic), axis=-1)

    save_rgb(out / "body_basecolor.png", base)
    save_rgb(out / "body_normal.png", normal)
    save_rgb(out / "body_orm.png", orm)
    Image.fromarray(np.uint8(height * 255), mode="L").save(out / "body_height.png")


def ventral_set(out: Path, size: int) -> None:
    macro = value_noise(size, 201, 6)
    plates = scale_pattern(size, 18.0, 202)
    base = np.zeros((size, size, 3), dtype=np.float32)
    base[..., 0] = 132 + macro * 55 + plates * 25
    base[..., 1] = 122 + macro * 47 + plates * 20
    base[..., 2] = 104 + macro * 40 + plates * 14
    stains = np.clip(value_noise(size, 203, 4) - 0.63, 0, 1)
    base[..., 0] -= stains * 50
    base[..., 1] -= stains * 42
    base[..., 2] -= stains * 30
    height = np.clip(plates * 0.85 + macro * 0.15, 0, 1)
    normal = height_to_normal(height, 7.0)
    ao = np.uint8(np.clip((0.55 + plates * 0.43) * 255, 0, 255))
    rough = np.uint8(np.clip((0.68 + macro * 0.2) * 255, 0, 255))
    orm = np.stack((ao, rough, np.zeros_like(ao)), axis=-1)
    save_rgb(out / "ventral_basecolor.png", base)
    save_rgb(out / "ventral_normal.png", normal)
    save_rgb(out / "ventral_orm.png", orm)


def wing_set(out: Path, size: int) -> None:
    yy, xx = np.mgrid[0:size, 0:size]
    u = xx / max(1, size - 1)
    v = yy / max(1, size - 1)
    macro = value_noise(size, 301, 7)
    fibers = 0.5 + 0.5 * np.sin((u * 26 + v * 5 + macro * 2.5) * math.pi)
    veins = np.zeros((size, size), dtype=np.float32)
    for slope, intercept, width in [
        (0.12, 0.16, 0.010), (0.28, 0.26, 0.008), (0.48, 0.34, 0.007),
        (0.70, 0.41, 0.006), (-0.18, 0.68, 0.006), (-0.35, 0.82, 0.005)
    ]:
        line = np.abs(v - (intercept + slope * u))
        veins = np.maximum(veins, np.exp(-(line / width) ** 2))
    edge = np.clip(np.minimum.reduce([u, 1-u, v, 1-v]) * 9.0, 0, 1)
    damage = value_noise(size, 302, 5)
    holes = ((damage > 0.79) & (edge < 0.45)).astype(np.float32)
    holes_img = Image.fromarray(np.uint8(holes * 255), mode="L").filter(ImageFilter.GaussianBlur(radius=max(1, size // 512)))
    holes = np.asarray(holes_img, dtype=np.float32) / 255.0
    alpha = np.uint8(np.clip((1.0 - holes * 0.9) * 255, 0, 255))

    base = np.zeros((size, size, 3), dtype=np.float32)
    base[..., 0] = 64 + macro * 45 + fibers * 19 + veins * 25
    base[..., 1] = 24 + macro * 25 + fibers * 8 + veins * 9
    base[..., 2] = 23 + macro * 22 + fibers * 6 + veins * 7
    base *= (0.68 + edge[..., None] * 0.32)
    height = np.clip(fibers * 0.18 + veins * 0.78 + macro * 0.12, 0, 1)
    normal = height_to_normal(height, 4.5)
    ao = np.uint8(np.clip((0.68 + edge * 0.25 - veins * 0.08) * 255, 0, 255))
    rough = np.uint8(np.clip((0.58 + macro * 0.23 - veins * 0.10) * 255, 0, 255))
    orm = np.stack((ao, rough, np.zeros_like(ao)), axis=-1)

    rgba = np.dstack((np.uint8(np.clip(base, 0, 255)), alpha))
    Image.fromarray(rgba, mode="RGBA").save(out / "wings_basecolor.png")
    save_rgb(out / "wings_normal.png", normal)
    save_rgb(out / "wings_orm.png", orm)
    Image.fromarray(alpha, mode="L").save(out / "wings_alpha.png")


def keratin_set(out: Path, size: int) -> None:
    macro = value_noise(size, 401, 6)
    striation = 0.5 + 0.5 * np.sin(np.linspace(0, 42 * math.pi, size)[None, :] + macro * 4.0)
    base = np.zeros((size, size, 3), dtype=np.float32)
    base[..., 0] = 77 + macro * 65 + striation * 18
    base[..., 1] = 64 + macro * 50 + striation * 14
    base[..., 2] = 52 + macro * 38 + striation * 10
    height = np.clip(striation * 0.45 + macro * 0.55, 0, 1)
    normal = height_to_normal(height, 5.0)
    ao = np.uint8(np.clip((0.72 + macro * 0.22) * 255, 0, 255))
    rough = np.uint8(np.clip((0.70 + macro * 0.20 - striation * 0.08) * 255, 0, 255))
    orm = np.stack((ao, rough, np.zeros_like(ao)), axis=-1)
    save_rgb(out / "keratin_basecolor.png", base)
    save_rgb(out / "keratin_normal.png", normal)
    save_rgb(out / "keratin_orm.png", orm)


def mouth_eye_sets(out: Path, size: int) -> None:
    macro = value_noise(size, 501, 6)
    mouth = np.zeros((size, size, 3), dtype=np.float32)
    mouth[..., 0] = 92 + macro * 70
    mouth[..., 1] = 28 + macro * 32
    mouth[..., 2] = 30 + macro * 34
    save_rgb(out / "mouth_basecolor.png", mouth)
    rough = np.uint8(np.clip((0.28 + macro * 0.18) * 255, 0, 255))
    ao = np.uint8(np.clip((0.75 + macro * 0.20) * 255, 0, 255))
    save_rgb(out / "mouth_orm.png", np.stack((ao, rough, np.zeros_like(ao)), axis=-1))
    save_rgb(out / "mouth_normal.png", height_to_normal(macro, 2.5))

    teeth = np.zeros((size, size, 3), dtype=np.float32)
    teeth[..., 0] = 176 + macro * 52
    teeth[..., 1] = 164 + macro * 45
    teeth[..., 2] = 137 + macro * 34
    save_rgb(out / "teeth_basecolor.png", teeth)
    teeth_r = np.uint8(np.clip((0.48 + macro * 0.28) * 255, 0, 255))
    save_rgb(out / "teeth_orm.png", np.stack((ao, teeth_r, np.zeros_like(ao)), axis=-1))
    save_rgb(out / "teeth_normal.png", height_to_normal(macro, 1.8))

    eye_size = max(256, size // 4)
    yy, xx = np.mgrid[0:eye_size, 0:eye_size]
    cx = cy = (eye_size - 1) * 0.5
    dx = (xx - cx) / eye_size
    dy = (yy - cy) / eye_size
    radius = np.sqrt(dx * dx + dy * dy)
    iris = np.clip(1.0 - radius * 2.2, 0, 1)
    pupil = (np.abs(dx) < 0.035) & (radius < 0.34)
    eye = np.zeros((eye_size, eye_size, 3), dtype=np.float32)
    eye[..., 0] = 44 + iris * 150
    eye[..., 1] = 22 + iris * 105
    eye[..., 2] = 12 + iris * 30
    eye[pupil] = (9, 5, 3)
    save_rgb(out / "eyes_basecolor.png", eye)
    eye_rough = np.full((eye_size, eye_size), 28, dtype=np.uint8)
    eye_ao = np.full((eye_size, eye_size), 255, dtype=np.uint8)
    save_rgb(out / "eyes_orm.png", np.stack((eye_ao, eye_rough, np.zeros_like(eye_ao)), axis=-1))
    flat_normal = np.zeros((eye_size, eye_size, 3), dtype=np.uint8)
    flat_normal[..., 0] = 128
    flat_normal[..., 1] = 128
    flat_normal[..., 2] = 255
    save_rgb(out / "eyes_normal.png", flat_normal)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=2048)
    args = parser.parse_args()
    if args.size not in {1024, 2048, 4096}:
        raise SystemExit("Texture size must be 1024, 2048 or 4096.")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    body_set(out, args.size)
    ventral_set(out, args.size)
    wing_set(out, args.size)
    keratin_set(out, args.size)
    mouth_eye_sets(out, args.size)
    print(f"Generated PBR textures in {out} at {args.size}x{args.size}")


if __name__ == "__main__":
    main()
