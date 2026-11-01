import React from 'react';
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,cleanup,act} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {Splash} from './Splash';
import {useWorkspaceMotion} from './motion';
afterEach(()=>{cleanup();vi.restoreAllMocks();delete (HTMLElement.prototype as unknown as {animate?:unknown}).animate;vi.unstubAllGlobals();delete document.documentElement.dataset.reducedMotion;});
it('动态版本与黑屏文字独立，正常动画固定1000ms，初始化慢时保留加载状态',()=>{
 const animation={cancel:vi.fn(),onfinish:null as null|(()=>void)};const animate=vi.fn((_frames:unknown,_options:unknown)=>animation);vi.stubGlobal('matchMedia',()=>({matches:false}));Object.defineProperty(HTMLElement.prototype,'animate',{configurable:true,value:animate});
 render(<I18nextProvider i18n={createDesktopI18n('zh-CN')}><Splash version="9.8.7-internal.1" ready={false}/></I18nextProvider>);expect(screen.getByText('v9.8.7-internal.1')).toBeTruthy();expect(animate.mock.calls[0][1]).toMatchObject({duration:1000});act(()=>animation.onfinish?.());expect(screen.getByRole('status').textContent).toBe('正在准备工作区');
});
it('减少动态效果立即跳过视觉片段，但不伪造初始化就绪',()=>{
 vi.stubGlobal('matchMedia',()=>({matches:false}));const view=render(<I18nextProvider i18n={createDesktopI18n('en-US')}><Splash version="9.8.7" ready={false} reduced/></I18nextProvider>);expect(screen.getByRole('status').textContent).toBe('Preparing your workspace');view.rerender(<I18nextProvider i18n={createDesktopI18n('en-US')}><Splash version="9.8.7" ready reduced/></I18nextProvider>);expect(screen.queryByText('v9.8.7')).toBeNull();
});
it('页面动效只作用容器，切页不卸载内部状态，用户减少动态效果时不调用动画',()=>{
 vi.stubGlobal('matchMedia',()=>({matches:false}));const animate=vi.fn((_frames:unknown,_options:unknown)=>({cancel:vi.fn()}));Object.defineProperty(HTMLElement.prototype,'animate',{configurable:true,value:animate});function Page({name}:{name:string}){const ref=useWorkspaceMotion(name);return <section ref={ref}><input defaultValue="state"/></section>;}
 const view=render(<Page name="Home"/>);const input=view.container.querySelector('input');view.rerender(<Page name="Music"/>);expect(view.container.querySelector('input')).toBe(input);expect(animate.mock.calls[0][1]).toMatchObject({duration:220});document.documentElement.dataset.reducedMotion='true';view.rerender(<Page name="Settings"/>);expect(animate).toHaveBeenCalledTimes(1);
});
