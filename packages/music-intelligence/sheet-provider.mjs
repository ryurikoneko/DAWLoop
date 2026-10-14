import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {fileDigest} from './model-download.mjs';
const directory=path.dirname(fileURLToPath(import.meta.url));
export async function verifyConfinedFiles(root,rows){
 const realRoot=await fs.realpath(root);
 for(const row of rows){const file=path.resolve(root,row.path??row.name),relative=path.relative(root,file);if(!relative||relative.startsWith('..')||path.isAbsolute(relative)||!(/^[a-f0-9]{64}$/).test(row.sha256))throw Error('MI_MODEL_HASH_REJECTED');const real=await fs.realpath(file);if(real!==file||!real.startsWith(realRoot+path.sep)||await fileDigest(file)!==row.sha256)throw Error('MI_MODEL_HASH_REJECTED');}
}
export async function sheetProvider(home){
 const lock=JSON.parse(await fs.readFile(path.join(directory,'sheetsage2-provider.lock'),'utf8'));
 const environment=path.join(home,lock.environment),manifest=path.join(home,lock.environmentManifest);
 if(await fileDigest(manifest)!==lock.environmentManifestSha256)throw Error('MI_MODEL_HASH_REJECTED');
 await verifyConfinedFiles(environment,JSON.parse(await fs.readFile(manifest,'utf8')));
 const models=[];
 for(const row of lock.models){const folder=path.join(home,row.directory);await verifyConfinedFiles(folder,row.files);models.push({...row,folder});}
 const target=path.join(home,'models','sheetsage2','verified-'+lock.models[0].revision+'.json');
 // 身份由应用固定合同决定；Worker 不从可编辑的历史报告取得版本资格。
 await fs.writeFile(target,JSON.stringify(models),{encoding:'utf8'});
 return {python:path.join(environment,'python.exe'),manifest:target,revision:lock.models[0].revision,bytes:lock.bytes};
}
