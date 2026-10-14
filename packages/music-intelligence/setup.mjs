import fs from 'node:fs/promises';
import path from 'node:path';
import {hardwareStatus} from './hardware.mjs';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileDigest} from './model-download.mjs';
import {managedRuntime} from './managed-runtime.mjs';
import {fileURLToPath} from 'node:url';
const execute=promisify(execFile);
const GiB=1024**3;
export function capabilityMatrix(h,freeBytes){
 const windows=h.platform==='win32',ram=h.ramBytes??0,gpu=h.gpu?.memoryMiB;
 return [{id:'basic-pitch',license:'Apache-2.0',downloadBytes:null,minimumStorageBytes:5*GiB,qualification:windows&&ram>=8*GiB?'RECOMMENDED':windows?'CONDITIONAL':'UNKNOWN',reason:windows?'CPU_ONNX_QUALIFIED':'PLATFORM_NOT_QUALIFIED',installable:windows},
 {id:'omar-rq',license:'CC-BY-NC-SA-4.0',codeLicense:'AGPL-3.0',downloadBytes:2325316350,minimumStorageBytes:8*GiB,qualification:windows&&ram>=16*GiB?'RECOMMENDED':'CONDITIONAL',reason:'CPU_MEMORY_RECOMMENDATION',installable:windows},
 {id:'sheetsage2',license:'CC-BY-NC-4.0',downloadBytes:2758551412,minimumStorageBytes:8*GiB,qualification:windows&&ram>=16*GiB?'CONDITIONAL':'UNKNOWN',reason:'CPU_RUNTIME_TIMING_REVIEW_REQUIRED',installable:windows},
 {id:'yue2-plan',license:'CC-BY-NC-4.0',downloadBytes:7261441640,minimumStorageBytes:16*GiB,qualification:'UNKNOWN',reason:gpu!==undefined&&gpu<10000?'GPU_BUDGET_CPU_PLAN_UNQUALIFIED':'PLAN_RUNTIME_UNQUALIFIED',installable:false},
 {id:'yue2-audio',license:'CC-BY-NC-4.0',downloadBytes:null,minimumStorageBytes:30*GiB,qualification:windows&&gpu!==undefined&&gpu<24576?'UNSUPPORTED':'UNKNOWN',reason:'FULL_AUDIO_RECOMMENDED_ROUTE_UNQUALIFIED',installable:false}].map(row=>({...row,freeBytes,diskEligible:freeBytes>=row.minimumStorageBytes,qualification:freeBytes<row.minimumStorageBytes&&row.installable?'CONDITIONAL':row.qualification}));
}
export async function setupStatus(home){const hardware=await hardwareStatus(),disk=await fs.statfs(home);hardware.osRelease=(await import('node:os')).release();hardware.arch=process.arch;let preferences;try{preferences=JSON.parse(await fs.readFile(path.join(home,'ai-setup.json'),'utf8'));}catch{}const python=[];
 try{const runtime=JSON.parse(await fs.readFile(path.join(home,'runtime.json'),'utf8'));for(const key of ['python','omarPython','basePython'])if(runtime[key]){try{if(await fileDigest(runtime[key])!==runtime[key+'Sha256'])throw Error('MI_PYTHON_UNVERIFIED');const r=await execute(runtime[key],['-I','-B','-c','import sys;print(sys.version.split()[0])'],{windowsHide:true,timeout:3000,maxBuffer:4096});python.push({role:key,configured:true,version:r.stdout.trim(),verified:true});}catch{python.push({role:key,configured:true,verified:false});}}}catch{}hardware.python=python;
 const pitchPython=path.join(home,'environments/basic-pitch-v2/python.exe');try{if(await fs.realpath(pitchPython)!==pitchPython||await fileDigest(pitchPython)!=='5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec')throw Error('MI_PYTHON_UNVERIFIED');const r=await execute(pitchPython,['-I','-B','-c','import sys;print(sys.version.split()[0])'],{windowsHide:true,timeout:3000,maxBuffer:4096});python.push({role:'basicPitchPython',configured:true,verified:true,version:r.stdout.trim()});}catch{}
 if(!python.some(row=>row.role==='python')){const basic=await managedRuntime(home);if(basic.python){try{const r=await execute(basic.python,['-I','-B','-c','import sys;print(sys.version.split()[0])'],{windowsHide:true,timeout:3000,maxBuffer:4096});python.push({role:'python',configured:true,version:r.stdout.trim(),verified:true});}catch{python.push({role:'python',configured:true,verified:false});}}}
 const providers=capabilityMatrix(hardware,disk.bavail*disk.bsize);const budget=JSON.parse(await fs.readFile(path.join(path.dirname(fileURLToPath(import.meta.url)),'installation-budget.lock'),'utf8'));providers[0].downloadBytes=budget.basicPitch.downloadBytes;
 for(const row of providers){row.runtimeDownloadBytes=row.id==='basic-pitch'?budget.basicPitch.runtimeBytes:null;row.weightBytes=row.id==='basic-pitch'?budget.basicPitch.modelPackageBytes:row.downloadBytes;row.downloadingDependenciesKnown=row.id==='basic-pitch';}
 const omar=providers.find(r=>r.id==='omar-rq');if(!python.some(r=>r.role==='omarPython'&&r.verified)){omar.installable=false;omar.qualification='CONDITIONAL';omar.reason='INSTALL_BUDGET_UNQUALIFIED';}
 const sheet=providers.find(r=>r.id==='sheetsage2');try{await fs.access(path.join(home,'models/sheetsage2/environment-manifest-v3.json'));}catch{sheet.installable=false;sheet.reason='PREPARED_RUNTIME_REQUIRED';}
 return {schemaVersion:1,hardware,providers,completed:preferences?.completed===true,skipped:preferences?.skipped===true,offlineModelUploads:false};}
export async function saveSetup(home,skipped){if(typeof skipped!=='boolean')throw Error('MI_SETUP_REJECTED');await fs.writeFile(path.join(home,'ai-setup.json'),JSON.stringify({schemaVersion:1,completed:true,skipped,updatedAt:new Date().toISOString()}),{encoding:'utf8'});return true;}
