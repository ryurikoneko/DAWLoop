"""用已核验基础包和固定官方wheel生成独立ONNX组件，不读取活动模型环境。"""
import argparse,hashlib,json,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--sources',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(a.base.read_bytes())=='03f83f3bdf433dba538bc6ceffbf8a2a9e2b7842947ebdb8883a09347d658673'
with zipfile.ZipFile(a.base) as z:
 original_manifest=z.read('component.json');base=json.loads(original_manifest)
 expected={r['path']:z.read(r['path']) for r in base['files']}
 assert all(sha(expected[r['path']])==r['sha256'] for r in base['files'])
sources=json.loads(a.sources.read_text(encoding='utf-8'));excluded=[];licenses=[]
for row in sources:
 raw=(a.cache/row['file']).read_bytes();assert sha(raw)==row['sha256']
 with zipfile.ZipFile(a.cache/row['file']) as z:
  notices=[n for n in z.namelist() if any(v in n.lower() for v in ['license','copying','notice'])]
  licenses.append({'name':row['name'],'version':row['version'],'source':row,'licenseFiles':notices})
  for info in z.infolist():
   name=info.filename
   assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name and ':' not in name
   assert (info.external_attr>>16&0xf000)!=0xa000
   if info.is_dir():continue
   if '.data/scripts/' in name or name.endswith('.sf2'):
    excluded.append({'path':name,'sha256':sha(z.read(info)),'reason':'未使用的命令行入口或SoundFont，不用于ONNX转录'});continue
   assert '.data/' not in name
   target='Lib/site-packages/'+name;assert target not in expected
   expected[target]=z.read(info)
patches=[]
for name,old,new in [
 ('resampy/filters.py',b'import pkg_resources',b'import importlib.resources'),
 ('resampy/filters.py',b'pkg_resources.resource_filename(__name__, fname)',b'str(importlib.resources.files(__package__).joinpath(fname))'),
 ('audioread/__init__.py',b'    from . import rawread\n    result = [rawread.RawAudioFile]',b'    try:\n        from . import rawread\n        result = [rawread.RawAudioFile]\n    except ModuleNotFoundError as error:\n        if error.name not in ("aifc", "audioop", "sunau"):\n            raise\n        result = []')]:
 key='Lib/site-packages/'+name;before=expected[key];assert before.count(old)==1
 expected[key]=before.replace(old,new);patches.append({'path':key,'beforeSha256':sha(before),'afterSha256':sha(expected[key]),'old':old.decode(),'new':new.decode()})
rows=[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(expected.items())]
manifest={**base,'componentId':'basic-pitch','version':'1.0.0-alpha.2-r1','providerVersion':'0.4.0','runtime':'ONNX','modelsIncluded':True,'modelSha256':'2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec','files':rows,'installedBytes':sum(r['bytes'] for r in rows),'licenses':base['licenses']+licenses,'additionalSources':sources,'baseComponentSha256':sha(a.base.read_bytes()),'compatibilityPatches':patches,'excludedFiles':excluded,'publicRedistributionReview':'INTERNAL_CANDIDATE_ONLY_NATIVE_LICENSE_REVIEW_PENDING','dependencyVariant':'ONNX_ONLY_NO_TENSORFLOW'}
data=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
with zipfile.ZipFile(a.output,'x',compression=zipfile.ZIP_DEFLATED) as z:
 for n,b in [*sorted(expected.items()),('component.json',data)]:
  entry=zipfile.ZipInfo(n,(2026,10,14,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;z.writestr(entry,b)
lock={'schemaVersion':1,'componentId':'basic-pitch','version':manifest['version'],'platform':'win32','arch':'x64','fileName':a.output.name,'sha256':sha(a.output.read_bytes()),'manifestSha256':sha(data),'archiveBytes':a.output.stat().st_size,'installedBytes':manifest['installedBytes']+len(data),'fileCount':len(rows),'minimumFreeBytes':1073741824,'licenseAcknowledgement':'Apache-2.0','downloadUrl':None,'publicRedistributionReview':manifest['publicRedistributionReview'],'sourceKind':'VERIFIED_OFFICIAL_WHEELS'}
a.output.with_suffix('.lock').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8');print(json.dumps(lock))
