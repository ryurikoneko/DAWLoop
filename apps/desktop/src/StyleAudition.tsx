import {useEffect,useRef,useState} from 'react';
import {useTranslation} from 'react-i18next';
import type {MusicBridge} from '../../../packages/shared-types/music-contracts';

type Rating=Parameters<MusicBridge['styleAuditionRate']>[0]['ratings'];
const fields=['overall','rhythm','timbre','harmony','arrangement','reference'] as const;
const empty=()=>Object.fromEntries(fields.map(k=>[k,'unknown'])) as Rating;
export function StyleAudition(){
 const {i18n}=useTranslation();const zh=i18n.language==='zh-CN';
 const [pairs,setPairs]=useState<Array<{id:string;status:string;durationA:number;durationB:number;ratings:Rating|null}>>([]);
 const [index,setIndex]=useState(0),[ratings,setRatings]=useState<Rating>(empty),[error,setError]=useState(''),[busy,setBusy]=useState(false),[url,setUrl]=useState('');
 const [revealed,setRevealed]=useState<Awaited<ReturnType<MusicBridge['styleAuditionReveal']>> extends {data:infer D}?D:unknown>(null);
 const grant=useRef<{assetId:string;url:string}|null>(null);const audio=useRef<HTMLAudioElement>(null);
 async function release(){audio.current?.pause();if(grant.current){const old=grant.current;grant.current=null;await window.dawloop.music.releasePreview(old);}}
 useEffect(()=>()=>{void release();},[]);
 async function unwrap<T>(p:Promise<import('../../../packages/shared-types/contracts').Result<T>>){const r=await p;if(!r.ok)throw Error(r.error.code);return r.data;}
 async function act(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch{setError(zh?'无法读取听审清单，请确认研究目录包含本轮清单。':'Could not read the listening study. Check that this research folder contains the study.');}finally{setBusy(false);}}
 async function play(side:'a'|'b'){await release();const g=await unwrap(window.dawloop.music.styleAuditionPreview({pair:pairs[index].id,side}));grant.current=g;setUrl(g.url);}
 async function move(next:number){await release();setUrl('');setIndex(next);setRatings(pairs[next]?.ratings??empty());setRevealed(null);}
 const labels=zh?['整体听感','节奏','音色','和声','编曲','愿意加入参考库']:['Overall sound','Rhythm','Timbre','Harmony','Arrangement','Add to my references'];
 const pair=pairs[index];
 return <section className="panel" aria-label={zh?'片段盲听':'Blind listening'}><h3>{zh?'片段盲听':'Blind listening'}</h3><p>{zh?'先试听 A 和 B，再记录你的感受。歌曲信息与模型分数可在听后展开。':'Listen to A and B, then record your impression. Reveal song information and model scores after listening.'}</p>
 <button disabled={busy} onClick={()=>void act(async()=>{await move(0);const list=await unwrap(window.dawloop.music.styleAuditionList({}));setPairs(list);setRatings(list[0]?.ratings??empty());})}>{zh?'打开听审清单':'Open listening study'}</button>
 {error&&<p role="alert">{error}</p>}
 {pair&&<><p>{index+1} / {pairs.length} · {pair.status==='RATED'?(zh?'已记录':'Recorded'):(zh?'待试听':'Awaiting review')}</p><div className="buttons"><button disabled={busy} onClick={()=>void act(()=>play('a'))}>{zh?'试听 A':'Play A'} ({pair.durationA.toFixed(1)}s)</button><button disabled={busy} onClick={()=>void act(()=>play('b'))}>{zh?'试听 B':'Play B'} ({pair.durationB.toFixed(1)}s)</button></div>
 {url&&<audio ref={audio} key={url} src={url} autoPlay controls/>}
 <div className="form-grid">{fields.map((field,i)=><label key={field}>{labels[i]}<select aria-label={labels[i]} value={ratings[field]} onChange={e=>setRatings(v=>({...v,[field]:e.target.value as Rating[typeof field]}))}><option value="unknown">{zh?'无法判断':'Unsure'}</option><option value="similar">{field==='reference'?(zh?'喜欢，加入':'Like / include'):(zh?'相似':'Similar')}</option><option value="different">{field==='reference'?(zh?'不喜欢，不加入':'Dislike / exclude'):(zh?'不同':'Different')}</option></select></label>)}</div>
 <div className="buttons"><button disabled={busy} onClick={()=>void act(async()=>{await unwrap(window.dawloop.music.styleAuditionRate({pair:pair.id,ratings}));setPairs(await unwrap(window.dawloop.music.styleAuditionList({})));})}>{zh?'保存听审记录':'Save listening review'}</button><button disabled={busy} onClick={()=>void act(async()=>setRevealed(await unwrap(window.dawloop.music.styleAuditionReveal({pair:pair.id}))))}>{zh?'展开歌曲信息与分数':'Reveal songs and score'}</button><button disabled={busy||index===0} onClick={()=>void act(()=>move(index-1))}>{zh?'上一组':'Previous pair'}</button><button disabled={busy||index===pairs.length-1} onClick={()=>void act(()=>move(index+1))}>{zh?'下一组':'Next pair'}</button></div>
 {revealed!=null&&<PairDetails value={revealed} zh={zh}/>}</>}
 </section>;
}
function PairDetails({value,zh}:{value:unknown;zh:boolean}){const p=value as {a:{name:string;start:number;end:number};b:{name:string;start:number;end:number};score:number};return <div>{(['a','b'] as const).map(k=><p key={k}>{k.toUpperCase()}: {p[k].name} · {p[k].start.toFixed(1)}–{p[k].end.toFixed(1)}s</p>)}<p>{zh?'原始余弦值':'Raw cosine'}: {p.score.toFixed(6)}</p></div>;}
