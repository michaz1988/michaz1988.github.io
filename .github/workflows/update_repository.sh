#!/usr/bin/env bash
set -euo pipefail

python3 - "$@" <<'PYTHON'
"""Build the Kodi repository website from unpacked add-on sources."""

import argparse
import hashlib
import html
import os
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET


IGNORED_NAMES = {
    '.DS_Store',
    '.git',
    '.gitattributes',
    '.github',
    '.gitignore',
    '__pycache__',
}


def natural_key(value):
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r'(\d+)', value)
        if part
    ]


def addon_sources(addons_path):
    for directory in sorted(addons_path.iterdir(), key=lambda item: item.name.lower()):
        manifest = directory / 'addon.xml'
        if directory.is_dir() and manifest.is_file():
            yield directory, manifest


def read_manifest(manifest_path):
    root = ET.parse(manifest_path).getroot()
    addon_id = root.get('id')
    version = root.get('version')
    if not addon_id or not version:
        raise ValueError('%s: id oder version fehlt' % manifest_path)
    return root, addon_id, version


def copy_if_changed(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and source.read_bytes() == destination.read_bytes():
        return False
    shutil.copy2(source, destination)
    return True


def asset_paths(root):
    paths = {'addon.xml'}
    for name in ('changelog.txt', 'icon.png', 'icon.jpg', 'fanart.png', 'fanart.jpg'):
        paths.add(name)
    for asset in root.findall('.//assets/*'):
        if asset.text:
            paths.add(asset.text.strip().replace('\\', '/'))
    return sorted(paths)


def safe_relative_path(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Ungültiger Asset-Pfad: %s' % value)
    return path


def package_files(addon_path):
    for root, directories, files in os.walk(addon_path):
        directories[:] = sorted(
            name for name in directories if name not in IGNORED_NAMES
        )
        for name in sorted(files):
            if name in IGNORED_NAMES or name.endswith(('.pyc', '.pyo')):
                continue
            yield Path(root) / name


def archive_entries(addon_path, addon_id):
    entries = {}
    for source in package_files(addon_path):
        relative = source.relative_to(addon_path).as_posix()
        entries['%s/%s' % (addon_id, relative)] = source.read_bytes()
    return entries


def archive_matches_source(archive_path, addon_path, addon_id):
    expected = archive_entries(addon_path, addon_id)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = {name for name in archive.namelist() if not name.endswith('/')}
            if names != set(expected):
                return False
            return all(archive.read(name) == content
                       for name, content in expected.items())
    except (OSError, zipfile.BadZipFile):
        return False


def create_zip(addon_path, addon_id, destination):
    temporary = destination.with_suffix(destination.suffix + '.tmp')
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(
            temporary, 'w', zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            for source in package_files(addon_path):
                relative = source.relative_to(addon_path).as_posix()
                info = zipfile.ZipInfo(
                    '%s/%s' % (addon_id, relative),
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def keep_latest_zips(directory, addon_id, current_version, count=2):
    archives = sorted(
        directory.glob('%s-*.zip' % addon_id),
        key=lambda path: natural_key(
            path.name[len(addon_id) + 1:-len('.zip')]
        ),
    )
    current = directory / ('%s-%s.zip' % (addon_id, current_version))
    if archives and archives[-1] != current:
        raise RuntimeError(
            '%s %s ist älter als die bereits veröffentlichte Version %s' % (
                addon_id,
                current_version,
                archives[-1].name[len(addon_id) + 1:-len('.zip')],
            )
        )
    for archive in archives[:-count]:
        archive.unlink()


def prune_addon_directory(directory, retained_files):
    retained = {Path(value) for value in retained_files}
    for path in sorted(directory.rglob('*'), reverse=True):
        if path.is_file() and path.relative_to(directory) not in retained:
            path.unlink()
    for path in sorted(
        (item for item in directory.rglob('*') if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if not any(path.iterdir()):
            path.rmdir()


def prune_removed_addons(repository_path, addon_ids):
    for directory in repository_path.iterdir():
        if directory.is_dir() and directory.name not in addon_ids:
            print('Entferne veraltetes Add-on %s' % directory.name)
            shutil.rmtree(directory)


def manifest_without_declaration(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if lines and lines[0].lstrip().startswith('<?xml'):
        lines.pop(0)
    return '\n'.join(lines).rstrip()


def build_addon(addon_path, manifest_path, repository_path):
    root, addon_id, version = read_manifest(manifest_path)
    if addon_path.name != addon_id:
        raise ValueError(
            '%s: Verzeichnisname und Add-on-ID stimmen nicht überein' % addon_path
        )
    destination = repository_path / addon_id
    destination.mkdir(parents=True, exist_ok=True)

    retained = set()
    for value in asset_paths(root):
        relative = safe_relative_path(value)
        source = addon_path / relative
        if source.is_file():
            copy_if_changed(source, destination / relative)
            retained.add(relative)

    archive = destination / ('%s-%s.zip' % (addon_id, version))
    if not archive.exists():
        print('Erstelle %s' % archive.name)
        create_zip(addon_path, addon_id, archive)
    else:
        if not archive_matches_source(archive, addon_path, addon_id):
            raise RuntimeError(
                '%s wurde bei unveränderter Version %s geändert; '
                'bitte die Versionsnummer erhöhen.' % (addon_id, version)
            )
        print('Vorhanden %s' % archive.name)
    keep_latest_zips(destination, addon_id, version)
    retained.update(path.relative_to(destination)
                    for path in destination.glob('%s-*.zip' % addon_id))
    prune_addon_directory(destination, retained)
    return addon_id, version, manifest_without_declaration(manifest_path)


def write_addons_xml(repository_path, manifests):
    content = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<addons>\n%s\n</addons>\n' % '\n\n'.join(manifests)
    ).encode('utf-8')
    destination = repository_path / 'addons.xml'
    if not destination.is_file() or destination.read_bytes() != content:
        destination.write_bytes(content)
    digest = hashlib.md5(content).hexdigest()
    checksum = repository_path / 'addons.xml.md5'
    if not checksum.is_file() or checksum.read_text(encoding='ascii') != digest:
        checksum.write_text(digest, encoding='ascii')


def format_size(size):
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return '%.2f %s' % (value, unit)
        value /= 1024


def write_index(directory, title):
    entries = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        if path.name in {'index.html', '.git'}:
            continue
        display = path.name + ('/' if path.is_dir() else '')
        size = '-' if path.is_dir() else format_size(path.stat().st_size)
        entries.append(
            '<tr><td><a href="%s">%s</a></td><td>%s</td></tr>' % (
                quote(display), html.escape(display), size
            )
        )
    document = '''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Index of {title}</title>
  <style>
    body {{ font: 16px sans-serif; margin: 2rem; color: #222; }}
    table {{ border-collapse: collapse; min-width: 32rem; }}
    td {{ border-bottom: 1px solid #ddd; padding: .45rem .8rem; }}
    td:last-child {{ text-align: right; color: #666; }}
  </style>
</head>
<body>
  <h1>Index of {title}</h1>
  <p><a href="../">../</a></p>
  <table>{rows}</table>
</body>
</html>
'''.format(title=html.escape(title), rows='\n'.join(entries))
    destination = directory / 'index.html'
    if not destination.is_file() or destination.read_text(encoding='utf-8') != document:
        destination.write_text(document, encoding='utf-8')


def write_indexes(root):
    if not root.is_dir():
        return
    directories = [Path(path) for path, names, _ in os.walk(root)
                   if '.git' not in Path(path).parts]
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        write_index(directory, '/' + directory.relative_to(root.parent).as_posix() + '/')


def create_test_addon(root, addon_id='plugin.video.test', version='1.0.0'):
    addon = root / addon_id
    addon.mkdir(parents=True)
    (addon / 'addon.xml').write_text(
        '<?xml version="1.0"?>\n'
        '<addon id="%s" name="Test" version="%s">'
        '<extension point="xbmc.addon.metadata">'
        '<assets><icon>resources/icon.png</icon></assets>'
        '</extension></addon>\n' % (addon_id, version),
        encoding='utf-8',
    )
    (addon / 'default.py').write_text('VALUE = 1\n', encoding='utf-8')
    resources = addon / 'resources'
    resources.mkdir()
    (resources / 'icon.png').write_bytes(b'icon')
    return addon


class RepositoryGeneratorTests(unittest.TestCase):
    def test_archives_are_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_test_addon(root)
            first = root / 'first.zip'
            second = root / 'second.zip'
            create_zip(addon, addon.name, first)
            create_zip(addon, addon.name, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_same_version_with_changed_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_test_addon(root / 'sources')
            repository = root / 'site' / 'repo'
            repository.mkdir(parents=True)
            build_addon(addon, addon / 'addon.xml', repository)
            (addon / 'default.py').write_text('VALUE = 2\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Versionsnummer erhöhen'):
                build_addon(addon, addon / 'addon.xml', repository)

    def test_obsolete_assets_and_addons_are_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addon = create_test_addon(root / 'sources')
            repository = root / 'site' / 'repo'
            destination = repository / addon.name
            destination.mkdir(parents=True)
            (destination / 'obsolete.jpg').write_bytes(b'old')
            stale = repository / 'plugin.video.removed'
            stale.mkdir()
            (stale / 'addon.xml').write_text('<addon/>', encoding='utf-8')

            build_addon(addon, addon / 'addon.xml', repository)
            prune_removed_addons(repository, {addon.name})

            self.assertFalse((destination / 'obsolete.jpg').exists())
            self.assertFalse(stale.exists())
            self.assertTrue((destination / 'resources' / 'icon.png').exists())

    def test_unsafe_asset_path_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_relative_path('../outside.png')

    def test_two_newest_numeric_versions_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for version in ('2026.08.18', '2026.08.18.3', '2026.08.18.4'):
                (directory / ('plugin.video.test-%s.zip' % version)).touch()
            keep_latest_zips(
                directory, 'plugin.video.test', '2026.08.18.4'
            )
            self.assertEqual(
                sorted(path.name for path in directory.glob('*.zip')),
                [
                    'plugin.video.test-2026.08.18.3.zip',
                    'plugin.video.test-2026.08.18.4.zip',
                ],
            )


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        RepositoryGeneratorTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--test', action='store_true', help='integrierte Tests ausführen'
    )
    parser.add_argument('--addons', type=Path)
    parser.add_argument('--site', type=Path)
    args = parser.parse_args(argv)
    if not args.test:
        missing = [
            option
            for option, value in (
                ('--addons', args.addons),
                ('--site', args.site),
            )
            if value is None
        ]
        if missing:
            parser.error('folgende Argumente fehlen: %s' % ', '.join(missing))
    return args


def main():
    args = parse_args()
    if args.test:
        return run_tests()
    addons_path = args.addons.resolve()
    site_path = args.site.resolve()
    repository_path = site_path / 'repo'
    repository_path.mkdir(parents=True, exist_ok=True)

    manifests = []
    count = 0
    for addon_path, manifest_path in addon_sources(addons_path):
        addon_id, version, manifest = build_addon(
            addon_path, manifest_path, repository_path
        )
        print('%s %s' % (addon_id, version))
        manifests.append(manifest)
        count += 1
    if not manifests:
        raise RuntimeError('Keine Add-ons mit addon.xml gefunden.')

    addon_ids = {
        ET.fromstring(manifest).get('id')
        for manifest in manifests
    }
    prune_removed_addons(repository_path, addon_ids)
    write_addons_xml(repository_path, manifests)
    write_indexes(repository_path)
    write_indexes(site_path / 'logos')
    print('%d Add-ons verarbeitet.' % count)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('Fehler: %s' % error, file=sys.stderr)
        raise
PYTHON
