import React from 'react';
import {afterEach,it,expect,vi} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {AnalysisChart} from './AnalysisChart';
import {TranscriptionAvailability} from './TranscriptionAvailability';
import type {AnalysisFieldV0_5} from '../../../packages/shared-types/analysis-contracts';
afterEach(cleanup);
it('全曲图表用真实分钟时间，鼠标和键盘试听请求沿用样本位置',()=>{
 const seek=vi.fn(),field={name:'energy',value:[[0,.1],[90,.3],[180,.2]],range:[0,189],status:'READY',unit:'linear_amplitude'} as AnalysisFieldV0_5;
 render(<I18nextProvider i18n={createDesktopI18n('zh-CN')}><AnalysisChart field={field} onSeek={seek}/></I18nextProvider>);
 const svg=screen.getByRole('img');fireEvent.keyDown(svg,{key:'End'});fireEvent.keyDown(svg,{key:'Enter'});expect(seek).toHaveBeenLastCalledWith(180);fireEvent.click(svg);expect(seek).toHaveBeenCalledTimes(2);expect(screen.getByText('3:09')).toBeTruthy();
});
it('不可用SheetSage2仍可查真实原因与设置；信息切换不授予转录权限',()=>{
 const configure=vi.fn();render(<I18nextProvider i18n={createDesktopI18n('en-US')}><TranscriptionAvailability model={{id:'sheetsage2',modelId:'SheetSage2',status:'ERROR',reason:'MI_MODEL_UNAVAILABLE',license:'Apache-2.0',revision:null,device:'cpu'}} developer={false} configure={configure}/></I18nextProvider>);
 expect(screen.getByRole('region')).toBeTruthy();expect(screen.getByText('SheetSage2')).toBeTruthy();expect(screen.queryByText('MI_MODEL_UNAVAILABLE')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Component Manager'}));expect(configure).toHaveBeenCalledTimes(1);
});
