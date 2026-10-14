import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export async function verifyPortable(directory) {
  const root=await fs.realpath(directory);const sha=raw=>createHash('sha256').update(raw).digest('hex');
  const manifest=JSON.parse(await fs.readFile(path.join(root,'portable-manifest.json'),'utf8'));
  if(manifest.schemaVersion!==1 || !Array.isArray(manifest.files) || manifest.files.length>10000)throw Error('PORTABLE_SCHEMA_REJECTED');
  const expected=new Set(['portable-manifest.json']);
  for(const row of manifest.files) {
    if(typeof row.path!=='string' || row.path.includes('\\') || row.path.split('/').some(part=>!part || part==='.' || part==='..') || path.isAbsolute(row.path) || !/^[a-f0-9]{64}$/.test(row.sha256) || expected.has(row.path))throw Error('PORTABLE_ENTRY_REJECTED');
    expected.add(row.path);const file=await fs.realpath(path.join(root,row.path));
    if(!file.startsWith(root+path.sep) || sha(await fs.readFile(file))!==row.sha256)throw Error('PORTABLE_BYTES_CHANGED');
  }
  async function walk(directory) {for(const entry of await fs.readdir(directory,{withFileTypes:true})) {
    const p=path.join(directory,entry.name);if(entry.isSymbolicLink())throw Error('PORTABLE_LINK_REJECTED');
    if(entry.isDirectory())await walk(p);else if(!expected.has(path.relative(root,p).replaceAll('\\','/')))throw Error('PORTABLE_EXTRA_FILE_REJECTED');
  }}
  await walk(root);
  for(const required of ['DAWLoop.exe','LICENSE','LICENSES.chromium.html','icudtl.dat','resources.pak','resources/app/package.json','resources/app/build-record.json','resources/app/apps/desktop/electron/main.mjs','resources/app/apps/desktop/electron/preload.cjs','resources/app/apps/desktop/dist/index.html','resources/app/node_modules/i18next/package.json'])if(!expected.has(required))throw Error('PORTABLE_REQUIRED_FILE_MISSING');
  const build=JSON.parse(await fs.readFile(path.join(root,'resources/app/build-record.json'),'utf8'));
  const alpha=build.releaseChannel==='preview'&&build.officialRelease===true&&/^\d+\.\d+\.\d+-alpha\.\d+$/.test(build.appVersion);
  if(!alpha && (build.releaseChannel!=='internal' || build.officialRelease!==false))throw Error('PORTABLE_SCOPE_REJECTED');
  const gate=JSON.parse(await fs.readFile(path.join(root,'resources/app/release_notification.json'),'utf8'));
  if(alpha && (build.sourceDirty||build.publicNotificationGate!=='DISABLED'||gate.notification_enabled!==false||gate.approved_by_owner!==false||gate.active_approval_id!==null||gate.approvals.length))throw Error('PORTABLE_PUBLIC_GATE_REJECTED');
  if(build.componentPack){
    const lock=JSON.parse(await fs.readFile(new URL('../packages/music-intelligence/basic-component.lock',import.meta.url),'utf8'));
    if(build.dependencies.python!=='offline-basic-component-pack'||build.componentPack.id!==lock.componentId||build.componentPack.version!==lock.version||build.componentPack.sha256!==lock.sha256||!expected.has('resources/components/'+lock.fileName))throw Error('PORTABLE_COMPONENT_SCOPE_REJECTED');
    if(sha(await fs.readFile(path.join(root,'resources/components',lock.fileName)))!==lock.sha256)throw Error('PORTABLE_COMPONENT_SCOPE_REJECTED');
  }else if(build.dependencies.python!=='not-bundled')throw Error('PORTABLE_SCOPE_REJECTED');
  if(build.optionalComponentPacks?.length){
    if(alpha||build.optionalComponentPacks.length!==1)throw Error('PORTABLE_COMPONENT_SCOPE_REJECTED');
    const lock=JSON.parse(await fs.readFile(new URL('../packages/music-intelligence/pitch-component.lock',import.meta.url),'utf8'));
    const pack=build.optionalComponentPacks[0];
    if(pack.id!==lock.componentId||pack.version!==lock.version||pack.sha256!==lock.sha256||!expected.has('resources/components/'+lock.fileName)||sha(await fs.readFile(path.join(root,'resources/components',lock.fileName)))!==lock.sha256)throw Error('PORTABLE_COMPONENT_SCOPE_REJECTED');
  }
  return {result:'PASS',files:manifest.files.length,appVersion:build.appVersion,manifestSha256:sha(await fs.readFile(path.join(root,'portable-manifest.json'))),sourceCommit:build.sourceCommit};
}
if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)console.log(JSON.stringify(await verifyPortable(process.argv[2])));
