import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


provenance = module(ROOT / 'scripts/firmware_provenance.py')
installer = module(ROOT / '.github/scripts/install-firmware-tree.py')


class ProvenanceTest(unittest.TestCase):
    def test_publication_rejects_source_changes_but_allows_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', '-C', tmp, '-c', 'user.name=Test',
                    '-c', 'user.email=test@example.invalid', *args], stderr=subprocess.PIPE).decode().strip()
            git('init')
            (root / 'config').mkdir()
            (root / 'config/a').write_text('source')
            git('add', '.')
            git('commit', '-m', 'source')
            source = git('rev-parse', 'HEAD')
            (root / 'firmware').mkdir()
            (root / 'firmware/a.uf2').write_text('binary')
            git('add', '.')
            git('commit', '-m', 'artifact')
            provenance.verify_publish(source, 'HEAD', root)
            (root / 'config/a').write_text('changed')
            self.assertTrue(provenance.git_state(root)['dirty'])
            git('add', '.')
            git('commit', '-m', 'change')
            with self.assertRaises(ValueError):
                provenance.verify_publish(source, 'HEAD', root)

    def test_sidecar_required_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'a.uf2'
            binary.write_bytes(b'firmware')
            with self.assertRaises(ValueError):
                installer.validate_staging(root, 1, True)
            sidecar = root / 'a.uf2.json'
            sidecar.write_text(json.dumps({'schema': 1, 'artifact': {
                'name': binary.name, 'sha256': hashlib.sha256(b'firmware').hexdigest()}}))
            self.assertEqual(len(installer.validate_staging(root, 1, True)), 2)
            binary.write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                installer.validate_staging(root, 1, True)

    def test_orphan_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.uf2.json').write_text('{}')
            with self.assertRaises(ValueError):
                installer.validate_staging(root, 1)
