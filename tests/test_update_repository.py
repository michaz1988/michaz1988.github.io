import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import update_repository


def create_addon(root, addon_id="plugin.video.test", version="1.0.0"):
    addon = root / addon_id
    addon.mkdir(parents=True)
    (addon / "addon.xml").write_text(
        '<?xml version="1.0"?>\n'
        '<addon id="%s" name="Test" version="%s">'
        '<extension point="xbmc.addon.metadata">'
        '<assets><icon>resources/icon.png</icon></assets>'
        '</extension></addon>\n' % (addon_id, version),
        encoding="utf-8",
    )
    (addon / "default.py").write_text("VALUE = 1\n", encoding="utf-8")
    resources = addon / "resources"
    resources.mkdir()
    (resources / "icon.png").write_bytes(b"icon")
    return addon


class RepositoryGeneratorTests(unittest.TestCase):
    def test_archives_are_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_addon(root)
            first = root / "first.zip"
            second = root / "second.zip"
            update_repository.create_zip(addon, addon.name, first)
            update_repository.create_zip(addon, addon.name, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_same_version_with_changed_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_addon(root / "sources")
            repository = root / "site" / "repo"
            repository.mkdir(parents=True)
            update_repository.build_addon(
                addon, addon / "addon.xml", repository
            )
            (addon / "default.py").write_text("VALUE = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Versionsnummer erhöhen"):
                update_repository.build_addon(
                    addon, addon / "addon.xml", repository
                )

    def test_obsolete_assets_and_addons_are_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_addon(root / "sources")
            repository = root / "site" / "repo"
            destination = repository / addon.name
            destination.mkdir(parents=True)
            (destination / "obsolete.jpg").write_bytes(b"old")
            stale = repository / "plugin.video.removed"
            stale.mkdir()
            (stale / "addon.xml").write_text("<addon/>", encoding="utf-8")

            update_repository.build_addon(
                addon, addon / "addon.xml", repository
            )
            update_repository.prune_removed_addons(repository, {addon.name})

            self.assertFalse((destination / "obsolete.jpg").exists())
            self.assertFalse(stale.exists())
            self.assertTrue((destination / "resources" / "icon.png").exists())

    def test_unsafe_asset_path_is_rejected(self):
        with self.assertRaises(ValueError):
            update_repository.safe_relative_path("../outside.png")

    def test_two_newest_numeric_versions_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for version in ("2026.08.18", "2026.08.18.3", "2026.08.18.4"):
                (directory / ("plugin.video.test-%s.zip" % version)).touch()
            update_repository.keep_latest_zips(
                directory, "plugin.video.test", "2026.08.18.4"
            )
            self.assertEqual(
                sorted(path.name for path in directory.glob("*.zip")),
                [
                    "plugin.video.test-2026.08.18.3.zip",
                    "plugin.video.test-2026.08.18.4.zip",
                ],
            )


if __name__ == "__main__":
    unittest.main()
