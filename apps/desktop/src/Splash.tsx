import {useEffect,useRef,useState} from 'react';
import {useTranslation} from 'react-i18next';

export function Splash({version,ready,reduced=false}:{version?:string;ready:boolean;reduced?:boolean}){
  const {t}=useTranslation();const mark=useRef<HTMLDivElement>(null),overlay=useRef<HTMLDivElement>(null);
  const [finished,setFinished]=useState(false),[visible,setVisible]=useState(true);
  useEffect(()=>{
    const noMotion=reduced||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if(noMotion||!mark.current?.animate){setFinished(true);return;}
    const animation=mark.current.animate([{opacity:0},{opacity:1,offset:.25},{opacity:1,offset:.7},{opacity:0}],{duration:1000,fill:'both',easing:'linear'});
    animation.onfinish=()=>setFinished(true);return()=>animation.cancel();
  },[reduced]);
  useEffect(()=>{if(!ready||!visible)return;
    // 就绪后即可操作；字标的视觉片段不充当人为启动计时门。
    if(!finished)return;
    setVisible(false);
  },[ready,finished,visible]);
  if(!visible)return null;
  return <div ref={overlay} className={'brand-splash'+(ready?' ready':'')} aria-label={t('brandMotion.starting')} data-ready={ready} data-visual-finished={finished}>
    {!finished&&<div ref={mark} className="splash-wordmark">DAWLoop</div>}
    {finished&&!ready&&<p className="splash-loading" role="status">{t('brandMotion.loading')}</p>}
    <small className="splash-version">{version?'v'+version:t('brandMotion.versionPending')}</small>
  </div>;
}
