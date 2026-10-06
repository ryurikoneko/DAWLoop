# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""验证公开部署产物；不会启动FL或安装Controller。"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(args, check=True, timeout=180, **kwargs)


def main():
    from dawloop.provenance import build_manifest, verify_manifest

    manifest = build_manifest(ROOT)
    assert verify_manifest(ROOT, manifest)['content_matches']
    fixture = ROOT / 'tests/native_fixtures/practical_16_note/rendered_source.py'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == (
        '7b7b6989b579350abfa7d50890c33e4f5bc4a9514c07b5132ff6b7afae048f3a')
    with tempfile.TemporaryDirectory(prefix='dawloop-ci-') as directory:
        private = Path(directory)
        run(sys.executable, str(ROOT / 'learning/examples/generic_learning/run.py'),
            '--output', str(private / 'learning'), cwd=ROOT)
        expected = ROOT / 'learning/examples/generic_learning/expected'
        assert len(list(expected.glob('*.json'))) == 7, 'LEARNING_FIXTURES_REQUIRED'
        for path in sorted(expected.glob('*.json')):
            assert json.loads(path.read_text(encoding='utf-8')) == json.loads(
                (private / 'learning' / path.name).read_text(encoding='utf-8')), path.name
        # 独立环境没有源码路径，避免editable安装掩盖wheel漏包。
        environment = private / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        wheels = list((ROOT / 'dist').glob('*.whl'))
        assert len(wheels) == 1, 'EXACTLY_ONE_WHEEL_REQUIRED'
        run(str(python), '-I', '-m', 'pip', 'install', '--no-deps', str(wheels[0]), cwd=private)
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        probe = '''
import importlib.metadata as metadata
import importlib.resources as resources
import json, sys
from pathlib import Path
import dawloop
assert dawloop.__version__ == sys.argv[1]
assert Path(dawloop.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
schemas = resources.files('dawloop.learning.schemas')
assert len(list(schemas.glob('*.json'))) == 4
for item in schemas.glob('*.json'):
    assert json.loads(item.read_text(encoding='utf-8'))['$schema']
assert resources.files('dawloop.adapters.gopher_native').joinpath('bridge.js').is_file()
assert resources.files('dawloop.runtime').joinpath('fixtures/reviewed_accept_four_note.npz').is_file()
package = metadata.metadata('dawloop')
assert package.get_all('Project-URL') and 'Development Status :: 3 - Alpha' in package.get_all('Classifier')
print('ISOLATED_WHEEL_PASS')
'''
        run(str(python), '-I', '-c', probe, version, cwd=private)
    print(json.dumps({'offline_validation': 'PASS', 'live_certification': 'NOT_RUN'}))


if __name__ == '__main__':
    main()
