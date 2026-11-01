import type {Job} from '../../../packages/shared-types/music-contracts';

export function taskStatusKey(job:Pick<Job,'state'|'method'>):string {
  if(job.state==='RUNNING')return ({analyze:'ANALYZING',transcribe:'TRANSCRIBING',writeMidi:'EXPORTING',load:'LOADING_MODEL'} as Record<string,string>)[job.method]??'RUNNING';
  return ['QUEUED','ANALYZING','TRANSCRIBING','EXPORTING','LOADING_MODEL','DOWNLOADING','PREPARING','INSTALLING','COMPLETED','CANCELLED','FAILED'].includes(job.state)?job.state:'UNKNOWN';
}
