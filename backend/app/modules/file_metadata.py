"""
Offline, read-only file metadata extraction: cryptographic hashes for every
file, plus EXIF for images and document metadata for PDFs. Nothing is
uploaded anywhere - all processing happens locally.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from pypdf import PdfReader


def _hashes(path: Path) -> dict:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest()}


def _dms_to_decimal(dms, ref) -> float | None:
    try:
        degrees, minutes, seconds = dms
        value = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
        if ref in ("S", "W"):
            value = -value
        return round(value, 6)
    except Exception:  # noqa: BLE001
        return None


def _extract_image_metadata(path: Path) -> dict:
    out = {"file_type": "image"}
    try:
        with Image.open(path) as img:
            out["format"] = img.format
            out["dimensions"] = f"{img.width}x{img.height}"
            out["mode"] = img.mode
            exif_raw = img._getexif() if hasattr(img, "_getexif") else None
            exif = {}
            gps = {}
            if exif_raw:
                for tag_id, value in exif_raw.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "GPSInfo":
                        for gps_id, gps_val in value.items():
                            gps_tag = GPSTAGS.get(gps_id, gps_id)
                            gps[gps_tag] = gps_val
                    else:
                        if isinstance(value, bytes):
                            try:
                                value = value.decode(errors="replace")
                            except Exception:  # noqa: BLE001
                                value = repr(value)
                        exif[tag] = value
            out["exif"] = {k: v for k, v in exif.items() if not str(k).startswith("_")}
            if gps:
                lat = _dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef")) if gps.get(
                    "GPSLatitude") else None
                lon = _dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef")) if gps.get(
                    "GPSLongitude") else None
                out["gps"] = {"latitude": lat, "longitude": lon, "raw": {k: str(v) for k, v in gps.items()}}
                if lat is not None and lon is not None:
                    out["gps"]["map_link"] = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
    except Exception as e:  # noqa: BLE001
        out["error"] = f"Could not parse image: {e}"
    return out


def _extract_pdf_metadata(path: Path) -> dict:
    out = {"file_type": "pdf"}
    try:
        reader = PdfReader(str(path))
        info = reader.metadata or {}
        out["page_count"] = len(reader.pages)
        out["metadata"] = {str(k).lstrip("/"): str(v) for k, v in dict(info).items()}
        out["encrypted"] = reader.is_encrypted
    except Exception as e:  # noqa: BLE001
        out["error"] = f"Could not parse PDF: {e}"
    return out


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".heic"}


def extract_metadata(path: str, original_filename: str) -> dict:
    p = Path(path)
    result = {
        "filename": original_filename,
        "size_bytes": p.stat().st_size,
        "hashes": _hashes(p),
    }
    ext = Path(original_filename).suffix.lower()
    if ext == ".pdf":
        result.update(_extract_pdf_metadata(p))
    elif ext in IMAGE_EXT:
        result.update(_extract_image_metadata(p))
    else:
        result["file_type"] = "other"
        result["note"] = "Only hashes computed - EXIF/PDF metadata extraction supports images and PDFs."
    return result
