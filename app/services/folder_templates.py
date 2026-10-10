import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_name(name: str, fallback: str = "Unknown") -> str:
    if name is None:
        name = ""
    name = str(name).strip()
    if not name:
        return fallback
    name = _INVALID_CHARS.sub("_", name)
    name = name.rstrip(". ")
    if name.upper() in _WINDOWS_RESERVED:
        name = f"_{name}"
    if not name:
        return fallback
    return name[:200]


def bpm_range_label(bpm: Optional[float]) -> str:
    if bpm is None:
        return "Unknown BPM"
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        return "Unknown BPM"
    for low, high, label in [
        (60, 99, "60-99 BPM"),
        (100, 119, "100-119 BPM"),
        (120, 124, "120-124 BPM"),
        (125, 129, "125-129 BPM"),
        (130, 134, "130-134 BPM"),
        (135, 139, "135-139 BPM"),
        (140, 159, "140-159 BPM"),
        (160, 199, "160-199 BPM"),
    ]:
        if low <= bpm <= high:
            return label
    if bpm < 60:
        return "Below 60 BPM"
    return "200+ BPM"


def build_path(template: str, fields: Dict[str, Optional[str]], base_dir: str = "",
               unknown_bpm_fallback: str = "Unknown BPM",
               unknown_key_fallback: str = "Unknown Key") -> str:
    resolved: Dict[str, str] = {}
    for key, value in fields.items():
        if value is None or str(value).strip() == "":
            if key == "bpm_range":
                resolved[key] = sanitize_name(unknown_bpm_fallback)
            elif key == "musical_key":
                resolved[key] = sanitize_name(unknown_key_fallback)
            else:
                resolved[key] = "Unknown"
        else:
            resolved[key] = sanitize_name(str(value))

    parts = template.split("/")
    sanitized_parts = []
    for part in parts:
        try:
            rendered = part.format(**resolved)
        except (KeyError, IndexError, ValueError):
            rendered = part
        sanitized_parts.append(sanitize_name(rendered, fallback="Unknown"))

    path = "/".join(sanitized_parts)
    if base_dir:
        path = f"{base_dir.rstrip('/')}/{path}"
    return path


def resolve_destination(track_fields: Dict[str, Optional[str]],
                        base_dir: str,
                        folder_template: str,
                        file_template: str,
                        extension: str,
                        unknown_bpm_fallback: str = "Unknown BPM",
                        unknown_key_fallback: str = "Unknown Key") -> str:
    folder = build_path(folder_template, track_fields, base_dir=base_dir,
                        unknown_bpm_fallback=unknown_bpm_fallback,
                        unknown_key_fallback=unknown_key_fallback)
    filename = build_path(file_template, track_fields,
                          unknown_bpm_fallback=unknown_bpm_fallback,
                          unknown_key_fallback=unknown_key_fallback)
    ext = extension.lstrip(".")
    return f"{folder}/{filename}.{ext}"


def unique_destination(path: str) -> str:
    import os
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    idx = 1
    while True:
        candidate = f"{base} ({idx}){ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1
