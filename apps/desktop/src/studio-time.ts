import type {TranscriptionSession,StudioTrack} from '../../../packages/shared-types/transcription-contracts';
import type {SymbolicScore} from '../../../packages/shared-types/music-contracts';
import {secondsAtBeat,beatAtSeconds} from './score-time';
export function studioMeter(s:TranscriptionSession):number[]{const counts=new Map<string,number>();for(const b of s.beats){const key=`${b[2]}/${b[3]}`;counts.set(key,(counts.get(key)??0)+1);}return [...counts].sort((a,b)=>b[1]-a[1])[0]?.[0].split('/').map(Number)??[4,4];}
export function studioBpm(s:TranscriptionSession):number|undefined{const values=s.tempo.map(t=>t.bpm).filter(v=>v>=20&&v<=300).sort((a,b)=>a-b);return values.length?values[Math.floor(values.length/2)]:undefined;}
export function studioClock(s:TranscriptionSession):SymbolicScore{
 const tempo=s.tempo.length?s.tempo:[{time:0,bpm:120}];let beat=0,previous=0,bpm=tempo[0].bpm;
 const map=tempo.map(p=>{beat+=(p.time-previous)*bpm/60;previous=p.time;bpm=p.bpm;return {start:beat,bpm:p.bpm};});
 return {schemaVersion:1,tempo:tempo[0].bpm,meter:studioMeter(s),tempoMap:map,notes:[],source:'MODEL_PREDICTION',edits:[]};
}
export function trackScore(s:TranscriptionSession,t:StudioTrack):SymbolicScore{const clock=studioClock(s);return {...clock,notes:t.notes.map(n=>({id:n.id,pitch:n.pitch,start:beatAtSeconds(clock,n.start),duration:beatAtSeconds(clock,n.end)-beatAtSeconds(clock,n.start),velocity:n.velocity,part:0}))};}
export function scoreTrack(s:TranscriptionSession,t:StudioTrack,score:SymbolicScore):StudioTrack{return {...t,notes:score.notes.map((n,i)=>({id:n.id??`${t.id}-${i}`,pitch:n.pitch,start:secondsAtBeat(score,n.start),end:secondsAtBeat(score,n.start+n.duration),velocity:n.velocity}))};}
