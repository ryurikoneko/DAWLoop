import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const require=createRequire(path.join(root,'apps/desktop/package.json'));
const ts=require('typescript');
test('组件仅允许品牌/版本静态 JSX，表单标签不得硬编码', async () => {
  const file=ts.createSourceFile('App.tsx',await fs.readFile(path.join(root,'apps/desktop/src/App.tsx'),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  const allowed=new Set(['D','DAWLoop','DAWLoop Runtime','FL Studio','Core API','v1']);
  function visit(node) {
    if(ts.isJsxText(node) && node.text.trim()) assert.ok(allowed.has(node.text.trim()),`Hardcoded UI: ${node.text}`);
    if(ts.isJsxAttribute(node) && ['aria-label','placeholder','title'].includes(node.name.text)) assert.ok(!ts.isStringLiteral(node.initializer),`Hardcoded ${node.name.text}`);
    ts.forEachChild(node,visit);
  }
  visit(file);
});
test('一键入口缺 Node/npm 时明确失败，不进入安装或改系统环境', {skip:process.platform!=='win32'}, async t => {
  const temporary=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-entry-check-'));
  t.after(()=>fs.rm(temporary,{recursive:true,force:true}));
  const system32=path.join(process.env.SystemRoot,'System32');
  for(const nodePresent of [false,true]) {
    if(nodePresent) await fs.writeFile(path.join(temporary,'node.cmd'),'@echo off\r\nexit /b 99\r\n','utf8');
    const env={...process.env,PATH:`${temporary};${system32}`};
    const child=spawn(path.join(system32,'cmd.exe'),['/d','/s','/c',`call "${path.join(root,'start-desktop.bat')}"`],{env,windowsHide:true,windowsVerbatimArguments:true,stdio:'pipe'});
    let output='';child.stdout.on('data',data=>output+=data.toString());child.stderr.on('data',data=>output+=data.toString());child.stdin.end('\n');
    const code=await new Promise((resolve,reject)=>{child.once('exit',resolve);child.once('error',reject);});
    assert.equal(code,1);assert.match(output,nodePresent?/npm is missing/:/Node.js is missing/);
    assert.doesNotMatch(output,/Installing developer dependencies|Starting Electron/);
  }
});
