#!/usr/bin/env python3
"""Fresnel build: services.yaml -> site/services.json

The dashboard page is read-only. This script is the only thing that
changes what it shows, and it refuses to emit a broken catalogue.

Usage:
    python3 tools/build.py            # build site/services.json
    python3 tools/build.py --check    # validate only, write nothing
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "services.yaml"
OUT = ROOT / "site" / "services.json"

ALLOWED_STATUS = {"new", "beta", "down", "planned"}
ALLOWED_PROVIDERS = {"duckduckgo", "google", "bing", "none"}
ALLOWED_THEMES = {"dark", "light"}


class ConfigError(Exception):
    pass


def hue_for(name: str) -> int:
    """Stable colour for a service, so the grid does not look random."""
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 360
    return h


def is_hex(value) -> bool:
    return isinstance(value, str) and value.startswith("#") and len(value) in (4, 7)


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def validate(doc: dict) -> dict:
    require(isinstance(doc, dict), "top level of the config must be a mapping")

    title = doc.get("title") or "Fresnel"
    require(isinstance(title, str) and title.strip(), "`title` must be a non-empty string")

    accent = doc.get("accent") or "#f2a65a"
    require(is_hex(accent), '`accent` must be a hex colour like "#f2a65a"')

    theme = (doc.get("theme") or "dark").lower()
    require(theme in ALLOWED_THEMES, f"`theme` must be one of {sorted(ALLOWED_THEMES)}")

    provider = (doc.get("search_provider") or "duckduckgo").lower()
    require(provider in ALLOWED_PROVIDERS,
            f"`search_provider` must be one of {sorted(ALLOWED_PROVIDERS)}")

    cats = doc.get("categories")
    require(isinstance(cats, list) and cats, "`categories` must be a non-empty list")

    seen_categories: set[str] = set()
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    out_categories = []

    for ci, cat in enumerate(cats):
        where = f"categories[{ci}]"
        require(isinstance(cat, dict), f"{where} must be a mapping")
        cname = cat.get("name")
        require(isinstance(cname, str) and cname.strip(), f"{where}.name must be a non-empty string")
        require(cname not in seen_categories, f"duplicate category name: {cname!r}")
        seen_categories.add(cname)

        cat_accent = cat.get("accent")
        if cat_accent is not None:
            require(is_hex(cat_accent),
                    f"category {cname!r}: `accent` must be a hex colour like \"#5aa7f2\"")

        services = cat.get("services")
        require(isinstance(services, list) and services,
                f"category {cname!r} must contain a non-empty `services` list")

        items = []
        for si, svc in enumerate(services):
            w = f"category {cname!r}, service {si + 1}"
            require(isinstance(svc, dict), f"{w} must be a mapping")
            require(
                isinstance(svc.get("name"), str) and svc["name"].strip(),
                f"{w}: `name` is required and must be a non-empty string",
            )
            name = svc["name"].strip()

            require(
                isinstance(svc.get("url"), str) and svc["url"].strip(),
                f"{w} ({name}): `url` is required and must be a non-empty string",
            )
            url = svc["url"].strip()
            require(url.startswith(("http://", "https://")),
                    f"{w} ({name}): `url` must start with http:// or https://")
            require(url not in seen_urls, f"{w} ({name}): duplicate url {url!r}")
            require(name not in seen_names, f"{w}: duplicate service name {name!r}")
            seen_urls.add(url)
            seen_names.add(name)

            status = svc.get("status")
            if status is not None:
                require(status in ALLOWED_STATUS,
                        f"{w} ({name}): `status` must be one of {sorted(ALLOWED_STATUS)}")

            tags = svc.get("tags") or []
            require(isinstance(tags, list) and all(isinstance(t, str) for t in tags),
                    f"{w} ({name}): `tags` must be a list of strings")

            hue = svc.get("hue")
            if hue is not None:
                require(isinstance(hue, int) and 0 <= hue <= 360,
                        f"{w} ({name}): `hue` must be an integer 0-360")

            monogram = svc.get("monogram")
            if monogram is not None:
                require(isinstance(monogram, str) and 1 <= len(monogram) <= 2,
                        f"{w} ({name}): `monogram` must be 1-2 characters")

            icon_host = svc.get("icon_host")
            if icon_host is not None:
                require(isinstance(icon_host, str) and "." in icon_host,
                        f"{w} ({name}): `icon_host` must be a hostname like \"git.lan\"")

            items.append({
                "name": name,
                "url": url,
                "description": (svc.get("description") or "").strip(),
                "icon": svc.get("icon"),
                "icon_host": icon_host or None,
                "monogram": monogram or name[0].upper(),
                "hue": hue if hue is not None else hue_for(name),
                "status": status,
                "tags": tags,
            })

        out_categories.append({
            "name": cname,
            "accent": cat_accent,
            "services": items,
        })

    # pinned: names, resolved across every category, in the order written
    pinned_raw = doc.get("pinned") or []
    require(isinstance(pinned_raw, list) and all(isinstance(p, str) for p in pinned_raw),
            "`pinned` must be a list of service names")
    require(len(set(pinned_raw)) == len(pinned_raw), "`pinned` lists the same service twice")

    pool = {s["name"]: s for c in out_categories for s in c["services"]}
    missing = [p for p in pinned_raw if p not in pool]
    require(not missing,
            f"`pinned` names services that do not exist: {', '.join(missing)}")

    return {
        "title": title.strip(),
        "subtitle": (doc.get("subtitle") or "").strip() or None,
        "accent": accent,
        "theme": theme,
        "search_provider": provider,
        "pinned": [pool[p] for p in pinned_raw],
        "categories": out_categories,
        "count": sum(len(c["services"]) for c in out_categories),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    check_only = "--check" in sys.argv[1:]

    if not CONFIG.exists():
        sys.exit(f"missing config: {CONFIG}")

    try:
        raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        data = validate(raw)
    except yaml.YAMLError as exc:
        sys.exit(f"{CONFIG.name}: YAML did not parse\n\n{exc}")
    except ConfigError as exc:
        sys.exit(f"{CONFIG.name}: {exc}")

    if check_only:
        print(f"ok: {data['count']} services in {len(data['categories'])} categories, "
              f"{len(data['pinned'])} pinned, theme {data['theme']}")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"built {OUT.relative_to(ROOT)}: {data['count']} services, "
          f"{len(data['categories'])} categories, {len(data['pinned'])} pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
