# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""正式tag必须来自main、匹配包版本，并通过明确的SSH签名信任表。"""

import argparse
from pathlib import Path
import re
import subprocess
import tomllib


def git(root, *arguments):
    result = subprocess.run(['git', '-C', str(root), *arguments], check=True,
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    return result.stdout.strip()


def verify_release(root, tag, *, main_ref='origin/main'):
    root = Path(root).resolve()
    match = re.fullmatch(r'v(\d+\.\d+\.\d+)-alpha\.(\d+)', tag)
    if not match:
        raise ValueError('RELEASE_TAG_FORMAT_INVALID')
    main_commit = git(root, 'rev-parse', main_ref + '^{commit}')
    if git(root, 'rev-parse', tag + '^{commit}') != main_commit:
        raise ValueError('RELEASE_TAG_MUST_POINT_TO_CURRENT_MAIN')
    if git(root, 'cat-file', '-t', tag) != 'tag':
        raise ValueError('RELEASE_ANNOTATED_SIGNED_TAG_REQUIRED')
    # 信任表来自main，不能接受待验证tag自己提供的任意签名者。
    allowed = git(root, 'show', main_ref + ':.github/release-signers.allowed')
    keys = [line for line in allowed.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if not keys:
        raise ValueError('TRUSTED_RELEASE_SIGNER_NOT_CONFIGURED')
    signers = root / '.github/release-signers.allowed'
    if signers.read_text(encoding='utf-8').strip() != allowed:
        raise ValueError('RELEASE_SIGNER_FILE_MISMATCH')
    git(root, '-c', 'gpg.format=ssh', '-c', 'gpg.ssh.allowedSignersFile=' + str(signers),
        'verify-tag', tag)
    metadata = tomllib.loads(git(root, 'show', tag + ':pyproject.toml'))
    if metadata['project']['version'] != match[1] + 'a' + match[2]:
        raise ValueError('RELEASE_PACKAGE_VERSION_MISMATCH')
    return main_commit


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(verify_release(args.root, args.tag))
