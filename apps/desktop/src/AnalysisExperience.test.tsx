import React from 'react';
import {afterEach,it,expect} from 'vitest';
import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {I18nextProvider} from 'react-i18next';
import {createDesktopI18n} from './i18n';
import {boundAnalysis,explainAnalysis,series} from './analysis-view';
import {AnalysisOverview} from './AnalysisOverview';
import {AnalysisChart} from './AnalysisChart';
import type {AnalysisFieldV0_5,MusicAnalysisResultV0_5} from '../../../packages/shared-types/analysis-contracts';
import type {Analysis,Asset} from '../../../packages/shared-types/music-contracts';
afterEach(cleanup);
const asset={id:'a'.repeat(32),sha256:'b'.repeat(64),name:'owned.wav'} as Asset;
const analysis={assetId:asset.id,sourceSha256:asset.sha256,analysisId:'owned-analysis'} as Analysis;
function field(name:string,value:AnalysisFieldV0_5['value'],extra:Partial<AnalysisFieldV0_5>={}):AnalysisFieldV0_5{return {name,value,range:[10,20],status:'READY',category:'MEASURED',unit:'linear_amplitude',method:'owned-fixture-method',reasonCode:null,confidenceLabel:null,confidenceScore:null,calibrationStatus:'NOT_APPLICABLE',origin:'AUDIO_MEASUREMENT',implementationVersion:'owned-fixture',observedAt:'2026-10-13T00:00:00.000Z',...extra};}
function record(fields:AnalysisFieldV0_5[]):MusicAnalysisResultV0_5{return {schemaVersion:'0.5',asset:{assetId:asset.id,sourceSha256:asset.sha256,duration:60,windowRange:[10,20]},analysis:{analysisId:analysis.analysisId!,analysisVersion:'0.5',implementationVersion:'owned-fixture',modelRevision:null,observedAt:'2026-10-13T00:00:00.000Z'},fields};}
it('自动摘要只显示当前音频与版本绑定的真实字段，缺字段不补零',()=>{
 const r=record([field('rms',.125),field('bpmCandidates',[120],{category:'ESTIMATED',unit:'BPM',origin:'ALGORITHM_ESTIMATE'})]);expect(boundAnalysis(analysis,r,asset)).toBe(r);expect(boundAnalysis({...analysis,assetId:'other'},r,asset)).toBeNull();expect(boundAnalysis({...analysis,analysisId:'other'},r,asset)).toBeNull();expect(boundAnalysis(analysis,r,{...asset,sha256:'c'.repeat(64)})).toBeNull();
 render(<I18nextProvider i18n={createDesktopI18n('zh-CN')}><AnalysisOverview analysis={analysis} record={r} asset={asset} developer={false}/></I18nextProvider>);expect(screen.getByText('0.125')).toBeTruthy();expect(screen.getByText('120.00')).toBeTruthy();expect(screen.getByText(/实际分析区间：10.000–20.000/)).toBeTruthy();expect(screen.getByText(/· 估计/)).toBeTruthy();expect(screen.getByText('调性不确定')).toBeTruthy();expect(screen.getByText('测量详情')).toBeTruthy();expect(screen.queryByRole('textbox')).toBeNull();
});
it('解释严格使用区间时间与有效样本，静音不产生情绪或段落判断',()=>{
 const r=record([field('energy',[[10,.1],[14,.1],[15,.5],[19,.5]]),field('spectralFlux',[[11,.02],[19,.3]]),field('onsets',[11,12,13],{category:'ESTIMATED'})]);const original=JSON.stringify(r),observations=explainAnalysis(r);expect(observations.map(o=>o.key)).toEqual(['energyHigher','fluxMaximum','onsetRate']);expect(observations[0].values).toEqual({front:.1,back:.5});expect(observations[1].values).toEqual({time:19,value:.3});expect(observations[2].values.rate).toBe(.3);expect(observations.every(o=>o.origin==='RULE_BASED_DRAFT')).toBe(true);expect(JSON.stringify(r)).toBe(original);
 expect(explainAnalysis(record([field('energy',[[10,0],[16,0]])]))[0].key).toBe('energySimilar');expect(explainAnalysis(record([]))).toEqual([]);expect(series(field('energy',[[9,.1],[10,.2]]))).toEqual([]);expect(series(field('energy',[[10,.1],[10,.2]]))).toEqual([]);expect(series(field('energy',[[10,NaN]]))).toEqual([]);
});
it('图表保留真实非零时间轴、单位、精确键盘读数与缺失状态',()=>{
 render(<I18nextProvider i18n={createDesktopI18n('en-US')}><AnalysisChart field={field('spectralCentroid',[[10,400],[12,800]],{unit:'Hz'})}/></I18nextProvider>);const svg=screen.getByRole('img');fireEvent.keyDown(svg,{key:'End'});expect(screen.getByRole('status').textContent).toBe('12.0000 s · 800.000 Hz');expect(screen.getByText('10.00')).toBeTruthy();expect(screen.getByText('20.00')).toBeTruthy();fireEvent.blur(svg);expect(screen.getByRole('status').textContent).toContain('Move over');
});
