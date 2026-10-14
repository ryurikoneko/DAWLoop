"""从固定官方原件重建基础组件，拒绝混入测试环境的额外字节。"""
import argparse,hashlib,json,re,zipfile
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--recipe',type=Path,required=True)
p.add_argument('--recipe-sha256',required=True)
p.add_argument('--cache',type=Path,required=True)
p.add_argument('--environment',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--native-dir',type=Path)
a=p.parse_args();sha=lambda b:hashlib.sha256(b).hexdigest()
recipe_bytes=a.recipe.read_bytes();assert sha(recipe_bytes)==a.recipe_sha256,'RECIPE_HASH_REJECTED'
recipe=json.loads(recipe_bytes);expected={};licenses=[]
for source in recipe['artifacts']:
 original=(a.cache/source['file']).read_bytes();assert sha(original)==source['sha256'],'SOURCE_HASH_REJECTED'
 base='' if source['kind']=='python' else 'Lib/site-packages/'
 with zipfile.ZipFile(a.cache/source['file']) as z:
  for info in z.infolist():
   name=info.filename
   if info.is_dir() or '.data/scripts/' in name:continue
   assert not name.startswith('/') and not any(v in ['..','.'] or ':' in v or '\\' in v for v in name.split('/'))
   assert (info.external_attr>>16&0xf000)!=0xa000
   if '.data/' in name:
    assert '.data/purelib/' in name or '.data/platlib/' in name
    name=re.split(r'\.data/(?:purelib|platlib)/',name,1)[1]
   raw=z.read(info);name=base+name
   assert name not in expected or expected[name]==raw,'SOURCE_COLLISION'
   expected[name]=raw
 if source['kind']=='wheel':licenses.append(source['licenseRecord'])
expected['python314._pth']=b'python314.zip\r\n.\r\nLib/site-packages\r\nimport site\r\n'
for replacement in recipe.get('nativeOverrides',[]):
 assert a.native_dir and replacement['path'] in expected,'NATIVE_OVERRIDE_NOT_AUTHORIZED'
 raw=(a.native_dir/replacement['file']).read_bytes()
 assert sha(raw)==replacement['sha256'],'NATIVE_OVERRIDE_HASH_REJECTED'
 expected[replacement['path']]=raw
actual={f.relative_to(a.environment).as_posix():f for f in a.environment.rglob('*') if f.is_file()}
assert set(actual)==set(expected),'EXTRA_OR_MISSING_SOURCE_FILE'
rows=[]
for name,raw in sorted(expected.items()):
 assert not actual[name].is_symlink() and actual[name].read_bytes()==raw,name
 rows.append({'path':name,'sha256':sha(raw),'bytes':len(raw)})
manifest={'schemaVersion':1,'componentId':'basic-audio','version':recipe.get('componentVersion','1.1.0-internal.1'),'platform':'win32','arch':'x64','pythonVersion':'3.14.8','pythonPath':'python.exe','providerVersion':'0.10.2.post1','files':rows,'installedBytes':sum(r['bytes'] for r in rows),'licenses':licenses,'pythonLicense':'LICENSE.txt','modelsIncluded':False,'sourceKind':'VERIFIED_OFFICIAL_WHEELS','sourceManifestSha256':sha(recipe_bytes),'pythonSource':recipe['artifacts'][0],'nativeOverrides':recipe.get('nativeOverrides',[]),'publicRedistributionReview':recipe.get('publicRedistributionReview','PENDING_NATIVE_OBLIGATIONS')}
raw_manifest=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for name,raw in sorted(expected.items()):
  entry=zipfile.ZipInfo(name,(2026,10,14,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,raw)
 entry=zipfile.ZipInfo('component.json',(2026,10,14,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,raw_manifest)
result={'version':manifest['version'],'sha256':sha(a.output.read_bytes()),'manifestSha256':sha(raw_manifest),'archiveBytes':a.output.stat().st_size,'installedBytes':manifest['installedBytes']+len(raw_manifest),'fileCount':len(rows),'fileName':a.output.name}
a.output.with_suffix('.audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
