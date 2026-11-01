import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { syncBuiltinESMExports } from 'node:module';

const root = process.env.DAWLOOP_TEST_OUTPUT_ROOT;
if (!root) throw new Error('TEST_OUTPUT_ROOT_REQUIRED');
const owned = fs.realpathSync(root);
const evidence=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
if(owned===evidence||owned.startsWith(evidence+path.sep))throw new Error('TEST_ROOT_INSIDE_EVIDENCE_REJECTED');
const originalRealpath = fs.realpathSync;
function resolved(value) {
  let current = value, suffix = [];
  while (!fs.existsSync(current)) { suffix.unshift(path.basename(current)); const parent=path.dirname(current);if(parent===current)throw new Error('TEST_OUTPUT_PATH_INVALID');current=parent; }
  return path.join(originalRealpath(current), ...suffix);
}
export function assertWritePath(value, followFinal=true) {
  if(typeof value==='number')return;
  const absolute=path.resolve(value instanceof URL?fileURLToPath(value):Buffer.isBuffer(value)?value.toString():value);
  const actual=followFinal?resolved(absolute):path.join(resolved(path.dirname(absolute)),path.basename(absolute));
  const relative=path.relative(owned,actual);
  if(relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw Object.assign(new Error('TEST_OUTPUT_OUTSIDE_OWNED_ROOT:'+absolute),{code:'TEST_OUTPUT_OUTSIDE_OWNED_ROOT'});
}
const writes=['writeFile','appendFile','mkdir','chmod','chown','utimes','truncate','mkdtemp'];
const removals=['unlink','rmdir','rm'];
const pairs=['rename','copyFile','cp','link'];
function wrap(object,name,check){const original=object[name];if(!original)return;object[name]=function(...args){check(args);return original.apply(this,args);};}
for(const object of [fs,fsp]) {
  for(const name of writes)wrap(object,name,args=>assertWritePath(args[0]));
  for(const name of removals)wrap(object,name,args=>assertWritePath(args[0],false));
  for(const name of pairs)wrap(object,name,args=>{if(name==='rename'||name==='link')assertWritePath(args[0],false);assertWritePath(args[1],false);});
  wrap(object,'symlink',args=>assertWritePath(args[1],false));
  wrap(object,'open',args=>{const flag=args[1];if(typeof flag==='number'?(flag&(fs.constants.O_WRONLY|fs.constants.O_RDWR|fs.constants.O_CREAT|fs.constants.O_TRUNC|fs.constants.O_APPEND)):flag&&/[wax+]/.test(flag))assertWritePath(args[0]);});
}
for(const name of writes)wrap(fs,name+'Sync',args=>assertWritePath(args[0]));
for(const name of removals)wrap(fs,name+'Sync',args=>assertWritePath(args[0],false));
for(const name of pairs)wrap(fs,name+'Sync',args=>{if(name==='rename'||name==='link')assertWritePath(args[0],false);assertWritePath(args[1],false);});
wrap(fs,'symlinkSync',args=>assertWritePath(args[1],false));
wrap(fs,'openSync',args=>{const flag=args[1];if(typeof flag==='number'?(flag&(fs.constants.O_WRONLY|fs.constants.O_RDWR|fs.constants.O_CREAT|fs.constants.O_TRUNC|fs.constants.O_APPEND)):flag&&/[wax+]/.test(flag))assertWritePath(args[0]);});
syncBuiltinESMExports();
