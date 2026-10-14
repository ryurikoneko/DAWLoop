import {it,expect} from 'vitest';
import {secondsAtBeat,beatAtSeconds} from './score-time';
import type {SymbolicScore} from '../../../packages/shared-types/music-contracts';
it('试听指针和音符时长使用同一Tempo Map，不把后段速度覆盖前段',()=>{
 const s={tempo:120,tempoMap:[{start:0,bpm:120},{start:4,bpm:60}]} as SymbolicScore;expect(secondsAtBeat(s,4)).toBe(2);expect(secondsAtBeat(s,6)).toBe(4);expect(beatAtSeconds(s,4)).toBe(6);for(const beat of [0,.25,1/3,4,7,20])expect(beatAtSeconds(s,secondsAtBeat(s,beat))).toBeCloseTo(beat,10);
});
