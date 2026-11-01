import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { WorldSnapshot } from '../../../packages/shared-types/contracts';

export function WorldView({ mode, developer=true }: {mode:'session'|'mixer'|'diagnostics';developer?:boolean}) {
  const {t}=useTranslation('mixer');
  const [world,setWorld]=useState<WorldSnapshot|null>(null);
  const [selected,setSelected]=useState<string|null>(null); const [parameterPage,setParameterPage]=useState(0);
  useEffect(()=>{
    let active=true, pending=false;
    async function read() {
      if (pending) return; pending=true;
      try {
        const result=await window.dawloop.call('getWorldSnapshot');
        let next=result.ok && result.data?.apiVersion===1 ? result.data : null;
        if (next?.state==='current' && (!next.observedAt || Date.now()-Date.parse(next.observedAt)<0 || Date.now()-Date.parse(next.observedAt)>15000 || !Number.isFinite(Date.parse(next.observedAt)))) next={...next,state:'stale',presentation:next.source==='mock'?'development-mock':'real-cached',session:null,target:null,tracks:[],capabilities:[]};
        if (active) setWorld(next);
      }
      catch { if (active) setWorld(null); } finally { pending=false; }
    }
    void read(); const timer=setInterval(()=>void read(),4000);
    return ()=>{active=false;clearInterval(timer);};
  },[]);
  useEffect(()=>{
    if (!world || world.state!=='current' || !world.observedAt) return;
    const observedAt=world.observedAt;
    const timer=setTimeout(()=>setWorld(previous=>previous?.observedAt===observedAt ? {...previous,state:'stale',presentation:previous.source==='mock'?'development-mock':'real-cached',reason:'WORLD_SNAPSHOT_STALE',session:null,target:null,tracks:[],capabilities:[]} : previous),Math.max(0,Date.parse(observedAt)+15000-Date.now()));
    return ()=>clearTimeout(timer);
  },[world]);
  const u=t('world.unknown');
  const plugins=world?.tracks.flatMap(track=>track.slots.flatMap(slot=>slot.plugin ? [{track,slot,plugin:slot.plugin,key:`${world.session?.hostId}:${world.session?.sessionId}:${world.session?.projectGeneration}:${track.index}:${slot.index}:${slot.plugin.instanceId}`}] : [])) ?? [];
  const selection=plugins.find(p=>p.key===selected);
  return <>
    <section className="panel"><h3>{t('world.session')}</h3><p>{t(`world.presentation.${world?.presentation ?? 'unavailable'}`)}</p><p>{t(`world.${world?.state ?? 'unknown'}`)}</p>
      {developer && world?.publisher && <><div className="row"><span>{t('world.sequence')}</span><span>{world.publisher.sequence}</span></div>
        {Object.entries(world.publisher.levels).map(([level,state])=><div className="row" key={level}><span>{t(`world.levels.${level}`)}</span><span>{t(`world.levelStates.${state}`)}</span></div>)}</>}
      <div className="row"><span>{t('world.project')}</span><span>{world?.session?.projectName ?? u}</span></div>
      {developer && <><div className="row"><span>{t('world.host')}</span><code>{world?.session?.hostId ?? u}</code></div>
      <div className="row"><span>{t('world.session')}</span><code>{world?.session?.sessionId ?? u}</code></div>
      <div className="row"><span>{t('world.generation')}</span><code>{world?.session?.projectGeneration ?? u}</code></div></>}
      <div className="row"><span>{t('world.target')}</span><span>{world?.target ? `${t('world.track')} ${world.target.trackIndex} / ${t('world.slot')} ${world.target.slotIndex}` : u}</span></div>
      <div className="row"><span>{t('world.observed')}</span><span>{world?.observedAt ?? u}</span></div>
      <p title={world?.reason}>{t('world.reason')}: {t(`world.reasons.${world?.reason ?? 'WORLD_SNAPSHOT_UNAVAILABLE'}`,{defaultValue:u})}</p>
    </section>
    {mode==='mixer' && <><section className="panel">
      {!world?.tracks.length && <p>{t('world.noTracks')}</p>}
      {world?.tracks.map(track=><div key={track.index}><h3>{t('world.track')} {track.index} · {track.name}</h3>
        {track.slots.map(slot=><div className="row" key={slot.index}><span>{t('world.slot')} {slot.index}</span>
          {slot.plugin ? <button onClick={()=>{setSelected(plugins.find(p=>p.track.index===track.index && p.slot.index===slot.index)!.key);setParameterPage(0);}}>{slot.plugin.name}</button> : <span>{t(`world.${slot.state==='empty'?'empty':'unknown'}`)}</span>}
        </div>)}
      </div>)}
    </section><section className="panel"><h3>{t('world.inspector')}</h3>
      {selection ? <><p>{t('world.name')}: {selection.plugin.name}</p><p>{t('world.identity')}: {t(selection.plugin.identityVerified?'world.verified':'world.unverified')}</p>
        <p>{t('world.track')}: {selection.track.index} / {t('world.slot')}: {selection.slot.index}</p>{developer && <p>{t('world.instance')}: {selection.plugin.instanceId ?? u}</p>}
        <p>{t('world.count')}: {selection.plugin.parameterCount ?? u}</p><p>{t('world.layout')}: {t(selection.plugin.layoutReadable?'world.available':'world.notReady')}</p>
        <p>{t('world.read')}: {t(selection.plugin.valuesReadable?'world.available':'world.notReady')}</p><p>{t('world.write')}: {t('world.disabled')}</p>
        {selection.plugin.parameters.slice(parameterPage*100,(parameterPage+1)*100).map(p=><div className="row" key={p.index}><span>{p.index} · {p.name}</span><span>{t('world.value')}: {p.value ?? u}</span></div>)}
        {selection.plugin.parameters.length>100 && <div className="buttons"><button disabled={parameterPage===0} onClick={()=>setParameterPage(p=>p-1)}>{t('world.previous')}</button><span>{parameterPage+1} / {Math.ceil(selection.plugin.parameters.length/100)}</span><button disabled={(parameterPage+1)*100>=selection.plugin.parameters.length} onClick={()=>setParameterPage(p=>p+1)}>{t('world.next')}</button></div>}
      </> : <p>{t('world.choose')}</p>}
    </section></>}
    {mode==='diagnostics' && developer && <section className="panel"><h3>{t('world.evidence')}</h3>
      {!world?.capabilities.length && <p>{u}</p>}
      {world?.capabilities.map(c=><div key={c.id}><h3>{c.id}</h3><p>{t(`common:status.${c.state}`)} · {t(`world.confidence.${c.confidence}`)}</p>
        {Object.entries(c.promotion).map(([stage,passed])=><div className="row" key={stage}><span>{t(`world.${stage}`)}</span><span>{t(passed?'world.passed':'world.blocked')}</span></div>)}
        {c.evidence.map(e=><p key={e.id}><code>{e.id}</code> · {t(e.outcome==='passed'?'world.passed':e.outcome==='failed'?'world.blocked':'world.unknown')} · {e.observedAt}<br/><code>{e.sha256}</code></p>)}
      </div>)}
    </section>}
  </>;
}
