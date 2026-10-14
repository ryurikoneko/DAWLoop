import React from 'react';
import {test,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {AudioSetupPanel} from './AudioSetupPanel';
import type {DesktopBridge} from '../../../packages/shared-types/contracts';
afterEach(cleanup);
test('用户无需选择Python目录，许可确认后通过已有安装API提交任务',async()=>{
 const install=vi.fn(async()=>({ok:true,data:'real-job-id'}));
 window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({ok:true,data:{state:'NOT_READY',componentState:'INSTALL_REQUIRED',resources:[],offlineInstallAvailable:true,reasonCode:null,component:{id:'basic-audio',version:'1.0.0-internal.1',archiveBytes:130805951,installedBytes:391080935,minimumFreeBytes:805306368,license:'PSF/BSD',licenseReview:'PENDING'}}})),install}} as unknown as DesktopBridge;
 const refresh=vi.fn(async()=>{});render(<I18nextProvider i18n={createDesktopI18n('en-US')}><AudioSetupPanel developer={false} pending={false} reasonCode={null} run={async work=>{await work();}} refresh={refresh}/></I18nextProvider>);
 const button=await screen.findByRole('button',{name:'Install basic components'});
 expect((button as HTMLButtonElement).disabled).toBe(true);expect(screen.queryByText(/1.0.0-internal.1/)).toBeNull();
 fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(button);
 await waitFor(()=>expect(install).toHaveBeenCalledWith({modelId:'basic',licenseAccepted:'PSF/BSD'}));
 expect(screen.queryByRole('button',{name:'Configure audio environment'})).toBeNull();
});
test('资源缺失时安装不可点击，界面明确提供恢复方向',async()=>{
 window.dawloop={music:{audioSetupStatus:vi.fn(async()=>({ok:true,data:{state:'NOT_READY',componentState:'INSTALL_REQUIRED',resources:[],offlineInstallAvailable:false,reasonCode:'MI_COMPONENT_PACKAGE_MISSING',component:{id:'basic-audio',version:'1.0.0-internal.1',archiveBytes:130805951,installedBytes:391080935,minimumFreeBytes:805306368,license:'PSF/BSD',licenseReview:'PENDING'}}}))}} as unknown as DesktopBridge;
 render(<I18nextProvider i18n={createDesktopI18n('zh-CN')}><AudioSetupPanel developer={false} pending={false} reasonCode="MI_COMPONENT_PACKAGE_MISSING" run={async work=>{await work();}} refresh={async()=>{}}/></I18nextProvider>);
 const button=await screen.findByRole('button',{name:'安装基础组件'});expect((button as HTMLButtonElement).disabled).toBe(true);expect(screen.getByText(/本安装包尚未附带可验证/)).toBeTruthy();expect(screen.queryByText('MI_COMPONENT_PACKAGE_MISSING')).toBeNull();
});
