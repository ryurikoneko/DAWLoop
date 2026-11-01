import React from 'react';
import {afterEach,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {MusicIntelligence} from './MusicIntelligence';
import type {DesktopBridge} from '../../../packages/shared-types/contracts';
afterEach(cleanup);
const asset={id:'1'.repeat(32),name:'owned.wav',sha256:'2'.repeat(64),bytes:100,extension:'.wav',collection:'default',visibility:'SESSION_IMPORT'};
it('迟到分析完成只更新结果，不覆盖用户选择的音乐库页面',async()=>{
 let completed=false;const status=vi.fn(async()=>({apiVersion:1,ok:true,data:{assets:[asset],jobs:completed?[{id:'completed',method:'analyze',state:'COMPLETED',progress:1,error:null,result:{assetId:asset.id,bpmCandidates:[],profile:{userDescription:''}}}]:[]}}));
 window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({apiVersion:1,ok:true,data:{state:'NOT_READY',resources:[],offlineInstallAvailable:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING'}})),status,models:vi.fn(async()=>({apiVersion:1,ok:true,data:[]}))}} as unknown as DesktopBridge;
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><MusicIntelligence active entry={{tab:'library',assetId:asset.id,sequence:1}}/></I18nextProvider>);
 await screen.findByRole('button',{name:asset.name});completed=true;
 await screen.findByText('Completed',{}, {timeout:3000});expect(screen.getByRole('tab',{name:'My music library'}).getAttribute('aria-selected')).toBe('true');expect(screen.getByRole('button',{name:asset.name})).toBeTruthy();
});
it('未就绪环境阻止分析，提供应用内连接入口且不创建失败任务',async()=>{
 const analyze=vi.fn();window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({apiVersion:1,ok:true,data:{state:'NOT_READY',resources:[],offlineInstallAvailable:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING'}})),status:vi.fn(async()=>({apiVersion:1,ok:true,data:{assets:[asset],jobs:[]}})),models:vi.fn(async()=>({apiVersion:1,ok:true,data:[{id:'basic',status:'BLOCKED',reason:'MI_PYTHON_NOT_CONFIGURED'}]})),analyze}} as unknown as DesktopBridge;
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><MusicIntelligence active entry={{tab:'analysis',assetId:asset.id,sequence:1}}/></I18nextProvider>);
 const button=await screen.findByRole('button',{name:'Analyze full song'});await waitFor(()=>expect((button as HTMLButtonElement).disabled).toBe(true));expect(await screen.findByRole('button',{name:'Recheck analysis components'})).toBeTruthy();expect(screen.queryByRole('button',{name:'Choose existing analysis components (advanced)'})).toBeNull();expect(analyze).not.toHaveBeenCalled();
});
it('失败任务没有推进进度条，可独立清除且其他任务保留',async()=>{
 let jobs=[{id:'failed',method:'analyze',state:'FAILED',progress:.4,error:'MI_WORKER_FAILED'},{id:'other',method:'owned',state:'QUEUED',progress:0,error:null}];const dismiss=vi.fn(async({id}:{id:string})=>{jobs=jobs.filter(j=>j.id!==id);return {apiVersion:1,ok:true,data:true};});
 window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({apiVersion:1,ok:true,data:{state:'NOT_READY',resources:[],offlineInstallAvailable:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING'}})),status:vi.fn(async()=>({apiVersion:1,ok:true,data:{assets:[],jobs}})),models:vi.fn(async()=>({apiVersion:1,ok:true,data:[]})),dismiss}} as unknown as DesktopBridge;
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><MusicIntelligence active/></I18nextProvider>);const clear=await screen.findByRole('button',{name:'Dismiss task record'});expect(screen.getAllByRole('progressbar').length).toBe(1);fireEvent.click(clear);await waitFor(()=>expect(dismiss).toHaveBeenCalledWith({id:'failed'}));await waitFor(()=>expect(screen.queryByRole('button',{name:'Dismiss task record'})).toBeNull());expect(screen.getByRole('button',{name:'Cancel'})).toBeTruthy();
});
