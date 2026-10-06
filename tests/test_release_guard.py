# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""签名发布不能把任意有效签名当成维护者身份。"""

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.release_guard import verify_release


class ReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic signer')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        (self.root / '.github').mkdir()
        (self.root / '.github/release-signers.allowed').write_text('# No trusted signer\n', encoding='utf-8')
        (self.root / 'pyproject.toml').write_text('[project]\nversion="0.2.0a2"\n', encoding='utf-8')
        self.commit()
        self.git('branch', 'trusted-main')

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.root), *arguments], check=True,
                              capture_output=True, text=True, encoding='utf-8', timeout=15).stdout.strip()

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic release fixture')

    def verify(self, tag='v0.2.0-alpha.2'):
        return verify_release(self.root, tag, main_ref='trusted-main')

    def test_invalid_tag_name(self):
        with self.assertRaisesRegex(ValueError, 'FORMAT_INVALID'):
            self.verify('--help')

    def test_lightweight_tag_rejected(self):
        self.git('tag', 'v0.2.0-alpha.2')
        with self.assertRaisesRegex(ValueError, 'SIGNED_TAG_REQUIRED'):
            self.verify()

    def test_missing_trusted_key_rejected(self):
        self.git('-c', 'tag.gpgsign=false', 'tag', '-a', 'v0.2.0-alpha.2', '-m', 'Unsigned')
        with self.assertRaisesRegex(ValueError, 'SIGNER_NOT_CONFIGURED'):
            self.verify()

    def test_branch_tag_rejected(self):
        (self.root / 'new.txt').write_text('Synthetic branch\n', encoding='utf-8')
        self.commit()
        self.git('tag', 'v0.2.0-alpha.2')
        with self.assertRaisesRegex(ValueError, 'CURRENT_MAIN'):
            self.verify()

    def test_signed_tag_requires_trusted_key_and_matching_version(self):
        key = self.root / 'synthetic-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       check=True, capture_output=True, timeout=15)
        public = key.with_suffix('.pub').read_text(encoding='utf-8').strip()
        self.git('config', 'gpg.format', 'ssh')
        self.git('config', 'user.signingkey', str(key))
        (self.root / '.github/release-signers.allowed').write_text(
            'synthetic@example.invalid namespaces="git" ' + public + '\n', encoding='utf-8')
        # 临时签名密钥不进入合成仓库提交，更不进入公开产物。
        self.git('add', '.github/release-signers.allowed')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic trusted signer')
        self.git('branch', '-f', 'trusted-main')
        self.git('tag', '-s', 'v0.2.0-alpha.2', '-m', 'Synthetic signed release')
        self.assertEqual(self.verify(), self.git('rev-parse', 'HEAD'))
        other = self.root / 'untrusted-key'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(other)],
                       check=True, capture_output=True, timeout=15)
        self.git('config', 'user.signingkey', str(other))
        self.git('tag', '-f', '-s', 'v0.2.0-alpha.2', '-m', 'Valid but untrusted signature')
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()
        self.git('config', 'user.signingkey', str(key))
        self.git('tag', '-f', '-s', 'v0.2.0-alpha.2', '-m', 'Synthetic trusted release')
        (self.root / '.github/release-signers.allowed').write_text('# Changed key\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SIGNER_FILE_MISMATCH'):
            self.verify()
        (self.root / '.github/release-signers.allowed').write_text(
            'synthetic@example.invalid namespaces="git" ' + public + '\n', encoding='utf-8')
        self.git('tag', '-s', 'v0.2.0-alpha.3', '-m', 'Wrong package version')
        with self.assertRaisesRegex(ValueError, 'VERSION_MISMATCH'):
            self.verify('v0.2.0-alpha.3')


if __name__ == '__main__':
    unittest.main()
