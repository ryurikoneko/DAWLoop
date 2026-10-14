import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {BASIC_COMPONENT,basicComponentSource,verifyBasicEnvironment} from '../../packages/music-intelligence/basic-component.mjs';
import {MusicIntelligenceService} from '../../packages/music-intelligence/service.mjs';
import {componentEntryPath} from '../../packages/music-intelligence/component-extract.mjs';

test('基础组件缺失时报告安装需求，不创建注定失败任务，不泄露目录',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'basic-component-missing-'));let service;
 try{service=new MusicIntelligenceService({home:path.join(root,'user'),componentRoot:path.join(root,'resources')});await service.initialize();const status=await service.audioSetupStatus();assert.equal(status.state,'NOT_READY');assert.equal(status.componentState,process.platform==='win32'?'INSTALL_REQUIRED':'NOT_SUPPORTED');assert.equal(status.offlineInstallAvailable,false);assert.equal(JSON.stringify(status).includes(root),false);await assert.rejects(service.install('basic',BASIC_COMPONENT.licenseAcknowledgement),/MI_COMPONENT_(PACKAGE_MISSING|PLATFORM_UNSUPPORTED)/);assert.equal(service.jobs.size,0);}finally{await service?.close();await fs.rm(root,{recursive:true,force:true});}
});
test('安装参数不允许注入来源目录，许可必须明确确认',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'basic-component-permission-'));const service=new MusicIntelligenceService({home:root});
 try{await service.initialize();await assert.rejects(service.call('install',{modelId:'basic',licenseAccepted:BASIC_COMPONENT.licenseAcknowledgement,path:root}),/IPC_REJECTED/);await assert.rejects(service.install('basic','ISC/BSD'),/MI_LICENSE_CONFIRMATION_REQUIRED/);assert.equal(service.jobs.size,0);}finally{await service.close();await fs.rm(root,{recursive:true,force:true});}
});
test('组件尺寸或摘要错误拒绝，普通JSON不能自报受信来源',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'basic-component-hash-'));
 try{await fs.writeFile(path.join(root,BASIC_COMPONENT.fileName),'not a component');const source=await basicComponentSource(root);assert.equal(source.available,false);assert.match(source.reasonCode,/MI_COMPONENT_(HASH_REJECTED|PLATFORM_UNSUPPORTED)/);await fs.writeFile(path.join(root,'component.json'),JSON.stringify({componentId:'basic-audio',files:[]}));await assert.rejects(verifyBasicEnvironment(root),/MI_COMPONENT_HASH_REJECTED/);}finally{await fs.rm(root,{recursive:true,force:true});}
});
test('组件状态和任务状态独立，取消不能伪装已提交启用的任务',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'basic-component-state-'));const service=new MusicIntelligenceService({home:root});
 try{await service.initialize();service.jobs.set('owned',{id:'owned',method:'install',modelId:'basic',state:'VERIFYING'});assert.equal((await service.audioSetupStatus()).componentState,'INSTALLING');service.jobs.get('owned').activationCommitted=true;assert.equal(service.cancel('owned'),false);Object.assign(service.jobs.get('owned'),{state:'FAILED',finishedAt:'2026-10-14',error:'MI_COMPONENT_INSTALL_FAILED'});assert.equal((await service.audioSetupStatus()).componentState,'FAILED');}finally{await service.close();await fs.rm(root,{recursive:true,force:true});}
});
test('归档路径拒绝穿越、绝对路径、ADS、设备名及Windows尾随歧义',()=>{
 const root=path.resolve(os.tmpdir(),'owned-component');
 for(const name of ['../escape','/escape','C:/escape','module\\escape','python.exe:stream','CON.txt','lib/aux','module.','module ','lib//module'])assert.throws(()=>componentEntryPath(root,name),/MI_ARCHIVE_PATH_REJECTED/);
 assert.equal(componentEntryPath(root,'Lib/site-packages/module.py'),path.join(root,'Lib/site-packages/module.py'));
});
