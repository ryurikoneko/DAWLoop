import React from 'react';
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {App} from './App';
import {AISetup} from './AISetup';
import {MusicIntelligence} from './MusicIntelligence';
import type {DesktopBridge,DesktopEnvironment} from '../../../packages/shared-types/contracts';

afterEach(cleanup);
const environment={packaged:true,appVersion:'0.5.1-internal.1',dependencies:{python:'not-bundled',controller:'present-unverified',core:'desktop-only',host:'user-installed'}} as DesktopEnvironment;
function fixture(language:'zh-CN'|'en-US'='en-US') {
  let config={schemaVersion:1,activeProfileId:'default',ui:{} as Record<string,unknown>,host:{executablePath:''},general:{launchAtLogin:false,detectHostOnStartup:true,autoStartRuntime:false,logLevel:'Normal'},features:{experimentalMixerWrite:false}};
  const music={status:vi.fn(async()=>({apiVersion:1,ok:true,data:{assets:[],jobs:[]}})),models:vi.fn(async()=>({apiVersion:1,ok:true,data:[]})),setupStatus:vi.fn(),importAudio:vi.fn(async()=>({apiVersion:1,ok:true,data:null}))};
  const call=vi.fn(async(method:string,p?:{ui?:object})=>{if(method==='updateConfig')config={...config,ui:{...config.ui,...p?.ui}};return {apiVersion:1,ok:true,data:({getConfig:config,updateConfig:config,testHostPath:{valid:false},getProfiles:[],getActiveProfile:null,getRecentLogs:[],getAppStatus:{backend:'real',runtime:{state:'unknown'},host:{state:'unknown'},bridges:[],errors:[],capabilities:[]}} as Record<string,unknown>)[method]};});
  window.dawloop={call,music} as unknown as DesktopBridge;
  const i18n=createDesktopI18n(language);const ui=render(<I18nextProvider i18n={i18n}><App environment={environment}/></I18nextProvider>);
  return {call,music,i18n,ui};
}
for(const language of ['en-US','zh-CN'] as const)it(`${language}：首启只属于首页，跳过保留，独立音乐入口不触发模型安装`,async()=>{
  const f=fixture(language);const title=language==='en-US'?'First launch checks':'首次启动检查';
  await screen.findByRole('heading',{name:title});
  for(const name of language==='en-US'?['Music Intelligence','Profiles','Mixer','Settings']:['音乐智能','Profiles','混音台','设置']) {
    if(name==='Profiles'&&language==='zh-CN')continue;
    fireEvent.click(screen.getByRole('button',{name:new RegExp(`^${name}`)}));
    expect(screen.queryByRole('heading',{name:title})).toBeNull();
  }
  fireEvent.click(screen.getByRole('button',{name:language==='en-US'?'Home':'首页'}));
  fireEvent.click(await screen.findByRole('button',{name:language==='en-US'?'Start using music features':'开始使用音乐功能'}));
  await waitFor(()=>expect(screen.queryByRole('heading',{name:title})).toBeNull());
  fireEvent.click(screen.getByRole('button',{name:language==='en-US'?'Music Intelligence':'音乐智能'}));
  expect(await screen.findByRole('button',{name:language==='en-US'?'Analyze music':'分析音乐'})).toBeTruthy();
  expect(f.music.setupStatus).not.toHaveBeenCalled();
  expect(f.call.mock.calls.some(([m])=>['startRuntime','setBackend','setMockScenario'].includes(m))).toBe(false);
});
it('模式立即保存且只改变展示，不授予开发后端权限',async()=>{
  const f=fixture();await screen.findByRole('heading',{name:'First launch checks'});
  expect(screen.queryByText('Core API')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Settings'}));
  fireEvent.click(screen.getByText('Advanced settings'));
  fireEvent.click(screen.getByRole('checkbox',{name:'Developer mode'}));
  await screen.findByText('Core API');expect(f.call).toHaveBeenCalledWith('updateConfig',{ui:{mode:'DEVELOPER_MODE'}});
  fireEvent.click(screen.getByRole('checkbox',{name:'Developer mode'}));
  await waitFor(()=>expect(screen.queryByText('Core API')).toBeNull());
  expect(f.call).toHaveBeenCalledWith('updateConfig',{ui:{mode:'USER_MODE'}});
  expect(f.call.mock.calls.some(([m])=>['setBackend','setMockScenario'].includes(m))).toBe(false);
});
it('禁用模型选择和许可控件提供原因，且不自动展开协议',async()=>{
  const status={completed:false,hardware:{cpu:'test',ramBytes:32*1024**3,platform:'win32',python:[],gpu:null},providers:[{id:'yue2-plan',qualification:'UNKNOWN',installable:false,diskEligible:true,minimumStorageBytes:1,freeBytes:20,downloadBytes:null,license:'CC-BY-NC-4.0',reason:'PLAN_RUNTIME_UNQUALIFIED'}]};
  window.dawloop={music:{setupStatus:vi.fn(async()=>({apiVersion:1,ok:true,data:status}))}} as unknown as DesktopBridge;
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><AISetup active/></I18nextProvider>);
  await waitFor(()=>expect(window.dawloop.music.setupStatus).toHaveBeenCalled());
  expect(screen.queryByRole('checkbox')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'AI first-use setup'}));
  const checks=await screen.findAllByRole('checkbox');expect(checks.every(c=>(c as HTMLInputElement).disabled)).toBe(true);
  expect(checks.every(c=>Boolean(c.getAttribute('aria-describedby')))).toBe(true);
  expect(screen.getByText(/not qualified for installation/)).toBeTruthy();
});
it('迟到的作曲完成记录不会把用户从音乐库拉回音符页',async()=>{
  let jobs:unknown[]=[];
  const status=vi.fn(async()=>({apiVersion:1,ok:true,data:{assets:[],jobs}}));
  window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({apiVersion:1,ok:true,data:{state:'NOT_READY',resources:[],offlineInstallAvailable:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING'}})),status,models:vi.fn(async()=>({apiVersion:1,ok:true,data:[]}))}} as unknown as DesktopBridge;
  const i18n=createDesktopI18n('en-US');
  const ui=render(<I18nextProvider i18n={i18n}><MusicIntelligence active/></I18nextProvider>);
  await waitFor(()=>expect(status).toHaveBeenCalled());fireEvent.click(screen.getByRole('tab',{name:'Melody creation'}));
  fireEvent.click(screen.getByRole('tab',{name:'My music library'}));
  jobs=[{id:'late-generation',state:'COMPLETED',method:'generate',result:{candidates:[{schemaVersion:1,tempo:120,meter:[4,4],tempoMap:[],notes:[],source:'RULE_BASED',edits:[]}]}}];
  ui.rerender(<I18nextProvider i18n={i18n}><MusicIntelligence active={false}/></I18nextProvider>);
  ui.rerender(<I18nextProvider i18n={i18n}><MusicIntelligence active/></I18nextProvider>);
  await waitFor(()=>expect(status.mock.calls.length).toBeGreaterThan(1));
  expect(screen.getByRole('tab',{name:'My music library'}).getAttribute('aria-selected')).toBe('true');
});
