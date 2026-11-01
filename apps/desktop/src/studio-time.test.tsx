import {describe,it,expect} from 'vitest';
import {trackScore,scoreTrack,studioMeter,studioBpm} from './studio-time';
import type {TranscriptionSession,StudioTrack} from '../../../packages/shared-types/transcription-contracts';
describe('工作台时间转换',()=>{it('变速及弱起下往返不量化音符',()=>{const s={tempo:[{time:0,bpm:99.384},{time:.31,bpm:100},{time:18.72,bpm:98}],beats:[[.31,1,4,4]]} as TranscriptionSession;const t:StudioTrack={id:'vocal',provenance:'MODEL_PREDICTION',notes:[{id:'one',start:.123456,end:19.987654,pitch:61,velocity:91}]};const next=scoreTrack(s,t,trackScore(s,t));expect(next.notes[0].start).toBeCloseTo(t.notes[0].start,10);expect(next.notes[0].end).toBeCloseTo(t.notes[0].end,10);expect(next.notes[0].pitch).toBe(61);});});
it('弱起首拍不能冒充全曲拍号与速度',()=>{const s={tempo:[{time:0,bpm:99.384},{time:.31,bpm:100},{time:.91,bpm:100}],beats:[[0,1,1,8],[.31,1,4,4],[.91,2,4,4]]} as TranscriptionSession;expect(studioMeter(s)).toEqual([4,4]);expect(studioBpm(s)).toBe(100);});
