import {readFile,writeFile,readdir,access,rename} from 'node:fs/promises';
import {observePianoRoll} from './piano_roll_binding_live.mjs';

export class NavigationObserver {
  constructor(sky,window,context) {
    this.sky=sky; this.window=window; this.context=context;
    this.completed=new Set(); this.pending=null;
  }

  async captureNext() {
    if(this.pending) throw Error('OBSERVATION_ALREADY_PENDING');
    const directory=this.context.output+'/mailbox';
    const files=(await readdir(directory)).filter(name=>name.endsWith('.request.json')&&!this.completed.has(name));
    if(files.length!==1) throw Error('PENDING_OBSERVATION_NOT_UNIQUE');
    const request=JSON.parse(await readFile(directory+'/'+files[0],'utf8')).request;
    if(await access(directory+'/'+request.request_id+'.cancel.json').then(()=>true,()=>false))
      throw Error('REQUEST_CANCELLED');
    if(request.pid!==this.context.pid||request.hwnd!==this.window.id)
      throw Error('WINDOW_IDENTITY_MISMATCH');
    this.pending={request,filename:files[0]};
    const result=await observePianoRoll(this.sky,this.window,{...this.context,output:request.output,
      expected_build:request.session.controller_build_id,
      controller_session_id:request.session.controller_session_id,
      project_generation:request.session.project_generation,target:request.target});
    this.pending.result=result;
    return {stage:request.stage,result};
  }

  async confirm(confirmed,visibleTitle) {
    const {request,result,filename}=this.pending??{};
    if(result?.status!=='BRACKET_PASSED_PENDING_VISUAL_REVIEW')throw Error('BRACKET_FAILED');
    const path=this.context.output+'/mailbox/'+request.request_id;
    if(await access(path+'.cancel.json').then(()=>true,()=>false))throw Error('REQUEST_CANCELLED');
    const receipt=JSON.parse(await readFile(request.output+'/observation.json','utf8'));
    const ui={visible:confirmed,confirmed,observer:'agent_visual_review',
      evidence_ref:request.stage+'/visual_review.json',
      pattern_number:request.target.expected_pattern_index,channel_name:request.target.expected_channel_name,
      window_pid:this.context.pid,window_hwnd:this.window.id,session:request.session,
      observed_unix:receipt.result.capture_completed_at.wall_unix_ms/1000,
      image_hash:result.image_hash,request_id:result.request_id,observer_generation:result.observer_generation,
      visible_title:visibleTitle,reviewed_unix:Date.now()/1000};
    await writeFile(request.output+'/visual_review.json',JSON.stringify(ui,null,2),{flag:'wx'});
    await writeFile(path+'.result.tmp',JSON.stringify({request,ui}),{flag:'wx'});
    await rename(path+'.result.tmp',path+'.result.json');
    this.completed.add(filename); this.pending=null;
    return {stage:request.stage,confirmed};
  }
}
