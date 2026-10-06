# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""公开文件内容清单；摘要一致不等于作者身份或签名已验证。"""

import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from dawloop import __version__


PROJECT_URL = 'https://github.com/ryurikoneko/DAWLoop'
PUBLIC_PATHS = ('src/dawloop', 'research', 'scripts', 'third_party', 'docs',
    'evidence/public', 'learning', 'profiles/examples', 'examples/music_plan',
    'LICENSES', 'MANIFEST.in', '.gitignore', '.gitattributes', 'SECURITY.md', 'AGENTS.md',
    'evidence/runtime_v2/file_snapshot_route.json',
    'LICENSE', 'NOTICE', 'AUTHORS', 'CITATION.cff', 'TRADEMARKS.md', 'LICENSE_POLICY.md',
    'README.md', 'README.en.md', '.github', 'requirements-ci.txt', 'CONTRIBUTING.md', 'pyproject.toml',
    'PROVENANCE.md', 'THIRD_PARTY_NOTICES.md')


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, encoding='utf-8', timeout=15)
    if result.returncode:
        raise ValueError('PROVENANCE_GIT_CHECK_FAILED')
    return result.stdout.strip()


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _research_hash(hashes):
    return _hash(_canonical({name: digest for name, digest in hashes.items()
                             if name.startswith(('docs/', 'evidence/'))}))


def _public_file(root, name):
    if type(name) is not str:
        raise ValueError('PROVENANCE_PATH_INVALID')
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or '\\' in name
            or ':' in name or path.as_posix() != name):
        raise ValueError('PROVENANCE_PATH_INVALID')
    candidate = root / name
    ancestors = [root.joinpath(*path.parts[:index]) for index in range(1, len(path.parts) + 1)]
    if any(parent.is_symlink() for parent in ancestors) or not candidate.resolve().is_relative_to(root):
        raise ValueError('PROVENANCE_PATH_ESCAPE')
    if not any(name == allowed or name.startswith(allowed + '/') for allowed in PUBLIC_PATHS):
        raise ValueError('PROVENANCE_PATH_NOT_PUBLIC')
    return candidate


def build_manifest(root, *, release_tag=None):
    root = Path(root).resolve()
    if Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise ValueError('PROVENANCE_EXACT_REPOSITORY_ROOT_REQUIRED')
    commit = _git(root, 'rev-parse', 'HEAD')
    dirty = bool(_git(root, 'status', '--porcelain', '--untracked-files=all'))
    if release_tag:
        if not isinstance(release_tag, str) or release_tag.startswith('-') or dirty:
            raise ValueError('RELEASE_REQUIRES_CLEAN_WORKTREE_AND_VALID_TAG')
        if _git(root, 'rev-parse', release_tag + '^{commit}') != commit:
            raise ValueError('RELEASE_TAG_COMMIT_MISMATCH')
        _git(root, 'verify-tag', release_tag)
    hashes = {}
    for allowed in PUBLIC_PATHS:
        base = root / allowed
        candidates = base.rglob('*') if base.is_dir() else (base,)
        for candidate in candidates:
            if '__pycache__' in candidate.parts or candidate.suffix in ('.pyc', '.pyo'):
                continue
            if candidate.is_file():
                name = candidate.relative_to(root).as_posix()
                checked = _public_file(root, name)
                hashes[name] = _hash(checked.read_bytes())
    payload = {'schema_version': 'dawloop-provenance-v1', 'project': 'DAWLoop',
        'upstream_url': PROJECT_URL, 'package_version': __version__, 'git_commit': commit,
        'worktree_dirty': dirty, 'release_tag': release_tag,
        'build_kind': 'SIGNED_TAG_SNAPSHOT' if release_tag else 'DEVELOPMENT_SNAPSHOT',
        'critical_source_hashes': dict(sorted(hashes.items())),
        'research_manifest_hash': _research_hash(hashes),
        'authenticity': 'NOT_VERIFIED_BY_THIS_MANIFEST'}
    return {'payload': payload, 'manifest_hash': _hash(_canonical(payload))}


def verify_manifest(root, manifest):
    if type(manifest) is not dict or set(manifest) != {'payload', 'manifest_hash'}:
        raise ValueError('PROVENANCE_MANIFEST_INVALID')
    payload = manifest['payload']
    required = {'schema_version', 'project', 'upstream_url', 'package_version', 'git_commit',
                'worktree_dirty', 'release_tag', 'build_kind', 'critical_source_hashes',
                'research_manifest_hash', 'authenticity'}
    if (type(payload) is not dict or set(payload) != required
            or payload.get('schema_version') != 'dawloop-provenance-v1'
            or type(payload.get('critical_source_hashes')) is not dict
            or not payload['critical_source_hashes']):
        raise ValueError('PROVENANCE_PAYLOAD_INVALID')
    if manifest['manifest_hash'] != _hash(_canonical(payload)):
        raise ValueError('PROVENANCE_MANIFEST_HASH_MISMATCH')
    research_hash = _research_hash(payload['critical_source_hashes'])
    if payload['research_manifest_hash'] != research_hash:
        raise ValueError('PROVENANCE_RESEARCH_HASH_MISMATCH')
    root = Path(root).resolve()
    mismatches = []
    for name, expected in payload['critical_source_hashes'].items():
        path = _public_file(root, name)
        if not path.is_file() or _hash(path.read_bytes()) != expected:
            mismatches.append(name)
    # 只核对列出的内容；未列文件和签名信任需要独立审查。
    return {'content_matches': not mismatches, 'mismatches': mismatches,
            'authenticity': 'NOT_VERIFIED', 'coverage': 'LISTED_FILES_ONLY'}


def run_provenance(args):
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        result = verify_manifest(args.root, manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['content_matches'] else 1
    manifest = build_manifest(args.root, release_tag=args.release_tag)
    if args.write_manifest:
        with args.write_manifest.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0
