import test from 'node:test';
import assert from 'node:assert/strict';
import {TranscriptionStudio,validateStudioTracks} from '../../packages/music-intelligence/transcription-studio.mjs';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const tracks=[{id:'vocal',notes:[{id:'a',pitch:60,start:.123,end:.789,velocity:100}],provenance:'MODEL_PREDICTION'}];
test('秒轴校验保留自由节奏，拒绝非法时值及重复轨道',()=>{assert.equal(validateStudioTracks(tracks),tracks);assert.throws(()=>validateStudioTracks([...tracks,...tracks]));assert.throws(()=>validateStudioTracks([{...tracks[0],notes:[{...tracks[0].notes[0],end:.1}]}]));assert.throws(()=>validateStudioTracks([{...tracks[0],notes:[{...tracks[0].notes[0],pitch:128}]}]));});
test('取消环境核验中的任务后不能迟到启动模型，重启保留取消状态',async()=>{const home=await fs.mkdtemp(path.join(os.tmpdir(),'dawloop-studio-cancel-'));const st=new TranscriptionStudio({home});await st.initialize();const s={id:'a'.repeat(32),schemaVersion:1,tracks:[],state:'IMPORTED',exports:{}};st.sessions.set(s.id,s);await fs.mkdir(st.dir(s));await fs.writeFile(path.join(st.dir(s),'input.wav'),'TEST_FIXTURE');let release,entered;const ready=new Promise(r=>entered=r);st.runtime=()=>{entered();return new Promise(r=>release=r);};st.start(s.id);await ready;await st.cancel(s.id);release(home);await st.task;assert.equal(s.state,'CANCELLED');assert.equal(st.sheet,undefined);const next=new TranscriptionStudio({home});await next.initialize();assert.equal(next.get(s.id).state,'CANCELLED');assert.ok(path.resolve(home).startsWith(path.resolve(os.tmpdir())+path.sep));await fs.rm(home,{recursive:true,force:true});});
