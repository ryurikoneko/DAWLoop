import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const desktop=path.join(root,'apps/desktop');
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const output=process.argv[2];
const componentPack=process.argv[3];
const pitchPack=process.argv[4];
if(process.argv.length>5)throw Error('UNSUPPORTED_BUILD_ARGUMENT');
const componentLock=JSON.parse(await fs.readFile(path.join(root,'packages/music-intelligence/basic-component.lock'),'utf8'));
const pitchLock=JSON.parse(await fs.readFile(path.join(root,'packages/music-intelligence/pitch-component.lock'),'utf8'));
if(pitchPack&&(!path.isAbsolute(pitchPack)||sha(await fs.readFile(pitchPack))!==pitchLock.sha256))throw Error('COMPONENT_PACKAGE_HASH_REJECTED');
if(componentPack&&(!path.isAbsolute(componentPack)||sha(await fs.readFile(componentPack))!==componentLock.sha256))throw Error('COMPONENT_PACKAGE_HASH_REJECTED');
if(process.platform!=='win32' || process.arch!=='x64')throw Error('WINDOWS_X64_BUILD_REQUIRED');
if(!output || !path.isAbsolute(output))throw Error('NEW_ABSOLUTE_OUTPUT_REQUIRED');
const target=path.resolve(output);
if(target===root || target.startsWith(root+path.sep))throw Error('BUILD_INSIDE_SOURCE_REJECTED');
await fs.mkdir(target,{recursive:false});
async function files(directory) {
  const entries=await fs.readdir(directory,{withFileTypes:true}); const result=[];
  for(const e of entries.sort((a,b)=>a.name.localeCompare(b.name,'en'))) {
    const p=path.join(directory,e.name);
    if(e.isSymbolicLink())throw Error('BUILD_SYMLINK_REJECTED');
    if(e.isDirectory())result.push(...await files(p));else if(e.isFile())result.push(p);
  }
  return result;
}
const run=spawnSync(process.execPath,[path.join(desktop,'node_modules/typescript/bin/tsc'),'--noEmit'],{cwd:desktop,encoding:'utf8',windowsHide:true});
if(run.status!==0)throw Error('TYPECHECK_FAILED');
const vite=spawnSync(process.execPath,[path.join(desktop,'node_modules/vite/bin/vite.js'),'build'],{cwd:desktop,encoding:'utf8',windowsHide:true});
if(vite.status!==0)throw Error('RENDERER_BUILD_FAILED');
const manifest=JSON.parse(await fs.readFile(path.join(desktop,'package.json'),'utf8'));
const publicAlpha=manifest.dawloopInternalCandidate!==true && manifest.dawloopReleaseChannel==='preview' && /^\d+\.\d+\.\d+-alpha\.\d+$/.test(manifest.version);
if(pitchPack&&publicAlpha)throw Error('PITCH_PUBLIC_DISTRIBUTION_NOT_APPROVED');
const releaseChannel=publicAlpha?'preview':'internal';
const notificationGate=JSON.parse(await fs.readFile(path.join(root,'release_notification.json'),'utf8'));
if(publicAlpha && (notificationGate.notification_enabled!==false||notificationGate.approved_by_owner!==false||notificationGate.active_approval_id!==null||notificationGate.approvals.length))throw Error('PUBLIC_NOTIFICATION_GATE_MUST_BE_DISABLED');
if(publicAlpha && (!componentPack || componentLock.publicRedistributionReview!=='NOTICE_AND_SOURCE_OBLIGATIONS_REVIEWED'))throw Error('PUBLIC_COMPONENT_REVIEW_REQUIRED');
const lock=JSON.parse(await fs.readFile(path.join(desktop,'package-lock.json'),'utf8'));
const buildTools={node:process.version};
for(const name of ['typescript','vite']) {
  const installed=JSON.parse(await fs.readFile(path.join(desktop,'node_modules',name,'package.json'),'utf8'));
  if(installed.version!==lock.packages['node_modules/'+name]?.version)throw Error('BUILD_TOOL_LOCK_MISMATCH');
  buildTools[name]=installed.version;
}
const electron=path.join(desktop,'node_modules/electron/dist');
const electronVersion=(await fs.readFile(path.join(electron,'version'),'utf8')).trim();
if(electronVersion!==manifest.devDependencies.electron)throw Error('ELECTRON_VERSION_MISMATCH');
const recipeInputs={};
const included=[];
async function copy(source,relative,recipe=true) {
  const raw=await fs.readFile(source);const dest=path.join(target,relative);
  await fs.mkdir(path.dirname(dest),{recursive:true});await fs.writeFile(dest,raw,{flag:'wx'});
  included.push({path:relative.replaceAll('\\','/'),sha256:sha(raw),bytes:raw.length});
  if(recipe)recipeInputs[path.relative(root,source).replaceAll('\\','/')]=sha(raw);
}
for(const file of await files(electron)) {
  const rel=path.relative(electron,file);
  if(rel.startsWith('resources'+path.sep))continue;
  await copy(file,rel==='electron.exe'?'DAWLoop.exe':rel);
}
const iconSource=path.join(desktop,'public/brand/DAWLoop.ico');
const iconPython=process.env.DAWLOOP_BUILD_PYTHON;
if(!iconPython||!path.isAbsolute(iconPython))throw Error('EXPLICIT_BUILD_PYTHON_REQUIRED');
const originalExe=path.join(electron,'electron.exe');
const iconRun=spawnSync(iconPython,['-I','-B',path.join(root,'tools/windows-brand-icon.py'),path.join(target,'DAWLoop.exe'),iconSource,sha(await fs.readFile(originalExe))],{encoding:'utf8',windowsHide:true});
if(iconRun.status!==0)throw Error('ICON_RESOURCE_UPDATE_FAILED: '+iconRun.stderr.slice(-1000));
const iconRecord=JSON.parse(iconRun.stdout);
const app='resources/app';
if(componentPack)await copy(componentPack,path.join('resources/components',componentLock.fileName),false);
if(pitchPack)await copy(pitchPack,path.join('resources/components',pitchLock.fileName),false);
await copy(path.join(root,'release_notification.json'),path.join(app,'release_notification.json'));
for(const sub of ['electron','locales','dist'])for(const file of await files(path.join(desktop,sub)))await copy(file,path.join(app,'apps/desktop',sub,path.relative(path.join(desktop,sub),file)));
for(const file of await files(path.join(root,'packages')))if(/\.(mjs|cjs)$/.test(file)||path.relative(root,file).replaceAll('\\','/').startsWith('packages/music-intelligence/')&&/\.(py|ps1|lock)$/.test(file))await copy(file,path.join(app,'packages',path.relative(path.join(root,'packages'),file)));
// renderer 的依赖已打进资产；主进程只需要 i18next，不复制测试工具或开发环境。
const i18n=path.join(desktop,'node_modules/i18next');
const i18nManifest=JSON.parse(await fs.readFile(path.join(i18n,'package.json'),'utf8'));
if(i18nManifest.dependencies && Object.keys(i18nManifest.dependencies).length)throw Error('NEW_MAIN_DEPENDENCY_AUDIT_REQUIRED');
for(const file of await files(i18n))await copy(file,path.join(app,'node_modules/i18next',path.relative(i18n,file)));
for(const name of ['LICENSE','NOTICE'])await copy(path.join(root,name),path.join(app,name));
const licenses={};const remaining=Object.keys(manifest.dependencies);
while(remaining.length) {
  const name=remaining.shift();if(licenses[name])continue;
  const base=path.join(desktop,'node_modules',name);const packageInfo=JSON.parse(await fs.readFile(path.join(base,'package.json'),'utf8'));
  if(packageInfo.version!==lock.packages['node_modules/'+name]?.version)throw Error('RUNTIME_LOCK_MISMATCH');
  const license=(await fs.readdir(base)).find(n=>/^licen[cs]e(?:\.md|\.txt)?$/i.test(n));
  if(!license || packageInfo.license!=='MIT')throw Error('RUNTIME_LICENSE_AUDIT_REQUIRED');
  await copy(path.join(base,license),path.join('licenses',name.replaceAll('/','_')+'.txt'));
  licenses[name]={version:packageInfo.version,license:packageInfo.license};
  for(const f of await files(base))recipeInputs[path.relative(root,f).replaceAll('\\','/')]=sha(await fs.readFile(f));
  remaining.push(...Object.keys(packageInfo.dependencies??{}));
}
const sourceHead=spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8',windowsHide:true});
if(sourceHead.status!==0)throw Error('SOURCE_VERSION_REQUIRED');
const sourceStatus=spawnSync('git',['status','--porcelain'],{cwd:root,encoding:'utf8',windowsHide:true});
if(sourceStatus.status!==0)throw Error('SOURCE_STATUS_REQUIRED');
const version=publicAlpha?manifest.version:manifest.version+'-internal.1';
const distributionName='DAWLoop+'+version;
for(const [source,relative] of [['LICENSE','licenses/DAWLoop-MIT.txt'],['NOTICE','licenses/DAWLoop-NOTICE.txt'],['THIRD_PARTY_NOTICES.md','licenses/DAWLoop-THIRD-PARTY-NOTICES.md'],[manifest.dawloopReleaseChannel==='preview'?'docs/DESKTOP_ALPHA_BUILD.md':'docs/DESKTOP_DISTRIBUTION.zh.md','USER_GUIDE.zh.md'],[manifest.dawloopReleaseChannel==='preview'?'docs/DESKTOP_ALPHA_BUILD.md':'docs/DESKTOP_DISTRIBUTION.en.md','USER_GUIDE.en.md']])await copy(path.join(root,source),relative);
for(const file of await files(path.join(root,'LICENSES/desktop-runtime')))await copy(file,path.join('licenses/desktop-runtime',path.relative(path.join(root,'LICENSES/desktop-runtime'),file)));
if(pitchPack)for(const file of await files(path.join(root,'LICENSES/basic-pitch')))await copy(file,path.join('licenses/basic-pitch',path.relative(path.join(root,'LICENSES/basic-pitch'),file)));
await copy(path.join(root,'docs/DESKTOP_ALPHA_BUILD.md'),'FIRST_RUN_AND_SOURCE.md');
await fs.writeFile(path.join(target,app,'package.json'),JSON.stringify({name:'dawloop-desktop',version,productName:distributionName,dawloopReleaseChannel:releaseChannel,type:'module',main:'apps/desktop/electron/main.mjs'},null,2)+'\n',{encoding:'utf8',flag:'wx'});
for(const relative of ['tools/build-portable.mjs','tools/windows-brand-icon.py',...(await files(path.join(desktop,'public'))).map(f=>path.relative(root,f)),'apps/desktop/package.json','apps/desktop/package-lock.json','apps/desktop/index.html','apps/desktop/vite.config.ts','apps/desktop/tsconfig.json',... (await files(path.join(desktop,'src'))).map(f=>path.relative(root,f)),...(await files(path.join(root,'packages'))).filter(f=>f.endsWith('.ts')).map(f=>path.relative(root,f))])recipeInputs[relative.replaceAll('\\','/')]=sha(await fs.readFile(path.join(root,relative)));
if(publicAlpha && sourceStatus.stdout.trim())throw Error('CLEAN_PUBLIC_SOURCE_REQUIRED');
const record={schemaVersion:1,distributionName,releaseReadiness:publicAlpha?'EXPERIMENTAL_ALPHA_MAINTAINER_RISK_ACCEPTED':'INTERNAL_ONLY',cleanWindowsE2E:'NOT_TESTED',cleanWindowsRiskAcceptedByMaintainer:publicAlpha,publicNotificationGate:'DISABLED',branding:iconRecord,builtAt:new Date().toISOString(),releaseChannel,officialRelease:publicAlpha,platform:'win32',arch:'x64',appVersion:version,electronVersion,
  sourceCommit:sourceHead.stdout.trim(),sourceDirty:sourceStatus.stdout.trim().length>0,buildTools,recipeInputs,lockfileSha256:recipeInputs['apps/desktop/package-lock.json'],licenses,
  componentPack:componentPack?{id:componentLock.componentId,version:componentLock.version,sha256:componentLock.sha256,licenseReview:componentLock.publicRedistributionReview}:null,
  optionalComponentPacks:pitchPack?[{id:pitchLock.componentId,version:pitchLock.version,sha256:pitchLock.sha256,licenseReview:pitchLock.publicRedistributionReview}]:[],
  dependencies:{node:'included-in-electron',python:componentPack?'offline-basic-component-pack':'not-bundled',core:'desktop-only',controller:'user-installed-not-bundled',flStudio:'user-installed-not-bundled'},
  reproducibility:'逐文件内容摘要可重建；不承诺ZIP字节或完整环境一致',signed:false};
for(const [relative,expected] of Object.entries(recipeInputs))if(sha(await fs.readFile(path.join(root,relative)))!==expected)throw Error('PACKAGING_SOURCE_CHANGED');
await fs.writeFile(path.join(target,app,'build-record.json'),JSON.stringify(record,null,2)+'\n',{encoding:'utf8',flag:'wx'});
await fs.writeFile(path.join(target,publicAlpha?'ALPHA_README.txt':'INTERNAL_ONLY.txt'),(publicAlpha?"Experimental Alpha — Tested on maintainer's Windows environment. Clean Windows compatibility has not been independently verified.\nPUBLIC_NOTIFICATION_GATE = DISABLED\n":'INTERNAL TEST CANDIDATE - NOT A RELEASE\n')+'Run DAWLoop.exe. Node/npm are not required. '+(componentPack?'An offline basic component pack is included; review licenses and install it in the app. WAV analysis is supported; external codec analysis is not bundled.':'Python is not included.')+' FL/Controller are not included.\nSettings/logs use Windows user folders. No automatic Controller deployment.\n',{encoding:'utf8',flag:'wx'});
const inventory=[];for(const file of await files(target))inventory.push({path:path.relative(target,file).replaceAll('\\','/'),sha256:sha(await fs.readFile(file))});
await fs.writeFile(path.join(target,'portable-manifest.json'),JSON.stringify({schemaVersion:1,files:inventory},null,2)+'\n',{encoding:'utf8',flag:'wx'});
console.log(JSON.stringify({result:'PASS',version,files:inventory.length,output:target,releaseChannel}));
