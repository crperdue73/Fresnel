"""Tests for the Fresnel validator.

The validator is the product. If it lets a broken catalogue through,
the promise on the front page is a lie, so it gets tested and CI runs it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build  # noqa: E402


def base(**overrides):
    doc = {
        "title": "Test",
        "categories": [
            {
                "name": "Infra",
                "services": [
                    {"name": "Git", "url": "https://git.lan"},
                    {"name": "Logs", "url": "https://logs.lan"},
                ],
            }
        ],
    }
    doc.update(overrides)
    return doc


class Validate(unittest.TestCase):
    def test_minimal_config_passes(self):
        data = build.validate(base())
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["accent"], "#f2a65a")

    def test_missing_url_names_the_service(self):
        doc = base()
        doc["categories"][0]["services"].append({"name": "Broken", "description": "x"})
        with self.assertRaises(build.ConfigError) as ctx:
            build.validate(doc)
        self.assertIn("Broken", str(ctx.exception))
        self.assertIn("url", str(ctx.exception))

    def test_duplicate_url_rejected(self):
        doc = base()
        doc["categories"][0]["services"].append({"name": "Dup", "url": "https://git.lan"})
        with self.assertRaises(build.ConfigError):
            build.validate(doc)

    def test_duplicate_service_name_rejected(self):
        doc = base()
        doc["categories"][0]["services"].append({"name": "Git", "url": "https://other.lan"})
        with self.assertRaises(build.ConfigError):
            build.validate(doc)

    def test_bad_theme_rejected(self):
        with self.assertRaises(build.ConfigError):
            build.validate(base(theme="sepia"))

    def test_bad_accent_rejected(self):
        with self.assertRaises(build.ConfigError):
            build.validate(base(accent="orange"))

    def test_pinned_unknown_service_rejected(self):
        with self.assertRaises(build.ConfigError) as ctx:
            build.validate(base(pinned=["Ghost"]))
        self.assertIn("Ghost", str(ctx.exception))

    def test_pinned_resolves_in_order(self):
        data = build.validate(base(pinned=["Logs", "Git"]))
        self.assertEqual([s["name"] for s in data["pinned"]], ["Logs", "Git"])

    def test_category_accent_kept(self):
        doc = base()
        doc["categories"][0]["accent"] = "#5aa7f2"
        data = build.validate(doc)
        self.assertEqual(data["categories"][0]["accent"], "#5aa7f2")

    def test_hue_is_stable_across_builds(self):
        first = build.validate(base())["categories"][0]["services"][0]["hue"]
        second = build.validate(base())["categories"][0]["services"][0]["hue"]
        self.assertEqual(first, second)

    def test_bad_status_rejected(self):
        doc = base()
        doc["categories"][0]["services"][0]["status"] = "on-fire"
        with self.assertRaises(build.ConfigError):
            build.validate(doc)


if __name__ == "__main__":
    unittest.main()
