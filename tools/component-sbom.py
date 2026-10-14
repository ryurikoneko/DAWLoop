"""只读组件资产盘点；许可证声明与完整再分发资格分别记录。"""
import argparse,csv,hashlib,io,json,posixpath,zipfile
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('archive',type=Path)
parser.add_argument('--expected-sha256',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
digest=lambda b:hashlib.sha256(b).hexdigest()
assert digest(args.archive.read_bytes())==args.expected_sha256,'ARCHIVE_HASH_REJECTED'
with zipfile.ZipFile(args.archive) as z:
 manifest=json.loads(z.read('component.json'))
 expected={r['path']:r for r in manifest['files']}
 assert set(z.namelist())==set(expected)|{'component.json'} and len(z.namelist())==len(expected)+1
 owners={};records={};license_files={}
 for name in expected:
  if name.endswith('.dist-info/RECORD'):
   prefix=name.rsplit('/',1)[0];metadata=z.read(prefix+'/METADATA').decode('utf-8')
   package=next(l[6:] for l in metadata.splitlines() if l.startswith('Name: ')).lower().replace('_','-')
   records[package]=prefix
   for row in csv.reader(io.StringIO(z.read(name).decode('utf-8'))):
    owners.setdefault(posixpath.normpath('Lib/site-packages/'+row[0]),[]).append(package)
 files=[];unmapped=[]
 for name,row in expected.items():
  b=z.read(name);assert digest(b)==row['sha256'] and len(b)==row['bytes'],name
  owner=owners.get(name,['cpython'] if not name.startswith('Lib/site-packages/') else [])
  if not owner:unmapped.append(name)
  native=Path(name).suffix.lower() in {'.exe','.dll','.pyd'}
  files.append({'path':name,'sha256':row['sha256'],'bytes':row['bytes'],'owners':owner,'native':native,'licenseConcluded':'NOASSERTION','redistributionReview':'PENDING_NATIVE_REVIEW' if native else 'DECLARED_LICENSE_REVIEW_REQUIRED'})
  if any(t in Path(name).name.lower() for t in ['license','copying','notice']):license_files[name]={'sha256':row['sha256'],'owners':owner,'text':b.decode('utf-8',errors='replace')}
 packages=[]
 for a in manifest['licenses']:
  package=a['name'];texts=[n for n,v in license_files.items() if package in v['owners']]
  packages.append({'name':package,'version':a['version'],'declaredLicense':a.get('licenseExpression'),'metadataLicense':a.get('licenseMetadata'),'classifiers':a.get('licenseClassifiers'),'source':a['officialArtifact'],'licenseTexts':texts,'copyright':'SEE_ORIGINAL_LICENSE_TEXT','sourceObligation':'REVIEW_REQUIRED' if 'LGPL' in str(a) or 'MPL' in str(a) else 'NOTICE_PRESERVATION_AND_BUNDLED_LIBRARY_REVIEW','publicPackageAllowed':False})
 result={'schemaVersion':1,'component':manifest['componentId'],'version':manifest['version'],'pythonVersion':manifest['pythonVersion'],'archiveSha256':args.expected_sha256,'packages':packages,'files':files,'licenseTexts':license_files,'unmappedFiles':unmapped,'publicRedistribution':'BLOCKED_UNTIL_ITEM_REVIEWS_CLOSED','scope':'Declared upstream license is not a conclusion covering all bundled native subcomponents'}
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with args.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps({'files':len(files),'nativeFiles':sum(f['native'] for f in files),'packages':len(packages),'licenses':len(license_files),'unmapped':len(unmapped)}))
