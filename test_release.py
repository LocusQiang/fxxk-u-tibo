"""Verify the distributable cannot pick up local state or extra files."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from package_release import ROOT, build, release_files


class ReleaseTests(unittest.TestCase):
    def test_zip_matches_allowlist_and_has_no_private_runtime_files(self):
        with tempfile.TemporaryDirectory(prefix='release-test-', dir=ROOT) as folder:
            result = build(destination=folder)
            archive = Path(result['archive'])
            with zipfile.ZipFile(archive) as package:
                self.assertIsNone(package.testzip())
                names = [name.split('/', 1)[1] for name in package.namelist()]
                self.assertEqual(set(names), {path.relative_to(ROOT).as_posix() for path in release_files()})
                for name in names:
                    self.assertNotIn('.runtime', Path(name).parts)
                    self.assertNotIn('.venv', Path(name).parts)
                    self.assertFalse(name.endswith(('.log', '.sqlite', '.jsonl', '.pid')))
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), result['sha256'])

    def test_asset_provenance_matches_distributed_files(self):
        provenance = json.loads((ROOT / 'assets/kitchen/PROVENANCE.json').read_text(encoding='utf-8'))
        self.assertEqual(len(provenance['assets']), 28)
        for asset in provenance['assets']:
            path = ROOT / 'assets/kitchen' / asset['file']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), asset['sha256'])


if __name__ == '__main__':
    unittest.main()
