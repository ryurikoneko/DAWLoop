import React from 'react';
import {afterEach,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {PianoRoll} from './PianoRoll';
import type {SymbolicScore} from '../../../packages/shared-types/music-contracts';
afterEach(cleanup);
it('显示舍入不改变三连音原始时间；小节线使用实际拍号',()=>{
 const score:SymbolicScore={schemaVersion:1,source:'USER_EDITED',tempo:120,meter:[3,4],tempoMap:[{start:0,bpm:120}],notes:[{id:'precision-note',pitch:60,start:1/3,duration:2/3,velocity:90,part:0} as SymbolicScore['notes'][number]],edits:[]},change=vi.fn();
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><PianoRoll initial={score} onChange={change} audition={()=>{}}/></I18nextProvider>);
 const input=screen.getByRole('spinbutton',{name:'start-precision-note'});expect((input as HTMLInputElement).value).toBe('0.3333');const calls=change.mock.calls.length;fireEvent.focus(input);fireEvent.blur(input);expect(change.mock.calls.length).toBe(calls);expect(change.mock.calls[0][0].notes[0].start).toBe(1/3);
 const lines=screen.getByRole('img',{name:'Editable note grid'}).querySelectorAll('line[stroke="#778387"]');expect(lines[1].getAttribute('x1')).toBe(String(64+3*48));
 fireEvent.change(input,{target:{value:'0.5'}});fireEvent.blur(input);expect(change.mock.calls.at(-1)?.[0].notes[0].start).toBe(.5);
});
