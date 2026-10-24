"""Photo evidence: capture time and GPS from a photo's EXIF block, and the checks a claim cares about."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import UTC, date, datetime

from PIL import Image, UnidentifiedImageError

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_DATETIME_ORIGINAL = 0x9003
_DATETIME = 0x0132


@dataclass(frozen=True)
class PhotoMeta:
    name: str
    taken_at: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    readable: bool = True
    # The phone's location when the photo was uploaded. Weaker than GPS in the photo itself (the farmer may
    # have uploaded it elsewhere), so it never replaces it and a photo that needs it is still warned about.
    device_lat: float | None = None
    device_lon: float | None = None


def _to_degrees(value: object, ref: object) -> float | None:
    try:
        d, m, s = (float(x) for x in value)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        return None
    degrees = d + m / 60 + s / 3600
    return -degrees if str(ref).upper() in ("S", "W") else degrees


def _parse_time(raw: object) -> datetime | None:
    try:
        return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def read_photo(name: str, data: bytes) -> PhotoMeta:
    """Never raises: a file that is not an image, or has no EXIF, comes back with the fields empty."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
            sub = exif.get_ifd(_EXIF_IFD)
            gps = exif.get_ifd(_GPS_IFD)
    except (UnidentifiedImageError, OSError, ValueError):
        return PhotoMeta(name, readable=False)
    taken = _parse_time(sub.get(_DATETIME_ORIGINAL) or exif.get(_DATETIME))
    lat = _to_degrees(gps.get(2), gps.get(1)) if gps.get(2) else None
    lon = _to_degrees(gps.get(4), gps.get(3)) if gps.get(4) else None
    return PhotoMeta(name, taken, lat, lon)


def photo_warnings(photos: list[PhotoMeta], event_date: date, tolerance_days: int = 1) -> list[str]:
    """What a reviewer would question about the photos. Empty list means nothing to flag."""
    out: list[str] = []
    for p in photos:
        if not p.readable:
            out.append(f"{p.name}: not a readable image")
            continue
        if p.taken_at is None:
            out.append(f"{p.name}: no capture time in the photo (EXIF missing)")
        else:
            gap = (p.taken_at.date() - event_date).days
            if gap < -tolerance_days:
                out.append(f"{p.name}: taken {-gap} days BEFORE the event date")
            elif gap > tolerance_days:
                out.append(f"{p.name}: taken {gap} days after the event date")
        if p.lat is None or p.lon is None:
            if p.device_lat is not None and p.device_lon is not None:
                out.append(f"{p.name}: no GPS in the photo; the phone's location when uploading is recorded instead")
            else:
                out.append(f"{p.name}: no GPS location in the photo")
    return out
