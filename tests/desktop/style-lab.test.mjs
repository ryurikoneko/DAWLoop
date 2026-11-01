import test from 'node:test';
import assert from 'node:assert/strict';
import {StyleLabBridge} from '../../apps/desktop/electron/style-lab.mjs';

test('Style Lab只接受已打开研究库的显式操作，不接受路径或执行参数',async()=>{
 const bridge=new StyleLabBridge({home:'unused'});
 await assert.rejects(bridge.call('list',{}),/IPC_REJECTED/);
 bridge.root='unused';
 for(const [method,params] of [['execute',{}],['clip',{id:'test',path:'C:/private'}],['search',{query:'test',scope:'cross',command:'scan'}],['feedback',{query:'a',candidate:'b',liked:1,approved:true}]])await assert.rejects(bridge.call(method,params),/IPC_REJECTED/);
 for(const [method,params] of [['auditionPreview',{pair:'x',side:'a',mode:'whole',path:'C:/private'}],['auditionRate',{pair:'x',ratings:{},approved:true}],['auditionSummary',{path:'C:/private'}],['auditionLeaveBlind',{command:'scan'}]])await assert.rejects(bridge.call(method,params),/IPC_REJECTED/);
 bridge.close();
});

test('语义研究接口拒绝额外路径、模型执行参数及未打开的资料库',async()=>{
 const bridge=new StyleLabBridge({home:'unused'});
 await assert.rejects(bridge.semantic('styleSemanticStart',{}),/IPC_REJECTED/);
 bridge.root='unused';
 for(const method of ['styleSemanticStart','styleSemanticStatus','styleSemanticCancel'])await assert.rejects(bridge.semantic(method,{path:'C:/private'}),/IPC_REJECTED/);
 await assert.rejects(bridge.semantic('execute',{}),/IPC_REJECTED/);
});

test('生成实验仅接受显式合同，批量分析必须绑定实验，拒绝任意来源和执行参数',async()=>{
 const bridge=new StyleLabBridge({home:'unused'});bridge.root='unused';
 for(const [method,params] of [['generationWorkspace',{command:'scan'}],['generationCreate',{settings:{},path:'C:/private'}],['generationClip',{trial:'x',start:0,end:2,path:'C:/private'}],['generationRevise',{prompt:'x',old:'a',new:'b',reason:'x',trials:[],execute:true}]])await assert.rejects(bridge.call(method,params),/IPC_REJECTED/);
 for(const params of [{trial:'pending'},{trial:'pending',experiment:'invalid'},{trial:'x',command:'scan'}])await assert.rejects(bridge.generation('styleGenerationAnalyze',params),/IPC_REJECTED/);
 await assert.rejects(bridge.generation('styleGenerationCancel',{}),/GENERATION_WORKER_NOT_OWNED/);
});
