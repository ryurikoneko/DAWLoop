import {useTranslation} from 'react-i18next';
import type {Asset,Analysis} from '../../../packages/shared-types/music-contracts';
import type {AnalysisFieldV0_5,MusicAnalysisResultV0_5} from '../../../packages/shared-types/analysis-contracts';
import {analysisUnit,boundAnalysis,explainAnalysis,overviewFields,series} from './analysis-view';
import {AnalysisChart} from './AnalysisChart';

function reading(field:AnalysisFieldV0_5):string {
  if(field.status!=='READY'||field.value===null)return '—';
  if(typeof field.value==='number')return Number.isFinite(field.value)?Number(field.value.toPrecision(5)).toString():'—';
  if(['beats','onsets'].includes(field.name)&&Array.isArray(field.value))return String(field.value.length);
  if(field.name==='bpmCandidates'&&Array.isArray(field.value))return field.value.map(v=>Number(v).toFixed(2)).join(', ')||'—';
  if(field.name==='tonalCandidates'&&Array.isArray(field.value))return field.value.map(v=>{const row=v as {pitchClass:number;strength:number};return `${['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'][row.pitchClass]} (${row.strength.toFixed(3)})`;}).join(', ')||'—';
  const points=series(field);if(points.length)return `${Math.min(...points.map(p=>p[1])).toPrecision(4)}–${Math.max(...points.map(p=>p[1])).toPrecision(4)}`;
  return '—';
}
export function AnalysisOverview({analysis,record,asset,developer,charts=false,state='READY',onSeek}:{analysis:Analysis|null;record:MusicAnalysisResultV0_5|null;asset:Asset|undefined;developer:boolean;charts?:boolean;state?:string;onSeek?:(time:number)=>void}) {
  const {t}=useTranslation('music'),bound=boundAnalysis(analysis,record,asset);
  if(!bound)return <p role="status">{t(analysis?'ux04.bindingPending':'noAnalysis')}</p>;
  const range=bound.asset.windowRange??bound.fields.find(f=>f.name==='energy')?.range;
  const find=(name:string)=>bound.fields.find(f=>f.name===name),bpm=find('bpmCandidates'),key=find('key'),lufs=find('lufs'),peak=find('samplePeakDbfs');
  const primary=key?.status==='READY'?key.value as unknown as {tonic:number;mode:string}:null;
  const pitchNames=['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'];
  const formatTime=(seconds:number)=>Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0');
  const metric=(name:string,value:string,notice?:string)=><article className="mi-metric" key={name}><h4>{t('song.'+name)}</h4><strong>{value}</strong>{notice&&<small> · {notice}</small>}</article>;
  const observations=explainAnalysis(bound);
  return <section aria-label={t('ux04.machineSummary')}><h3>{t('ux04.machineSummary')}</h3><p><strong>{asset?.name}</strong> · {range?t('ux04.window',{start:range[0].toFixed(3),end:range[1].toFixed(3)}):t('unknown')} · {t('ux04.analysisStates.'+state)}</p>
    {range&&(range[0]>0||range[1]<bound.asset.duration!-.01)&&<p>{t('song.partial')}</p>}
    <div className="mi-metric-grid mi-song-overview">
      {metric('bpm',bpm?.status==='READY'&&Array.isArray(bpm.value)&&bpm.value.length?Math.round(Number(bpm.value[0]))+' BPM':t('song.uncertain'),bpm?.status==='READY'&&Array.isArray(bpm.value)&&bpm.value.length?t('song.estimated'):undefined)}
      {metric('key',primary?pitchNames[primary.tonic]+' '+t('song.'+primary.mode):t('song.keyUnknown'),primary?t('song.estimated'):undefined)}
      {lufs?.status==='READY'&&typeof lufs.value==='number'?metric('lufs',lufs.value.toFixed(1)+' LUFS'):null}
      {metric('peak',peak?.status==='READY'&&typeof peak.value==='number'?peak.value.toFixed(1)+' dBFS':'—')}
      {metric('duration',bound.asset.duration===null?t('unknown'):formatTime(bound.asset.duration))}
      {range&&metric('coverage',formatTime(range[0])+'–'+formatTime(range[1]))}
    </div>
    {lufs?.status!=='READY'&&<p>{t('song.lufsUnavailable')} · {t('song.lufsReasons.'+(lufs?.reasonCode??'MI_LUFS_STANDARD_NOT_READY'))}</p>}
    <h4>{t('song.changes')}</h4><ul>{observations.map(o=><li key={o.key}>{t('song.rules.'+o.key,Object.fromEntries(Object.entries(o.values).map(([k,v])=>[k,k==='time'?formatTime(v):Number(v.toFixed(2))])))} {onSeek&&o.key==='fluxMaximum'&&<button onClick={()=>onSeek(o.values.time)}>{t('song.listenHere')}</button>}{developer&&<code>{o.origin} · {o.sourceFields.join(', ')}</code>}</li>)}</ul>
    {charts&&['energy','spectralCentroid','spectralFlux'].map(name=>{const f=find(name);return f?<AnalysisChart key={name} field={f} onSeek={onSeek}/>:<p key={name}>{t('ux04.chartUnavailable',{name:t('ux04.metrics.'+name)})}</p>;})}
    <details className="mi-measurement-details"><summary>{t('song.details')}</summary>{Array.isArray(find('keyCandidates')?.value)&&<p>{t('song.keyAlternatives')}: {(find('keyCandidates')!.value as unknown as {tonic:number;mode:string;score:number}[]).slice(0,3).map(k=>pitchNames[k.tonic]+' '+t('song.'+k.mode)+(developer?' ('+k.score.toFixed(4)+')':'')).join(' / ')}</p>}<div className="mi-metric-grid">{overviewFields.map(name=>{const field=find(name);return <article key={name} className="mi-metric"><h4>{t('ux04.metrics.'+name)}</h4><strong>{field?reading(field):'—'}</strong> <small>{analysisUnit(field?.unit,k=>t(k))}</small><p>{t('ux04.metricHelp.'+name)}</p>{developer&&field&&<details><summary>{t('technicalDetails')}</summary><pre>{JSON.stringify(field,null,2)}</pre></details>}</article>;})}</div>{developer&&<pre>{JSON.stringify(bound,null,2)}</pre>}</details>
  </section>;
}
