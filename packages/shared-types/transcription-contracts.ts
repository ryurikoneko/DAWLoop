import type {Result} from './contracts';
export type StudioTrackId='vocal'|'melody'|'chords'|'bass'|'combined';
export interface StudioNote {id:string;pitch:number;start:number;end:number;velocity:number}
export interface StudioTrack {id:Exclude<StudioTrackId,'combined'>;notes:StudioNote[];provenance:string}
export interface TranscriptionSession {schemaVersion:1;id:string;revision:number;name:string;assetId:string;duration:number;peaks:number[];state:string;stage:string;error?:string;tempo:{time:number;bpm:number}[];beats:(string|number)[][];keys:string[][];structure:string[][];chords:{start:number;end:number;label:string;voicing?:string;confidence?:string}[];tracks:StudioTrack[];rawDirectory?:string;modelVersions:Record<string,string>;edited:boolean;exports:Record<string,{token:string;notes:number;maxErrorSeconds:number}>}
export interface StudioBridge {call(method:string,params?:unknown):Promise<Result<unknown>>;drop(files:File[]):Promise<Result<unknown>>;drag(params:{id:string;revision:number;track:StudioTrackId;token:string}):Promise<Result<{nativeStarted:boolean}>>}
