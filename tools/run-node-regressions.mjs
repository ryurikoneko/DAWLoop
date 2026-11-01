import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const desktop=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../apps/desktop');
if(path.resolve(os.tmpdir()).startsWith(path.resolve(desktop,'../../..')+path.sep))throw new Error('TEST_TEMP_INSIDE_EVIDENCE_REJECTED');
const root=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-node-regression-'));
const guard=new URL('./test-output-guard.mjs',import.meta.url).href;
const options=`--permission --allow-fs-read=* --allow-fs-write="${root.replaceAll('\\','/')}" --allow-child-process --allow-worker --allow-addons --import="${guard}"`;
const env={...process.env,DAWLOOP_TEST_OUTPUT_ROOT:root,TMP:root,TEMP:root,TMPDIR:root,NODE_OPTIONS:options};
async function run(args){return await new Promise(resolve=>{const child=spawn(process.execPath,args,{cwd:desktop,env,stdio:'inherit',windowsHide:true});child.once('error',()=>resolve(1));child.once('exit',code=>resolve(code??1));});}
try {
  const node=await run(['--test','../../tests/desktop/*.test.mjs']);
  const ui=node===0?await run(['node_modules/vitest/vitest.mjs','run','--configLoader','runner']):null;
  process.exitCode=node||ui||0;
} finally {
  // root 由本次 mkdtemp 返回；不接受调用方指定清理目标。
  await fs.rm(root,{recursive:true,force:true});
  console.log(JSON.stringify({temporaryRoot:root,cleanup:'REMOVED_THIS_RUN_ONLY'}));
}
