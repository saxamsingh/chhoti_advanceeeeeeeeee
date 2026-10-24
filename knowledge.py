"""Loaders for the sourced knowledge files (knowledge/*.yaml). Nothing about prices, MSP or distances is
hardcoded in code: it lives in those files, each with a source or an `assumed` flag."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Settings


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --- MSP --------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MspEntry:
    crop: str
    marketing_season: str
    price_rs_per_qtl: float
    source_url: str
    source_title: str
    quality: str  # official | secondary
    on_sale_now: bool
    note: str = ""


def msp_for(settings: Settings, crop: str) -> MspEntry | None:
    """The MSP for the season whose grain is on sale now, or None when the crop has no researched MSP."""
    entries = _load(settings.knowledge_dir / "msp.yaml").get("crops", {}).get(crop, [])
    parsed = [
        MspEntry(
            crop=crop,
            marketing_season=e["marketing_season"],
            price_rs_per_qtl=float(e["price_rs_per_qtl"]),
            source_url=e["source_url"],
            source_title=e.get("source_title", ""),
            quality=e.get("quality", "secondary"),
            on_sale_now=bool(e.get("on_sale_now")),
            note=e.get("note", ""),
        )
        for e in entries
    ]
    return next((e for e in parsed if e.on_sale_now), None)


# --- mandis and selling rules ----------------------------------------------------------------------------------
@dataclass(frozen=True)
class Mandi:
    name: str
    distance_km: float
    assumed: bool
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class MarketConfig:
    price_url: str
    rate_rs_per_qtl_per_km: float
    rate_assumed: bool
    max_age_days: int
    min_ratio_to_msp: float
    max_ratio_to_msp: float
    min_mandis: int
    districts: dict[str, list[Mandi]] = field(default_factory=dict)

    def mandis_for(self, district: str) -> list[Mandi]:
        for name, mandis in self.districts.items():
            if name.lower() == district.lower():
                return mandis
        return []


def market_config(settings: Settings) -> MarketConfig:
    doc = _load(settings.knowledge_dir / "mandi_costs.yaml")
    rules = doc.get("price_rules", {})
    districts = {
        name: [
            Mandi(
                m["name"],
                float(m["distance_km"]),
                bool(m.get("assumed", True)),
                tuple(m.get("aliases", [m["name"]])),
            )
            for m in d.get("mandis", [])
        ]
        for name, d in doc.get("districts", {}).items()
    }
    return MarketConfig(
        price_url=doc["price_source"]["url"],
        rate_rs_per_qtl_per_km=float(doc["transport"]["rs_per_qtl_per_km"]),
        rate_assumed=bool(doc["transport"].get("assumed", True)),
        max_age_days=int(rules.get("max_age_days", 3)),
        min_ratio_to_msp=float(rules.get("min_ratio_to_msp", 0.6)),
        max_ratio_to_msp=float(rules.get("max_ratio_to_msp", 2.0)),
        min_mandis=int(rules.get("min_mandis", 3)),
        districts=districts,
    )


# --- weather ----------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Intimation:
    hours: int
    source_url: str
    source_title: str


def imd_url(settings: Settings) -> str:
    return _load(settings.knowledge_dir / "weather.yaml")["imd"]["url"]


def intimation(settings: Settings) -> Intimation:
    doc = _load(settings.knowledge_dir / "weather.yaml")["intimation"]
    return Intimation(int(doc["hours"]), doc["source_url"], doc["source_title"])
