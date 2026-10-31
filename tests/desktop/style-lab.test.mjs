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
