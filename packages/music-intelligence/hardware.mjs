import os from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile);
export async function hardwareStatus(){
 const result={cpu:os.cpus()[0]?.model,ramBytes:os.totalmem(),freeRamBytes:os.freemem(),platform:process.platform,gpu:null,wsl:null};
 try{const r=await execute('nvidia-smi',['--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],{windowsHide:true,timeout:4000,maxBuffer:65536});const [name,memory,driver]=r.stdout.trim().split(',').map(v=>v.trim());result.gpu={name,memoryMiB:Number.parseInt(memory),driver};}catch{result.gpu=null;}
 if(process.platform==='win32')try{const r=await execute('wsl',['--list','--quiet'],{windowsHide:true,timeout:4000,maxBuffer:65536,encoding:'buffer'});result.wsl=r.stdout.toString('utf16le').split(/\r?\n/).filter(Boolean);}catch{result.wsl=null;}
 return result;
}
export function modelSupport(id,hardware){
 if(id==='omar-rq')return hardware.ramBytes>=16*1024**3?'SUPPORTED':'CONDITIONAL';
 if(id==='sheetsage2')return 'CONDITIONAL';
 if(id==='yue2')return 'CONDITIONAL';
 return 'UNKNOWN';
}
