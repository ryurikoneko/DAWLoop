import React from 'react';
import {afterEach,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {AudioSetupPanel} from './AudioSetupPanel';
import {taskStatusKey} from './task-status';
import type {DesktopBridge} from '../../../packages/shared-types/contracts';
afterEach(cleanup);
it('任务状态独立于模型状态，执行方法提供真实工作阶段的名称',()=>{
 for(const [method,key] of [['analyze','ANALYZING'],['load','LOADING_MODEL'],['transcribe','TRANSCRIBING'],['writeMidi','EXPORTING']])expect(taskStatusKey({state:'RUNNING',method})).toBe(key);
 for(const state of ['QUEUED','CANCELLED','COMPLETED','FAILED'])expect(taskStatusKey({state,method:'analyze'})).toBe(state);
 expect(taskStatusKey({state:'AVAILABLE',method:'analyze'})).toBe('UNKNOWN');
});
it('缺少组件时不会要求找清单，连接已有环境必须明确确认，稍后配置不启动任务',async()=>{
 const resourceId='a'.repeat(64),connect=vi.fn(async()=>({ok:true,data:{state:'READY'}}));window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({ok:true,data:{state:'NOT_READY',resources:[{id:resourceId,license:'ISC/BSD',additionalBytes:0}],offlineInstallAvailable:false}})),connectLocalAudioRuntime:connect}} as unknown as DesktopBridge;
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><AudioSetupPanel developer={false} pending={false} reasonCode="MI_PYTHON_NOT_CONFIGURED" run={async work=>{await work();}} refresh={async()=>{}}/></I18nextProvider>);
 fireEvent.click(screen.getByRole('button',{name:'Recheck analysis components'}));const button=await screen.findByRole('button',{name:'Use and check components on this computer'});expect((button as HTMLButtonElement).disabled).toBe(true);expect(screen.queryByText(/runtime.json/)).toBeNull();fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(button);await waitFor(()=>expect(connect).toHaveBeenCalledWith({resourceId}));fireEvent.click(screen.getByRole('button',{name:'Set up later'}));expect(screen.queryByRole('checkbox')).toBeNull();
});
