import type {Analysis,Asset} from '../../../packages/shared-types/music-contracts';
import type {AnalysisFieldV0_5,MusicAnalysisResultV0_5} from '../../../packages/shared-types/analysis-contracts';

export type RuleObservation={key:'energyHigher'|'energyLower'|'energySimilar'|'fluxMaximum'|'onsetRate';values:Record<string,number>;sourceFields:string[];origin:'RULE_BASED_DRAFT'};
export const overviewFields=['bpmCandidates','beats','onsets','rms','samplePeak','crestFactor','spectralCentroid','spectralFlux','tonalCandidates','lufs'] as const;
export function analysisUnit(unit:string|null|undefined,translate:(key:string)=>string):string {return unit?translate(`ux04.units.${unit}`):'';}
export function series(field:AnalysisFieldV0_5|undefined):[number,number][] {
  if(!field||field.status!=='READY'||!Array.isArray(field.value)||!field.range)return [];
  const rows=field.value;
  if(!rows.every((r,i)=>Array.isArray(r)&&r.length===2&&r.every(v=>typeof v==='number'&&Number.isFinite(v))&&Number(r[0])>=field.range![0]&&Number(r[0])<=field.range![1]&&(i===0||Number(r[0])>Number((rows[i-1] as number[])[0]))))return [];
  return rows as [number,number][];
}
export function boundAnalysis(analysis:Analysis|null,record:MusicAnalysisResultV0_5|null,asset:Asset|undefined):MusicAnalysisResultV0_5|null {
  if(!analysis||!record||!asset||record.asset.assetId!==asset.id||analysis.assetId!==asset.id||record.asset.sourceSha256!==asset.sha256||analysis.sourceSha256!==asset.sha256||record.analysis.analysisId!==analysis.analysisId)return null;
  return record;
}
// 只解释已经发布的测量样本，不把能量或频谱变化升级为歌曲结构、情绪或风格。
export function explainAnalysis(record:MusicAnalysisResultV0_5):RuleObservation[] {
  const get=(name:string)=>record.fields.find(f=>f.name===name),observations:RuleObservation[]=[];
  const energy=get('energy'),points=series(energy);
  if(energy?.range&&points.length>=2){
    const mid=(energy.range[0]+energy.range[1])/2,front=points.filter(p=>p[0]<mid),back=points.filter(p=>p[0]>=mid);
    if(front.length&&back.length){const mean=(p:[number,number][])=>p.reduce((sum,r)=>sum+r[1],0)/p.length,a=mean(front),b=mean(back),key=b>a*1.1?'energyHigher':a>b*1.1?'energyLower':'energySimilar';observations.push({key,values:{front:a,back:b},sourceFields:['energy'],origin:'RULE_BASED_DRAFT'});}
  }
  const flux=series(get('spectralFlux'));if(flux.length){const maximum=flux.reduce((a,b)=>b[1]>a[1]?b:a);observations.push({key:'fluxMaximum',values:{time:maximum[0],value:maximum[1]},sourceFields:['spectralFlux'],origin:'RULE_BASED_DRAFT'});}
  const onsets=get('onsets');if(onsets?.status==='READY'&&onsets.range&&onsets.range[1]>onsets.range[0]&&Array.isArray(onsets.value)&&onsets.value.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=onsets.range![0]&&v<=onsets.range![1]))observations.push({key:'onsetRate',values:{count:onsets.value.length,rate:onsets.value.length/(onsets.range[1]-onsets.range[0])},sourceFields:['onsets'],origin:'RULE_BASED_DRAFT'});
  return observations;
}
