import sys,zipfile,hashlib
from pathlib import Path
archive,pip,target=map(Path,sys.argv[1:])
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b'
assert hashlib.sha256(pip.read_bytes()).hexdigest()=='71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e'
target.mkdir(exist_ok=False,parents=True)
for source,dest in [(archive,target),(pip,target/'Lib/site-packages')]:
    with zipfile.ZipFile(source) as z:
        for name in z.namelist():
            p=(dest/name).resolve();assert p.is_relative_to(dest.resolve())
        z.extractall(dest)
(target/'python311._pth').write_bytes(b'python311.zip\n.\nLib/site-packages\nimport site\n')
