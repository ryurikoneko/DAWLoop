# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""给CI构建的实际产物建立来源清单和摘要，不推断作者身份。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from dawloop.provenance import build_manifest, verify_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = build_manifest(root, release_tag=args.tag)
    assert verify_manifest(root, manifest)['content_matches']
    output = root / 'dist/release'
    output.mkdir(exist_ok=False)
    packages = [*root.glob('dist/*.whl'), *root.glob('dist/*.tar.gz')]
    if len(packages) != 2:
        raise ValueError('RELEASE_REQUIRES_WHEEL_AND_SDIST')
    for path in packages:
        shutil.copyfile(path, output / path.name)
    (output / 'source-provenance.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir())}
    (output / 'release-manifest.json').write_text(json.dumps({
        'git_commit': manifest['payload']['git_commit'], 'release_tag': args.tag,
        'kind': 'RELEASE_CANDIDATE' if args.tag is None else 'TRUSTED_SIGNED_TAG_BUILD',
        'assets': hashes, 'attestation': 'VERIFY_SEPARATELY_WITH_GITHUB_CLI',
    }, indent=2) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
        for path in sorted(output.iterdir())), encoding='utf-8')


if __name__ == '__main__':
    main()
