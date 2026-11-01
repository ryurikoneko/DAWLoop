import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { Config, DesktopEnvironment, DesktopMethodMap, DesktopArgs } from '../../../packages/shared-types/contracts';

async function call<K extends keyof DesktopMethodMap>(method:K,...args:DesktopArgs<K>) {
  const result=await window.dawloop.call(method,...args);if(!result.ok)throw Error(result.error.code);return result.data;
}
export function FirstRun({config,environment,onSaved}:{config:Config;environment:DesktopEnvironment;onSaved:(config:Config)=>void}) {
  const {t,i18n}=useTranslation();const [candidate,setCandidate]=useState(config.host.executablePath);
  const [valid,setValid]=useState(false);const [checked,setChecked]=useState(false);const [busy,setBusy]=useState(true);const [error,setError]=useState('');
  useEffect(()=>{let current=true;void call('testHostPath',config.host.executablePath).then(result=>{if(current){setValid(result.valid);setChecked(true);setBusy(false);}}).catch(()=>{if(current){setError('IPC_REJECTED');setBusy(false);}});return()=>{current=false;};},[]);
  async function perform(task:()=>Promise<void>) {setBusy(true);setError('');try{await task();}catch(e){setError(e instanceof Error?e.message:'INTERNAL_ERROR');}finally{setBusy(false);}}
  async function finish(savePath:boolean) {
    const next=await call('updateConfig',{...(savePath?{host:{executablePath:candidate}}:{}),ui:{onboardingCompleted:true}});onSaved(next);
  }
  return <section className="panel" aria-label={t('setup.title')}><h2>{t('setup.title')}</h2><p>{t('setup.internal')}</p>
    <label>{t('settings:language')} <select aria-label={t('setup.language')} value={i18n.language} disabled={busy} onChange={e=>void perform(async()=>{const language=e.target.value as 'zh-CN'|'en-US';const next=await call('updateConfig',{ui:{language}});onSaved(next);await i18n.changeLanguage(language);})}><option value="zh-CN">{t('languageNames.zh-CN')}</option><option value="en-US">{t('languageNames.en-US')}</option></select></label>
    <p>{t('ux.startMusicNote')}</p><details><summary>{t('ux.flOptional')}</summary><p>{t('setup.pathNote')}</p><div className="buttons"><input aria-label={t('setup.path')} value={candidate} maxLength={4096} disabled={busy} onChange={e=>{setCandidate(e.target.value);setValid(false);setChecked(false);}}/>
      <button disabled={busy} onClick={()=>void perform(async()=>{const result=await window.dawloop.browseHost();if(!result.ok)throw Error(result.error.code);if(result.data){setCandidate(result.data);setValid(false);setChecked(false);}})}>{t('setup.browse')}</button>
      <button disabled={busy} onClick={()=>void perform(async()=>{const result=await call('testHostPath',candidate);setValid(result.valid);setChecked(true);})}>{t('setup.check')}</button></div>
    {checked && <p role="status">{t(valid?'setup.pathValid':'setup.pathMissing')}</p>}
    <ul><li>{t(`setup.python.${environment.dependencies?.python??'not-bundled'}`)}</li><li>{t('setup.core')}</li><li>{t(`setup.controllerStates.${environment.dependencies?.controller??'not-probed'}`)}</li></ul></details>
    {error && <p role="alert">{t(`errorCodes.${error}`,{defaultValue:t('fallback.error')})}</p>}
    <div className="buttons"><button disabled={busy||!valid} onClick={()=>void perform(()=>finish(true))}>{t('setup.continue')}</button><button disabled={busy} onClick={()=>void perform(()=>finish(false))}>{t('setup.desktopOnly')}</button></div>
  </section>;
}
