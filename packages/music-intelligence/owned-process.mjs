import {execFile} from 'node:child_process';
export function terminateOwnedProcess(child){
 if(!child||child.exitCode!==null||child.signalCode!==null||!Number.isSafeInteger(child.pid))return;
 // 安装器可能创建 ensurepip 子进程；只清理仍属于当前任务的进程树。
 if(process.platform==='win32')execFile('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,timeout:3000},()=>{});
 else child.kill();
}
