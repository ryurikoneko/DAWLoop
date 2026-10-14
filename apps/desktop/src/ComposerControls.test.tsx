import React,{useState} from 'react';
import {afterEach,it,expect} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {ComposerControls,type ComposerSettings} from './ComposerControls';
afterEach(cleanup);
it('简易预设和高级参数共享真实状态，收起不会丢失参数或伪造成功',()=>{
 const submissions:ComposerSettings[]=[];function Wrapper(){const [value,onChange]=useState<ComposerSettings>({tempo:120,key:0,scale:'major',meter:'4/4',density:.55,rhythm:'even',bars:4,seed:42,progression:'I vi IV V',energyCurve:'.4 .7 .8 .5',style:''});return <ComposerControls value={value} onChange={onChange} generate={()=>submissions.push(value)} pending={false}/>;}
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><Wrapper/></I18nextProvider>);expect(screen.queryByRole('spinbutton',{name:'Seed'})).toBeNull();fireEvent.change(screen.getByRole('combobox',{name:'Note density preset'}),{target:{value:'high'}});fireEvent.click(screen.getByRole('button',{name:'Advanced composition settings'}));const seed=screen.getByRole('spinbutton',{name:'Seed'});fireEvent.change(seed,{target:{value:'99'}});expect((screen.getByRole('spinbutton',{name:'Note density (0.1–1)'}) as HTMLInputElement).value).toBe('0.85');fireEvent.click(screen.getByRole('button',{name:'Advanced composition settings'}));fireEvent.click(screen.getByRole('button',{name:'Generate candidate'}));expect(submissions).toHaveLength(1);expect(submissions[0].density).toBe(.85);expect(submissions[0].seed).toBe(99);expect(screen.queryByText('Completed')).toBeNull();
});
