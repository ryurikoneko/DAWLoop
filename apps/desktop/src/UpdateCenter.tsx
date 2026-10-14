// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
import {useEffect,useState} from 'react';
import {useTranslation} from 'react-i18next';
import type {DesktopUpdateView} from '../../../packages/shared-types/contracts';
export type UpdateView=DesktopUpdateView;
function useUpdateView() {
  const [view,setView]=useState<UpdateView|null>(null);
  useEffect(()=>{
    let alive=true,pending=false;
    async function read(){if(pending)return;pending=true;try{const r=await window.dawloop.updates?.get();if(alive&&r?.ok)setView(r.data);}catch{}finally{pending=false;}}
    void read();const timer=setInterval(()=>void read(),5000);
    return()=>{alive=false;clearInterval(timer);};
  },[]);
  return [view,setView] as const;
}
export function UpdateIndicator({onOpen}:{onOpen:()=>void}) {
  const {i18n}=useTranslation();const [view]=useUpdateView();
  if(view?.status!=='UPDATE_AVAILABLE'||!view.release||view.publicPush!=='APPROVED')return null;
  return <button className="update-indicator" onClick={onOpen}><span aria-hidden="true">●</span> {i18n.language==='zh-CN'?'有新版本':'Update available'}</button>;
}
export function UpdateCenter({developer=false}:{developer?:boolean}) {
  const {i18n}=useTranslation();const zh=i18n.language==='zh-CN';
  const labels=zh?{title:'软件更新',version:'当前版本',check:'检查更新',enabled:'自动检查更新',toast:'允许 Windows 更新提示',channel:'更新频道',checked:'最近检查时间',unknown:'尚未检查',policy:'公开更新通知须经维护者批准。内部版本不会通知普通用户。',later:'稍后提醒',open:'查看更新与下载',error:'暂时无法检查更新，请稍后重试。你可以继续使用音乐功能。'}:
    {title:'Software updates',version:'Installed version',check:'Check for updates',enabled:'Automatically check for updates',toast:'Allow Windows update reminders',channel:'Update channel',checked:'Last check',unknown:'Not checked yet',policy:'Public update notifications require maintainer approval. Internal releases never notify ordinary users.',later:'Remind me later',open:'View update and download',error:'Unable to check right now. Try again later; your music workspace remains available.'};
  const statuses=zh?{UPDATE_AVAILABLE:'更新可用',UP_TO_DATE:'当前频道无更新',CHECK_FAILED:'检查失败',CHECK_DISABLED:'检查已关闭',UNKNOWN:'尚未确认'}:
    {UPDATE_AVAILABLE:'Update available',UP_TO_DATE:'No newer release in this channel',CHECK_FAILED:'Check failed',CHECK_DISABLED:'Check disabled',UNKNOWN:'Not confirmed'};
  const [view,setView]=useUpdateView(),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false);
  async function action(method:'check'|'configure'|'snooze'|'open',params?:object){setBusy(true);setFailed(false);try{const r=await window.dawloop.updates[method](params);if(!r.ok)throw Error();if(method!=='open')setView(r.data as UpdateView);}catch{setFailed(true);}finally{setBusy(false);}}
  return <section id="desktop-update-center" className="panel" aria-label={labels.title}><h3>{labels.title}</h3><p>{labels.version}: {view?.version??labels.unknown}</p>
    <p>{view?statuses[view.status]:labels.unknown}</p><p>{labels.checked}: {view?.checkedAt?new Date(view.checkedAt).toLocaleString(i18n.language):labels.unknown}</p>
    <p>{zh?'更新会在后台检查，不打断你的创作。':'Updates are checked in the background, without interrupting your work.'}</p>{developer&&<p>{labels.policy}</p>}{view&&<><label className="check"><input type="checkbox" checked={view.preferences.enabled} disabled={busy} onChange={e=>void action('configure',{enabled:e.target.checked})}/>{labels.enabled}</label>
      <label className="check"><input type="checkbox" checked={view.preferences.notifications} disabled={busy} onChange={e=>void action('configure',{notifications:e.target.checked})}/>{labels.toast}</label>
      <label>{labels.channel}<select aria-label={labels.channel} value={view.preferences.channel} disabled={busy} onChange={e=>void action('configure',{channel:e.target.value})}><option value="stable">Stable</option><option value="preview">Preview</option></select></label></>}
    <button disabled={busy||view?.preferences.enabled===false} onClick={()=>void action('check')}>{labels.check}</button>
    {view?.status==='UPDATE_AVAILABLE'&&view.release&&view.publicPush==='APPROVED'&&<div className="update-summary"><h4>DAWLoop {view.release.version}</h4><p>{zh?'新版本已准备好，你可以在方便时查看。':'A new version is ready to explore whenever you have time.'}</p><p>{new Date(view.release.publishedAt).toLocaleDateString(i18n.language)}</p><details><summary>{zh?'更新说明':'Release notes'}</summary><p style={{whiteSpace:'pre-wrap'}}>{view.release.notes}</p></details><div className="buttons"><button disabled={busy} onClick={()=>void action('open')}>{labels.open}</button><button disabled={busy} onClick={()=>void action('snooze')}>{labels.later}</button></div><small>{zh?'打开官方下载页；下载后解压到新目录，并按应用内引导配置组件。不会自动替换当前程序或删除你的数据。':'Opens the official download page. Extract to a new folder and follow the in-app component setup. Your app and data are not replaced automatically.'}</small></div>}
    {failed&&<p role="alert">{labels.error}</p>}</section>;
}
