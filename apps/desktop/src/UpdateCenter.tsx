// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 ryurikoneko
import {useEffect,useState} from 'react';
import {useTranslation} from 'react-i18next';
import type {DesktopUpdateView} from '../../../packages/shared-types/contracts';
export type UpdateView=DesktopUpdateView;
export function UpdateCenter() {
  const {i18n}=useTranslation();const zh=i18n.language==='zh-CN';
  const labels=zh?{title:'关于 DAWLoop',version:'当前版本',check:'检查更新',enabled:'启动时检查更新',toast:'Windows 更新通知',channel:'更新频道',checked:'最近检查时间',unknown:'尚未确认',policy:'公开更新通知须经维护者批准。内部版本不会通知普通用户。',later:'稍后提醒',open:'查看更新内容',error:'检查失败，音乐工作区仍可使用。'}:
    {title:'About DAWLoop',version:'Installed version',check:'Check for updates',enabled:'Check on startup',toast:'Windows update notifications',channel:'Update channel',checked:'Last check',unknown:'Not confirmed',policy:'Public update notifications require maintainer approval. Internal releases never notify ordinary users.',later:'Remind me later',open:'View release notes',error:'Check failed. Your music workspace remains available.'};
  const statuses=zh?{UPDATE_AVAILABLE:'更新可用',UP_TO_DATE:'当前频道无更新',CHECK_FAILED:'检查失败',CHECK_DISABLED:'检查已关闭',UNKNOWN:'尚未确认'}:
    {UPDATE_AVAILABLE:'Update available',UP_TO_DATE:'No newer release in this channel',CHECK_FAILED:'Check failed',CHECK_DISABLED:'Check disabled',UNKNOWN:'Not confirmed'};
  const [view,setView]=useState<UpdateView|null>(null),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false);
  useEffect(()=>{let alive=true;window.dawloop.updates?.get().then(r=>{if(alive&&r.ok)setView(r.data);}).catch(()=>{if(alive)setFailed(true);});return()=>{alive=false;};},[]);
  async function action(method:'check'|'configure'|'snooze'|'open',params?:object){setBusy(true);setFailed(false);try{const r=await window.dawloop.updates[method](params);if(!r.ok)throw Error();if(method!=='open')setView(r.data as UpdateView);}catch{setFailed(true);}finally{setBusy(false);}}
  return <section className="panel" aria-label={labels.title}><h3>{labels.title}</h3><p>{labels.version}: {view?.version??labels.unknown}</p>
    <p>{view?statuses[view.status]:labels.unknown}</p><p>{labels.checked}: {view?.checkedAt?new Date(view.checkedAt).toLocaleString(i18n.language):labels.unknown}</p>
    <p>{labels.policy}</p>{view&&<><label className="check"><input type="checkbox" checked={view.preferences.enabled} disabled={busy} onChange={e=>void action('configure',{enabled:e.target.checked})}/>{labels.enabled}</label>
      <label className="check"><input type="checkbox" checked={view.preferences.notifications} disabled={busy} onChange={e=>void action('configure',{notifications:e.target.checked})}/>{labels.toast}</label>
      <label>{labels.channel}<select aria-label={labels.channel} value={view.preferences.channel} disabled={busy} onChange={e=>void action('configure',{channel:e.target.value})}><option value="stable">Stable</option><option value="preview">Preview</option></select></label></>}
    <button disabled={busy||view?.preferences.enabled===false} onClick={()=>void action('check')}>{labels.check}</button>
    {view?.status==='UPDATE_AVAILABLE'&&view.release&&<><h4>DAWLoop {view.release.version}</h4><p>{new Date(view.release.publishedAt).toLocaleDateString(i18n.language)}</p><p style={{whiteSpace:'pre-wrap'}}>{view.release.notes}</p><button disabled={busy} onClick={()=>void action('open')}>{labels.open}</button><button disabled={busy} onClick={()=>void action('snooze')}>{labels.later}</button></>}
    {failed&&<p role="alert">{labels.error}</p>}</section>;
}
