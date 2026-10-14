import sys,zipfile,hashlib
from pathlib import Path
pip=Path(sys.argv[1]);target=Path(sys.executable).resolve().parent
assert hashlib.sha256(pip.read_bytes()).hexdigest()=='71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e','MI_MODEL_HASH_REJECTED'
dest=target/'Lib/site-packages'
with zipfile.ZipFile(pip) as z:
    for name in z.namelist():
        assert (dest/name).resolve().is_relative_to(dest.resolve()),'MI_ARCHIVE_PATH_REJECTED'
    z.extractall(dest)
(target/'python311._pth').write_bytes(b'python311.zip\n.\nLib/site-packages\nimport site\n')
