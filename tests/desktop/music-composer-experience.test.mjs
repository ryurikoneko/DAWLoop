import test from 'node:test';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import {compose} from '../../packages/music-intelligence/composer.mjs';
const base={mode:'original',seed:42,tempo:120,key:0,scale:'major',meter:[4,4],density:.55,rhythm:'even',bars:4,progression:'I vi IV V',energyCurve:[.4,.7,.8,.5],candidates:1};
test('音乐工作区所有常量翻译键在两种语言中存在，不能用通用缺失提示掩盖遗漏',async()=>{
 const modules=['MusicIntelligence.tsx','ComposerControls.tsx','AnalysisChart.tsx','AnalysisOverview.tsx','PianoRoll.tsx','AudioPreviewPlayer.tsx','AudioSetupPanel.tsx','AISetup.tsx'];
 for(const language of ['en-US','zh-CN']){const resource=JSON.parse(await fs.readFile(new URL(`../../apps/desktop/locales/${language}/music.json`,import.meta.url),'utf8'));for(const name of modules){const source=await fs.readFile(new URL(`../../apps/desktop/src/${name}`,import.meta.url),'utf8');for(const match of source.matchAll(/\bt\('([^']+)'(?=[,)])/g)){let value=resource;for(const part of match[1].split('.'))value=value?.[part];assert.equal(typeof value,'string',`${language}:${name}:${match[1]}`);}}}
});
test('同种子可复现；预设、调性、级数与节奏的变化直接作用于现有引擎',()=>{
 const a=compose(base);assert.deepEqual(a,compose(base));assert.notDeepEqual(a.candidates[0].notes,compose({...base,seed:43}).candidates[0].notes);
 const rows=[.25,.55,.85].map(density=>compose({...base,density}).candidates[0]);assert.ok(rows[0].notes.length<rows[2].notes.length);assert.deepEqual(rows.map(r=>r.provenance.constraints.density),[.25,.55,.85]);
 const sync=compose({...base,rhythm:'syncopated'}).candidates[0];assert.ok(sync.notes.some(n=>n.start%1===.5));assert.ok(a.candidates[0].notes.every(n=>n.start%1===0));
 assert.deepEqual(compose({...base,rhythm:'sparse'}).candidates[0].notes,a.candidates[0].notes);assert.deepEqual(compose({...base,style:'UNUSED_STYLE'}).candidates[0].notes,a.candidates[0].notes);
 const shifted=compose({...base,key:2}).candidates[0];assert.notDeepEqual(shifted.notes,a.candidates[0].notes);assert.ok(shifted.notes.every(n=>[0,2,4,5,7,9,11].includes((n.pitch-2+120)%12)));assert.deepEqual(shifted.chords.map(c=>c.pitches),a.candidates[0].chords.map(c=>c.pitches.map(p=>p+2)));assert.notDeepEqual(compose({...base,scale:'minor'}).candidates[0].chords,a.candidates[0].chords);assert.notDeepEqual(compose({...base,progression:'V IV I'}).candidates[0].chords,a.candidates[0].chords);
 assert.equal(compose({...base,meter:[6,8]}).candidates[0].chords[0].duration,3);assert.throws(()=>compose({...base,density:NaN}),/MI_COMPOSITION_REJECTED/);assert.throws(()=>compose({...base,progression:'I-X'}),/MI_COMPOSITION_REJECTED/);
});
