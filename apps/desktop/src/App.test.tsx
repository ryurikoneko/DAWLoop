import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App, State } from './App';
import { I18nextProvider } from 'react-i18next';
import { createDesktopI18n } from './i18n';
import type { AppStatus, DesktopBridge } from '../../../packages/shared-types/contracts';

afterEach(cleanup);
describe('状态展示', () => {
  for (const value of ['checking','connected','disconnected','degraded','running','stopped','faulted','starting','stopping','unknown']) it(value, () => { const {container} = render(<I18nextProvider i18n={createDesktopI18n('en-US')}><State value={value}/></I18nextProvider>); expect(container.querySelector(`.${value}`)).not.toBeNull(); expect(container.textContent?.toLowerCase()).toContain(value); });
});
function bridge(state='disconnected') {
  const status = { apiVersion:1,appVersion:'test',backend:'mock',label:'DEVELOPMENT MOCK',observedAt:'2026-10-07T00:00:00Z',runtime:{state:'stopped',version:null,controllable:true,reason:'MOCK'},host:{state,detected:false,processRunning:false,version:null,reason:'MOCK'},bridges:[],capabilities:[],errors:[] } as AppStatus;
  const profile = { schemaVersion:1,id:'default',name:'Default',runtime:{},verification:{preset:'Strict'},agent:{},mixer:{},ui:{} };
  const config = { ui:{mode:'DEVELOPER_MODE'}, schemaVersion:1,activeProfileId:'default',general:{ launchAtLogin:false,detectHostOnStartup:true,autoStartRuntime:false,logLevel:'Normal' },host:{executablePath:''},features:{} };
  const entries = [{sequence:1,timestamp:'2026-10-07T00:00:00Z',source:'Runtime',level:'INFO',message:'old log'}];
  const call = vi.fn(async (method:string) => ({ apiVersion:1,ok:true,data:({getAppStatus:status,getRecentLogs:entries,getConfig:config,getProfiles:[profile],getActiveProfile:profile} as Record<string,unknown>)[method] ?? null }));
  window.dawloop = { call,copy:vi.fn(async()=>({apiVersion:1,ok:true,data:null})),browseHost:vi.fn() } as unknown as DesktopBridge;
  return call;
}
it('加载后显示Mock标签；日志clear-view不调用删除方法', async () => {
  const call = bridge(); render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>); expect(screen.getAllByText('Reading status…').length).toBeGreaterThan(0);
  await waitFor(()=>expect(screen.getByText('DEVELOPMENT MOCK')).toBeTruthy()); fireEvent.click(screen.getByRole('button',{name:'Logs'}));
  expect(screen.getByText('old log')).toBeTruthy(); fireEvent.click(screen.getByText('Clear view')); expect(screen.queryByText('old log')).toBeNull();
  expect(call.mock.calls.every(([method])=>!method.toLowerCase().includes('delete'))).toBe(true);
});
it('错误结果显示错误，不保留绿色状态', async () => {
  bridge(); window.dawloop.call = vi.fn(async () => ({apiVersion:1,ok:false,error:{code:'OFFLINE',category:'backend',message:'离线',recoverable:true}})) as DesktopBridge['call'];
  const {container} = render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>); await waitFor(()=>expect(screen.getAllByRole('alert').some(x=>x.textContent?.includes('Operation failed'))).toBe(true)); expect(container.querySelector('.connected')).toBeNull();
});
it('普通模式不渲染开发控件；显式开发模式才显示', async () => {
  bridge();
  const i18n=createDesktopI18n('en-US');
  const {rerender}=render(<I18nextProvider i18n={i18n}><App/></I18nextProvider>);
  await screen.findByText('DEVELOPMENT MOCK');
  expect(screen.queryByLabelText('Backend')).toBeNull();
  expect(screen.queryByLabelText('Mock scenario')).toBeNull();
  rerender(<I18nextProvider i18n={i18n}><App development/></I18nextProvider>);
  expect(screen.getByLabelText('Backend')).toBeTruthy();
  expect(screen.getByLabelText('Mock scenario')).toBeTruthy();
});
it('后到的旧状态请求不能覆盖较新的状态', async () => {
  const original=bridge(); let resolveOld!: (value: unknown)=>void; let reads=0;
  const old=new Promise(resolve=>{resolveOld=resolve;});
  window.dawloop.call=vi.fn(async(method:string)=>{
    if (method==='getAppStatus' && ++reads===1) return old;
    return original(method);
  }) as unknown as DesktopBridge['call'];
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>);
  await waitFor(()=>expect(reads).toBe(1));
  fireEvent.click(screen.getByRole('button',{name:'Refresh'}));
  await screen.findByText('DEVELOPMENT MOCK');
  const response=await original('getAppStatus');
  await act(async()=>{ resolveOld({...response,data:{...response.data as object,backend:'real'}}); });
  await waitFor(()=>expect(reads).toBe(2));
  expect(screen.queryByText('Real backend · read-only observer')).toBeNull();
});
it('日志检索叠加级别与来源，复制只包含当前匹配项', async () => {
  bridge();
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>);
  await screen.findByText('DEVELOPMENT MOCK'); fireEvent.click(screen.getByRole('button',{name:'Logs'}));
  fireEvent.change(screen.getByLabelText('Search messages or codes'),{target:{value:'OLD'}});
  expect(screen.getByText('old log')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Log level filter'),{target:{value:'ERROR'}});
  expect(screen.queryByText('old log')).toBeNull();
  fireEvent.click(screen.getByText('Copy logs'));
  await waitFor(()=>expect(window.dawloop.copy).toHaveBeenCalledWith(''));
  fireEvent.change(screen.getByLabelText('Log level filter'),{target:{value:'ALL'}});
  fireEvent.change(screen.getByLabelText('Log source filter'),{target:{value:'Desktop'}});
  expect(screen.queryByText('old log')).toBeNull();
});
it('读取失败后重试成功清除读取错误；恢复未知状态不宣称连接', async () => {
  const original=bridge(); let failed=true;
  window.dawloop.call=vi.fn(async(method:string)=>method==='getAppStatus' && failed
    ? {apiVersion:1,ok:false,error:{code:'BACKEND_OFFLINE',category:'backend',message:'BACKEND_OFFLINE',recoverable:true}}
    : original(method)) as unknown as DesktopBridge['call'];
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>);
  await screen.findByRole('alert'); failed=false;
  fireEvent.click(screen.getByRole('button',{name:'Retry observation'}));
  await screen.findByText('Connection has not been verified');
  expect(screen.queryByRole('alert')).toBeNull();
  expect(screen.queryByText('Connected',{exact:true})).toBeNull();
  expect(original.mock.calls.some(([method])=>method==='startRuntime')).toBe(false);
});
it('诊断取消导出可继续操作，且不重新读取宿主', async () => {
  const original=bridge();
  window.dawloop.call=vi.fn(async(method:string)=>method==='getDiagnostics' ? {apiVersion:1,ok:true,data:{apiVersion:1}} : original(method)) as unknown as DesktopBridge['call'];
  window.dawloop.exportDiagnostics=vi.fn(async()=>({apiVersion:1 as const,ok:true as const,data:{saved:false}}));
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><App/></I18nextProvider>);
  await screen.findByText('DEVELOPMENT MOCK'); fireEvent.click(screen.getByRole('button',{name:'Diagnostics'}));
  expect(screen.getByText('Export diagnostic report').hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByText('Run diagnostics'));
  await waitFor(()=>expect(screen.getByText('Export diagnostic report').hasAttribute('disabled')).toBe(false));
  fireEvent.click(screen.getByText('Export diagnostic report'));
  await screen.findByText('Export cancelled; no file written');
  expect(window.dawloop.exportDiagnostics).toHaveBeenCalledWith();
  expect(window.dawloop.call).toHaveBeenCalledWith('getDiagnostics');
});
