import {WholeSong} from './WholeSong';
import {StyleAudition} from './StyleAudition';
import {useRef,useState,useEffect} from 'react';
import {useTranslation} from 'react-i18next';
import type {StyleSegment,StyleCandidate} from '../../../packages/shared-types/music-contracts';

export function StyleLab(){
 const {i18n}=useTranslation();const zh=i18n.language==='zh-CN';
 const [segments,setSegments]=useState<StyleSegment[]>([]);const [query,setQuery]=useState('');const [scope,setScope]=useState<'cross'|'within'>('cross');const [results,setResults]=useState<StyleCandidate[]>([]);const [liked,setLiked]=useState<string[]>([]);const [name,setName]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [audio,setAudio]=useState('');const grant=useRef<{assetId:string;url:string}|null>(null);
 async function release(){if(grant.current){await window.dawloop.music.releasePreview(grant.current);grant.current=null;}}
 useEffect(()=>()=>{void release();},[]);
 async function act(work:()=>Promise<void>){setBusy(true);setError('');try{await work();}catch{setError(zh?'未能完成。请检查研究库及音频分析组件，再重试。':'Could not complete. Check the research library and audio components, then retry.');}finally{setBusy(false);}}
 async function unwrap<T>(p:Promise<import('../../../packages/shared-types/contracts').Result<T>>){const r=await p;if(!r.ok)throw Error(r.error.code);return r.data;}
 async function play(id:string){await release();const next=await unwrap(window.dawloop.music.stylePreview({id}));grant.current=next;setAudio(next.url);}
 return <section className="panel"><h3>Style Lab</h3><p>{zh?'选择参考片段，寻找值得试听比较的音乐，再收藏喜欢的部分。':'Choose a reference excerpt, discover listening comparisons and save your favorites.'}</p>
 <button disabled={busy} onClick={()=>void act(async()=>{const list=await unwrap(window.dawloop.music.styleOpen());if(list){await release();setAudio('');setSegments(list);setQuery(list[0]?.id??'');setResults([]);setLiked([]);}})}>{zh?'打开研究资料库':'Open research library'}</button>
 {!segments.length&&<p>{zh?'打开已完成向量分析的本地研究目录。首次计算通过当前研究入口完成。':'Open a local research folder with completed embeddings. Initial computation uses the research entry point.'}</p>}
 {!!segments.length&&<><StyleAudition key={segments[0].id}/><WholeSong segments={segments}/></>}
 {error&&<p role="alert">{error}</p>}
 {!!segments.length&&<><label>{zh?'参考片段':'Reference excerpt'}<select value={query} onChange={e=>{setQuery(e.target.value);setResults([]);}}>{segments.map(s=><option key={s.id} value={s.id}>{s.name} · {s.start.toFixed(1)}–{s.end.toFixed(1)}s</option>)}</select></label><div className="buttons"><button disabled={busy} onClick={()=>void act(()=>play(query))}>{zh?'试听参考':'Play reference'}</button><select aria-label={zh?'检索范围':'Search scope'} value={scope} onChange={e=>setScope(e.target.value as 'cross'|'within')}><option value="cross">{zh?'其他歌曲':'Other songs'}</option><option value="within">{zh?'同一歌曲':'Same song'}</option></select><button disabled={busy} onClick={()=>void act(async()=>setResults(await unwrap(window.dawloop.music.styleSearch({query,scope}))))}>{zh?'搜索相似片段':'Find similar excerpts'}</button></div></>}
 {audio&&<audio key={audio} src={audio} controls autoPlay/>}
 {results.map(r=><div className="panel" key={r.id}><strong>{r.name}</strong><p>{r.start.toFixed(1)}–{r.end.toFixed(1)}s · {zh?'向量接近度':'Vector similarity'} {r.cosine.toFixed(3)}</p><div className="buttons"><button disabled={busy} onClick={()=>void act(()=>play(r.id))}>{zh?'试听比较':'Listen'}</button><button disabled={busy} onClick={()=>void act(async()=>{await unwrap(window.dawloop.music.styleFeedback({query,candidate:r.id,liked:1}));setLiked(v=>[...new Set([...v,r.id])]);setResults(await unwrap(window.dawloop.music.styleSearch({query,scope})));})}>{zh?'喜欢':'Like'}</button><button disabled={busy} onClick={()=>void act(async()=>{await unwrap(window.dawloop.music.styleFeedback({query,candidate:r.id,liked:-1}));setLiked(v=>v.filter(id=>id!==r.id));setResults(await unwrap(window.dawloop.music.styleSearch({query,scope})));})}>{zh?'不喜欢':'Dislike'}</button></div></div>)}
 {!!liked.length&&<><label>{zh?'画像名称':'Profile name'}<input value={name} onChange={e=>setName(e.target.value)}/></label><button disabled={busy||!name.trim()} onClick={()=>void act(async()=>{await unwrap(window.dawloop.music.styleProfile({name:name.trim(),segments:liked}));setLiked([]);})}>{zh?'将喜欢的片段保存为画像':'Save favorites as a profile'}</button></>}
 </section>;
}
