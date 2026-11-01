import type {Note,SymbolicScore} from '../../../packages/shared-types/music-contracts';

export type IdentifiedNote=Note&{id:string};
export type EditorScore=Omit<SymbolicScore,'notes'>&{notes:IdentifiedNote[]};
export interface EditorState {score:EditorScore;past:EditorScore[];future:EditorScore[];selected:string[];clipboard:IdentifiedNote[];error:string|null}
export const MAX_EDITOR_NOTES=20000;
export const MAX_EDITOR_HISTORY=40;
export function midiTick(beat:number):number {const value=beat*480,lower=Math.floor(value);return value-lower===.5?(lower%2===0?lower:lower+1):Math.round(value);}
const clone=<T,>(value:T):T=>structuredClone(value);
export function validateEditorNote(note:Note):boolean {
  return Number.isInteger(note.pitch)&&note.pitch>=0&&note.pitch<=127&&Number.isFinite(note.start)&&note.start>=0&&note.start<=86400&&Number.isFinite(note.duration)&&note.duration>0&&note.duration<=3600&&Number.isInteger(note.velocity)&&note.velocity>=1&&note.velocity<=127&&Number.isInteger(note.part)&&note.part>=0&&note.part<=15;
}
export function createEditor(score:SymbolicScore,id:()=>string=()=>crypto.randomUUID()):EditorState {
  if(!score||score.schemaVersion!==1||!Array.isArray(score.notes)||score.notes.length>MAX_EDITOR_NOTES||!score.notes.every(validateEditorNote)||!Number.isFinite(score.tempo)||score.tempo<20||score.tempo>300)throw Error('MI_SCORE_EDITOR_REJECTED');
  if(!Array.isArray(score.meter)||score.meter.length!==2||!Number.isInteger(score.meter[0])||score.meter[0]<1||score.meter[0]>32||![1,2,4,8,16,32].includes(score.meter[1])||!Array.isArray(score.tempoMap)||score.tempoMap.length>10000||score.tempoMap.some(p=>!Number.isFinite(p.start)||p.start<0||!Number.isFinite(p.bpm)||p.bpm<20||p.bpm>300)||!Array.isArray(score.edits)||score.edits.length>200)throw Error('MI_SCORE_EDITOR_REJECTED');
  const used=new Set<string>(),notes=score.notes.map(note=>{const existing=(note as Note&{id?:string}).id;const next=existing??id();if(typeof next!=='string'||!next||next.length>100||used.has(next))throw Error('MI_NOTE_ID_REJECTED');used.add(next);return {...clone(note),id:next};});
  return {score:{...clone(score),notes},past:[],future:[],selected:[],clipboard:[],error:null};
}
export function selectNotes(state:EditorState,ids:string[],toggle=false):EditorState {
  const known=new Set(state.score.notes.map(n=>n.id));let selected=ids.filter(id=>known.has(id));
  if(toggle){const set=new Set(state.selected);for(const id of selected)if(set.has(id))set.delete(id);else set.add(id);selected=[...set];}
  return {...state,selected:[...new Set(selected)],error:null};
}
// 历史只在提交事务时增长；拖动预览不写入原始 score 或撤销队列。
export function commitEditor(state:EditorState,notes:IdentifiedNote[],operation:string,affected:string[]):EditorState {
  const ids=notes.map(n=>n.id);if(notes.length>MAX_EDITOR_NOTES||new Set(ids).size!==ids.length||!notes.every(n=>typeof n.id==='string'&&n.id.length<=100&&validateEditorNote(n)&&midiTick(n.start+n.duration)>midiTick(n.start)))return {...state,error:'MI_SCORE_EDITOR_REJECTED'};
  if(JSON.stringify(notes)===JSON.stringify(state.score.notes))return {...state,error:null};
  const originalSource=state.score.provenance?.originalSource??state.score.source;
  const score:EditorScore={...clone(state.score),source:'USER_EDITED',notes:clone(notes),provenance:{...clone(state.score.provenance??{}),originalSource},edits:[...state.score.edits.slice(-199),{operation,noteIds:affected,at:new Date().toISOString()}]};
  // 弯音属于声部时间线，不能借编辑单个音符清空其他音符共享的事件。
  return {...state,score,past:[...state.past.slice(-(MAX_EDITOR_HISTORY-1)),clone(state.score)],future:[],selected:state.selected.filter(id=>ids.includes(id)),error:null};
}
export function patchNotes(state:EditorState,ids:string[],patch:Partial<Note>,operation='properties'):EditorState {
  if(Object.keys(patch).some(k=>!['pitch','start','duration','velocity','part'].includes(k)))return {...state,error:'MI_SCORE_EDITOR_REJECTED'};
  const selected=new Set(ids);return commitEditor(state,state.score.notes.map(n=>selected.has(n.id)?{...n,...patch,id:n.id}:n),operation,ids);
}
export function moveNotes(state:EditorState,ids:string[],beats:number,pitches:number):EditorState {
  if(!Number.isFinite(beats)||!Number.isInteger(pitches))return {...state,error:'MI_SCORE_EDITOR_REJECTED'};
  const notes=state.score.notes.filter(n=>ids.includes(n.id));if(!notes.length)return state;
  const deltaTime=Math.max(-Math.min(...notes.map(n=>n.start)),Math.min(beats,86400-Math.max(...notes.map(n=>n.start)))),deltaPitch=Math.max(-Math.min(...notes.map(n=>n.pitch)),Math.min(pitches,127-Math.max(...notes.map(n=>n.pitch))));
  return commitEditor(state,state.score.notes.map(n=>ids.includes(n.id)?{...n,start:n.start+deltaTime,pitch:n.pitch+deltaPitch}:n),'move',ids);
}
export function addEditorNote(state:EditorState,note:Note,id:()=>string=()=>crypto.randomUUID()):EditorState {
  const next={...clone(note),id:id()},committed=commitEditor(state,[...state.score.notes,next],'add',[next.id]);return committed.error?committed:selectNotes(committed,[next.id]);
}
export function deleteNotes(state:EditorState,ids=state.selected):EditorState {return commitEditor(state,state.score.notes.filter(n=>!ids.includes(n.id)),'delete',ids);}
export function copyNotes(state:EditorState):EditorState {return {...state,clipboard:clone(state.score.notes.filter(n=>state.selected.includes(n.id))),error:null};}
export function pasteNotes(state:EditorState,time:number,id:()=>string=()=>crypto.randomUUID()):EditorState {
  if(!state.clipboard.length)return state;if(!Number.isFinite(time)||time<0)return {...state,error:'MI_SCORE_EDITOR_REJECTED'};
  const first=Math.min(...state.clipboard.map(n=>n.start)),notes=state.clipboard.map(n=>({...clone(n),start:n.start-first+time,id:id()})),committed=commitEditor(state,[...state.score.notes,...notes],'paste',notes.map(n=>n.id));return committed.error?committed:selectNotes(committed,notes.map(n=>n.id));
}
export function undoEditor(state:EditorState):EditorState {const score=state.past.at(-1);return score?{...state,score:clone(score),past:state.past.slice(0,-1),future:[clone(state.score),...state.future].slice(0,MAX_EDITOR_HISTORY),selected:state.selected.filter(id=>score.notes.some(n=>n.id===id)),error:null}:state;}
export function redoEditor(state:EditorState):EditorState {const score=state.future[0];return score?{...state,score:clone(score),past:[...state.past.slice(-(MAX_EDITOR_HISTORY-1)),clone(state.score)],future:state.future.slice(1),selected:state.selected.filter(id=>score.notes.some(n=>n.id===id)),error:null}:state;}
export const snapBeat=(value:number,grid:number)=>grid>0?Math.round(value/grid)*grid:value;
export function hasPitchOverlap(score:SymbolicScore):boolean {
  const ends=new Map<string,number>();for(const note of [...score.notes].sort((a,b)=>a.start-b.start)){const key=`${note.part}:${note.pitch}`,end=ends.get(key)??-1;if(note.start<end)return true;ends.set(key,Math.max(end,note.start+note.duration));}return false;
}
