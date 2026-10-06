# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""来源清单不能把开发快照、摘要或未信任签名冒充官方发布。"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from dawloop.provenance import build_manifest, verify_manifest


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.git('config', 'user.name', 'Synthetic test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        (self.root / 'LICENSE').write_text('Synthetic MIT fixture\n', encoding='utf-8')
        self.git('add', 'LICENSE')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic baseline')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True, encoding='utf-8')

    def test_clean_snapshot_is_not_release_or_authorship(self):
        manifest = build_manifest(self.root)
        self.assertFalse(manifest['payload']['worktree_dirty'])
        self.assertEqual(manifest['payload']['build_kind'], 'DEVELOPMENT_SNAPSHOT')
        self.assertEqual(verify_manifest(self.root, manifest)['authenticity'], 'NOT_VERIFIED')
        self.assertTrue(verify_manifest(self.root, manifest)['content_matches'])

    def test_dirty_snapshot_and_private_content_not_included(self):
        (self.root / 'workspace').mkdir()
        (self.root / 'workspace/private.json').write_text('private', encoding='utf-8')
        manifest = build_manifest(self.root)
        self.assertTrue(manifest['payload']['worktree_dirty'])
        self.assertEqual(set(manifest['payload']['critical_source_hashes']), {'LICENSE'})
        with self.assertRaisesRegex(ValueError, 'RELEASE_REQUIRES_CLEAN'):
            build_manifest(self.root, release_tag='v0')

    def test_unsigned_tag_does_not_enable_release(self):
        self.git('tag', 'v0')
        with self.assertRaisesRegex(ValueError, 'GIT_CHECK_FAILED'):
            build_manifest(self.root, release_tag='v0')

    def test_manifest_and_content_tampering(self):
        manifest = build_manifest(self.root)
        changed = deepcopy(manifest)
        changed['payload']['git_commit'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'MANIFEST_HASH_MISMATCH'):
            verify_manifest(self.root, changed)
        (self.root / 'LICENSE').write_text('Modified\n', encoding='utf-8')
        self.assertEqual(verify_manifest(self.root, manifest)['mismatches'], ['LICENSE'])

    def test_self_consistent_malicious_paths_rejected(self):
        for path in ('../private.json', 'src/dawloop/../../private.json', 'C:/private.json',
                     'workspace/private.json', 'src\\dawloop\\file.py'):
            with self.subTest(path=path):
                manifest = build_manifest(self.root)
                manifest['payload']['critical_source_hashes'] = {path: '0' * 64}
                manifest['manifest_hash'] = hashlib.sha256(json.dumps(manifest['payload'], sort_keys=True,
                    ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
                with self.assertRaises(ValueError):
                    verify_manifest(self.root, manifest)


if __name__ == '__main__':
    unittest.main()
