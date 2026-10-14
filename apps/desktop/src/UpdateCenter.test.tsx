// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {UpdateCenter,type UpdateView} from './UpdateCenter';
afterEach(cleanup);
const base:UpdateView={version:'0.5.6',preferences:{enabled:true,channel:'stable',notifications:true},checkedAt:null,status:'UNKNOWN',release:null,publicPush:'DISABLED',snoozeUntil:0};
function mount(view=base,language:'en-US'|'zh-CN'='en-US') {
  const ok=(data:unknown)=>({apiVersion:1,ok:true,data});
  const updates={get:vi.fn(async()=>ok(view)),check:vi.fn(async()=>ok(view)),configure:vi.fn(async(p:object)=>ok({...view,preferences:{...view.preferences,...p}})),snooze:vi.fn(async()=>ok({...view,snoozeUntil:999999})),open:vi.fn(async()=>ok(true))};
  Object.defineProperty(window,'dawloop',{configurable:true,value:{updates}});
  render(<I18nextProvider i18n={createDesktopI18n(language)}><UpdateCenter/></I18nextProvider>);return updates;
}
it('默认门关闭：显示版本和频道但不宣传未批准更新',async()=>{mount();await screen.findByText('Installed version: 0.5.6');expect(screen.queryByText('View release notes')).toBeNull();expect(screen.getByLabelText('Update channel')).toBeTruthy();});
it('检查更新、Preview选择、稍后提醒和查看按钮使用专用IPC',async()=>{const v={...base,status:'UPDATE_AVAILABLE' as const,publicPush:'APPROVED' as const,release:{version:'v0.6.0',publishedAt:'2026-10-14T00:00:00Z',notes:'Synthetic notes'}};const u=mount(v);await screen.findByText('View release notes');fireEvent.click(screen.getByText('Check for updates'));await waitFor(()=>expect(u.check).toHaveBeenCalled());fireEvent.change(screen.getByLabelText('Update channel'),{target:{value:'preview'}});await waitFor(()=>expect(u.configure).toHaveBeenCalledWith({channel:'preview'}));await waitFor(()=>expect((screen.getByText('Remind me later') as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByText('Remind me later'));await waitFor(()=>expect(u.snooze).toHaveBeenCalled());await waitFor(()=>expect((screen.getByText('View release notes') as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByText('View release notes'));await waitFor(()=>expect(u.open).toHaveBeenCalled());});
it('中文版入口且关闭检查按钮不会继续请求',async()=>{mount({...base,preferences:{...base.preferences,enabled:false},status:'CHECK_DISABLED'},'zh-CN');await screen.findByText('当前版本: 0.5.6');expect((screen.getByText('检查更新') as HTMLButtonElement).disabled).toBe(true);});
