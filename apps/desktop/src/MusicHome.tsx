import {useEffect,useState} from 'react';
import {useTranslation} from 'react-i18next';
import type {Asset} from '../../../packages/shared-types/music-contracts';
import type {MusicEntry} from './MusicIntelligence';

export function MusicHome({open}:{open:(tab:MusicEntry['tab'],assetId?:string,importAudio?:boolean)=>void}) {
  const {t}=useTranslation();const [assets,setAssets]=useState<Asset[]>([]);const [unavailable,setUnavailable]=useState(false);
  useEffect(()=>{let current=true;void window.dawloop.music?.status().then(r=>{if(!current)return;if(r.ok)setAssets(r.data.assets);else setUnavailable(true);}).catch(()=>{if(current)setUnavailable(true);});return()=>{current=false;};},[]);
  return <section className="panel"><h2>{t('ux.welcome')}</h2><p>{t('ux.welcomeNote')}</p><div className="task-grid">
    <button onClick={()=>open('library',undefined,true)}>{t('ux.importMusic')}</button>
    <button onClick={()=>open('library')}>{t('ux.openLibrary')}</button>
    <button onClick={()=>open('analysis')}>{t('ux.analyzeMusic')}</button>
    <button onClick={()=>open('score')}>{t('ux.audioToMidi')}</button>
  </div><h3>{t('ux.recentMusic')}</h3>{assets.slice(-5).reverse().map(a=><div className="row" key={a.id}><button onClick={()=>open('analysis',a.id)}>{a.name}</button></div>)}{!assets.length&&<p>{t(unavailable?'ux.libraryUnavailable':'ux.noRecentMusic')}</p>}</section>;
}
