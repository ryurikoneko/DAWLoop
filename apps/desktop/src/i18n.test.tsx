import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { createDesktopI18n, resources } from './i18n';
import { App } from './App';
import type { DesktopBridge } from '../../../packages/shared-types/contracts';

afterEach(cleanup);
describe('翻译资源与回退', () => {
  it('音乐主页和音符起点使用独立资源键', () => {
    const en=createDesktopI18n('en-US'),zh=createDesktopI18n('zh-CN');
    expect(en.t('music:start')).toBe('Start (beats)');expect(zh.t('music:start')).toBe('起点（拍）');
    expect(en.t('music:workspace')).toBe('Music home');expect(zh.t('music:workspace')).toBe('音乐主页');
  });
  function keys(value: object, prefix = ''): string[] { return Object.entries(value).flatMap(([key,item])=>typeof item==='object' && item ? keys(item,`${prefix}${key}.`) : [`${prefix}${key}`]); }
  it('每个命名空间中英文资源键一致，文案非空', () => {
    expect(Object.keys(resources['zh-CN']).sort()).toEqual(Object.keys(resources['en-US']).sort());
    for (const namespace of Object.keys(resources['en-US'])) {
      expect(keys(resources['zh-CN'][namespace]).sort()).toEqual(keys(resources['en-US'][namespace]).sort());
      for (const language of ['zh-CN','en-US']) expect(JSON.stringify(resources[language][namespace])).not.toContain(':""');
    }
  });
  it('生产缺键使用明确英文文本，不读取另一语言', () => {
    const data = structuredClone(resources) as typeof resources & Record<string, {common: {loading?:string}}>;
    delete data['en-US'].common.loading;
    const i18n = createDesktopI18n('en-US',data);
    expect(i18n.t('loading')).toBe('Content is temporarily unavailable. Retry or check diagnostics.');
    expect(i18n.t('noSuchKey')).toBe('Content is temporarily unavailable. Retry or check diagnostics.');
    expect(i18n.t('noSuchKey')).not.toBe('undefined');
  });
  it('空字符串也走回退', () => {
    const data = structuredClone(resources) as typeof resources & Record<string,{common:{loading:string}}>;
    data['en-US'].common.loading='';
    expect(createDesktopI18n('en-US',data).t('loading')).toBe('Content is temporarily unavailable. Retry or check diagnostics.');
  });
  it('开发缺键显式标记；中文缺键也不隐式借用英文资源', () => {
    const data = structuredClone(resources) as typeof resources & Record<string,{common:{loading?:string}}>;
    delete data['zh-CN'].common.loading;
    expect(createDesktopI18n('zh-CN',data,true).t('loading')).toBe('[missing:loading]');
    expect(createDesktopI18n('zh-CN',data).t('loading')).toBe('内容暂不可用，请重试或查看诊断。');
    expect(createDesktopI18n('en-US',data,true).t('noSuchKey',{defaultValue:'fallback'})).toBe('[missing:noSuchKey]');
  });
});
function setup(failLanguage = false, slowStatus = false, slowDiagnostics = false) {
  const config = {schemaVersion:1,activeProfileId:'default',ui:{language:'zh-CN'},general:{launchAtLogin:false,detectHostOnStartup:true,autoStartRuntime:false,logLevel:'Normal'},host:{executablePath:''},features:{experimentalMixerWrite:false}};
  const profile = {schemaVersion:1,id:'default',name:'Default',verification:{preset:'Strict'}};
  const status = {backend:'mock',observedAt:'2026-10-07T00:00:00Z',runtime:{state:'stopped',controllable:true},host:{state:'disconnected'},bridges:[],capabilities:[],errors:[]};
  const call = vi.fn(async(method:string,params?:unknown)=> {
    if (method==='getAppStatus' && slowStatus) return new Promise<never>(()=>{});
    if (method==='getDiagnostics' && slowDiagnostics) return new Promise<never>(()=>{});
    if (method==='updateConfig') {
      if (failLanguage) return {apiVersion:1,ok:false,error:{code:'INVALID_LANGUAGE'}};
      Object.assign(config.ui,(params as {ui:object}).ui);
    }
    return {apiVersion:1,ok:true,data:({getConfig:config,updateConfig:config,getProfiles:[profile],getActiveProfile:profile,getAppStatus:status,getRecentLogs:[]} as Record<string,unknown>)[method]};
  });
  window.dawloop={call} as unknown as DesktopBridge;
  const i18n = createDesktopI18n('zh-CN');
  render(<I18nextProvider i18n={i18n}><App/></I18nextProvider>);
  return {i18n,call};
}
it('当前窗口即时切英文，所有导航/设置/通知更新且未保存表单保留', async () => {
  const {i18n,call}=setup();
  await screen.findByText('DEVELOPMENT MOCK');
  fireEvent.click(screen.getByRole('button',{name:'设置'}));
  fireEvent.click(screen.getByText('启动与日志偏好'));
  const checkbox=screen.getByRole('checkbox',{name:i18n.t('settings:launchAtLogin')});fireEvent.click(checkbox);
  fireEvent.change(screen.getByLabelText('语言'),{target:{value:'en-US'}});
  await waitFor(()=>expect(i18n.language).toBe('en-US'));
  expect(screen.getByRole('button',{name:'Home'})).toBeTruthy();
  expect(screen.getByText('Language preference saved')).toBeTruthy();
  expect((screen.getByRole('checkbox',{name:i18n.t('settings:launchAtLogin')}) as HTMLInputElement).checked).toBe(true);
  expect(call.mock.calls.find(([method])=>method==='updateConfig')?.[1]).toEqual({ui:{language:'en-US'}});
});
it('保存失败保持原语言，展示可翻译错误，不能伪装持久化成功', async () => {
  const {i18n}=setup(true); await screen.findByText('DEVELOPMENT MOCK');
  fireEvent.click(screen.getByRole('button',{name:'设置'}));
  fireEvent.change(screen.getByLabelText('语言'),{target:{value:'en-US'}});
  await screen.findByRole('alert');expect(i18n.language).toBe('zh-CN');
  expect(screen.queryByText('Language preference saved')).toBeNull();
});
it('观察器未返回时语言保存仍完成、按钮恢复可用', async () => {
  const {i18n}=setup(false,true);
  fireEvent.click(screen.getByRole('button',{name:'设置'}));
  await screen.findByLabelText('语言');
  fireEvent.change(screen.getByLabelText('语言'),{target:{value:'en-US'}});
  await screen.findByText('Language preference saved');
  expect(i18n.language).toBe('en-US');
  expect((screen.getByLabelText('Language') as HTMLSelectElement).disabled).toBe(false);
  expect((screen.getByRole('button',{name:'Save settings'}) as HTMLButtonElement).disabled).toBe(false);
});
it('诊断等待期间可切到设置并保存语言', async () => {
  const {i18n}=setup(false,false,true);
  await screen.findByText('DEVELOPMENT MOCK');
  fireEvent.click(screen.getByRole('button',{name:'诊断'}));
  fireEvent.click(screen.getByRole('button',{name:'运行诊断'}));
  fireEvent.click(screen.getByRole('button',{name:'设置'}));
  expect((screen.getByLabelText('语言') as HTMLSelectElement).disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('语言'),{target:{value:'en-US'}});
  await screen.findByText('Language preference saved');
  expect(i18n.language).toBe('en-US');
});
