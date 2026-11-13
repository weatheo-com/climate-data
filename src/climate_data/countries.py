"""Per-country build settings: CDS boxes, places loader, URL language, scope notes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "places" / "raw"


@dataclass(frozen=True)
class Box:
    name: str
    bbox: tuple[float, float, float, float]  # N, W, S, E (CDS area order)

    def contains(self, lat, lon):
        n, w, s, e = self.bbox
        return (lat <= n) & (lat >= s) & (lon >= w) & (lon <= e)


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    boxes: tuple[Box, ...]
    lang: str
    places_default: Path
    code_label: str
    # places outside every box: dropped (and described) when True, error when False
    drop_outside: bool = False
    excluded: str = ""
    loader: Callable[[Path], pd.DataFrame] = field(default=None, repr=False)

    def load_places(self, path: str | Path | None = None) -> pd.DataFrame:
        return self.loader(Path(path) if path else self.places_default)


def _load_fr(path: Path) -> pd.DataFrame:
    from . import places_fr

    p = path / "communes-france-2026.csv" if path.is_dir() else path
    return places_fr.load(p)


def _generic(cc: str):
    def load(path: Path) -> pd.DataFrame:
        from . import places_generic

        return places_generic.load(cc, path)

    return load


COUNTRIES: dict[str, Country] = {
    "FR": Country(
        code="FR", name="France",
        boxes=(Box("metropolitan France incl. Corsica", (51.2, -5.3, 41.3, 9.7)),),
        lang="fr", places_default=RAW / "fr", code_label="INSEE commune code",
        drop_outside=True,
        excluded="Overseas departments and territories (Guadeloupe, Martinique, Guyane, "
                 "La Réunion, Mayotte and the overseas collectivities) are out of scope in "
                 "this version; only metropolitan France including Corsica is covered.",
        loader=_load_fr,
    ),
    "PT": Country(
        code="PT", name="Portugal",
        boxes=(
            Box("mainland Portugal", (42.2, -9.6, 36.9, -6.1)),
            Box("Madeira", (33.2, -17.4, 32.3, -16.2)),
            Box("Azores", (40.0, -31.4, 36.9, -24.9)),
        ),
        lang="pt", places_default=RAW / "pt", code_label="municipality DICO code",
        loader=_generic("PT"),
    ),
    "LU": Country(
        code="LU", name="Luxembourg",
        boxes=(Box("Luxembourg", (50.3, 5.6, 49.3, 6.6)),),
        lang="fr", places_default=RAW / "lu", code_label="commune code",
        loader=_generic("LU"),
    ),
    "RS": Country(
        code="RS", name="Serbia",
        boxes=(Box("Serbia", (46.3, 18.7, 41.7, 23.1)),),
        lang="en", places_default=RAW / "rs", code_label="municipality code",
        excluded="Kosovo municipalities (codes 90xxx) are not included.",
        loader=_generic("RS"),
    ),
    "DE": Country(
        code="DE", name="Germany",
        boxes=(Box("Germany", (55.1, 5.8, 47.2, 15.1)),),
        lang="de", places_default=RAW / "de", code_label="AGS municipality code",
        loader=_generic("DE"),
    ),
    "GB": Country(
        code="GB", name="United Kingdom",
        boxes=(Box("Great Britain", (60.9, -8.7, 49.8, 1.8)),),
        lang="en", places_default=RAW / "gb", code_label="ONS built-up area code (BUA22CD)",
        excluded="Northern Ireland is not included (ONS built-up areas 2022 cover "
                 "England, Wales and Scotland only).",
        loader=_generic("GB"),
    ),
}


def get(cc: str) -> Country:
    cc = cc.upper()
    if cc not in COUNTRIES:
        raise ValueError(f"unknown country {cc!r} (have {sorted(COUNTRIES)})")
    return COUNTRIES[cc]
