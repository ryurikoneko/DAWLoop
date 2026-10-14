import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { WorldView } from './WorldView';
import { createDesktopI18n } from './i18n';
import type { DesktopBridge } from '../../../packages/shared-types/contracts';
afterEach(()=>{cleanup();vi.useRealTimers();});
it('缺源时不把未知伪装成空轨道或已验证插件',async()=>{
  window.dawloop={call:vi.fn(async()=>({apiVersion:1,ok:true,data:{apiVersion:1,state:'unknown',source:'core',session:null,target:null,tracks:[],capabilities:[]}}))} as unknown as DesktopBridge;
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><WorldView mode="mixer"/></I18nextProvider>);
  await screen.findByText('No promoted current Mixer snapshot. Empty slots and zero parameters are not assumed.');
  expect(screen.queryByText('Verified in current bound evidence')).toBeNull();
  expect(screen.queryByRole('button')).toBeNull();
});
it('选择已晋级插件可显示身份布局及值，但不存在写按钮',async()=>{
  const plugin={instanceId:'synthetic-instance',name:'Synthetic plugin',parameterCount:1,parameters:[{index:0,name:'Synthetic gain',value:0.5,readState:'available'}],identityVerified:true,layoutReadable:true,valuesReadable:true,writeEnabled:false};
  window.dawloop={call:vi.fn(async()=>({apiVersion:1,ok:true,data:{apiVersion:1,state:'current',observedAt:new Date().toISOString(),source:'core',session:{sessionId:'synthetic-session',projectGeneration:'synthetic-generation',projectName:'Synthetic project'},target:{trackIndex:1,slotIndex:0},tracks:[{index:1,name:'Synthetic track',slots:[{index:0,state:'occupied',plugin}]}],capabilities:[]}}))} as unknown as DesktopBridge;
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><WorldView mode="mixer"/></I18nextProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'Synthetic plugin'}));
  expect(screen.getByText('Parameter write: Disabled / Not Ready')).toBeTruthy();
  expect(screen.getByText('Read-only value: 0.5')).toBeTruthy();
  expect(screen.getAllByRole('button')).toHaveLength(1);
});
it('刷新未返回时也按到期时刻撤销旧轨道；过期current响应不能恢复',async()=>{
  vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-08T00:00:00Z'));
  const old={apiVersion:1,state:'current',presentation:'real-live',observedAt:new Date().toISOString(),source:'core',session:null,target:null,tracks:[{index:1,name:'Synthetic track',slots:[]}],capabilities:[]};
  let first=true;
  window.dawloop={call:vi.fn(()=>{if(first){first=false;return Promise.resolve({apiVersion:1,ok:true,data:old});}return new Promise(()=>{});})} as unknown as DesktopBridge;
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><WorldView mode="mixer"/></I18nextProvider>);
  await act(async()=>{await Promise.resolve();});expect(screen.getByText('Track 1 · Synthetic track')).toBeTruthy();
  await act(async()=>{await vi.advanceTimersByTimeAsync(15001);});expect(screen.queryByText('Track 1 · Synthetic track')).toBeNull();
  expect(screen.getByText('Real Cached / Stale')).toBeTruthy();cleanup();
  window.dawloop={call:vi.fn(async()=>({apiVersion:1,ok:true,data:old}))} as unknown as DesktopBridge;
  render(<I18nextProvider i18n={createDesktopI18n('en-US')}><WorldView mode="mixer"/></I18nextProvider>);
  await act(async()=>{await Promise.resolve();});expect(screen.queryByText('Track 1 · Synthetic track')).toBeNull();
});
