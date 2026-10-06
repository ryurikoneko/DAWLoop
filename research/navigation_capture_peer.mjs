import { readFile, writeFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { CaptureIntervalObserver } from './capture_interval_observer.mjs';

export class NavigationCapturePeer {
  constructor(sky,window,context) {
    this.window=window;this.context=context;this.observer=new CaptureIntervalObserver(sky);
    this.handled=new Set();this.pending=null;this.packet=null;
  }
  async next() {
    const names=(await readdir(this.context.mailbox)).filter(name=>name.endsWith('.request.json'));
    const requests=await Promise.all(names.map(async name=>JSON.parse(await readFile(join(this.context.mailbox,name),'utf8'))));
    const candidates=requests.filter(row=>!this.handled.has(row.request.request_id)).sort((a,b)=>a.request_index-b.request_index);
    if(!candidates.length)return {waiting:true};
    this.pending=candidates[0];return this.pending;
  }
  async capture() {
    const payload=this.pending;
    if(payload?.action!=='OBSERVE_UI'||this.handled.has(payload.request.request_id))throw Error('REQUEST_GENERATION_MISMATCH');
    const request=Object.freeze({operation_id:payload.request.operation_id,request_id:payload.request.request_id,
      observer_generation:this.observer.generation,binding:structuredClone(payload.request),created_at:this.observer.stamp()});
    const packet=await this.observer.capture(request,this.window,{onRawResponse:async value=>{
      await writeFile(join(this.context.repository,'evidence/runtime_v2/target_preparation/live_5',`capture_raw_${payload.request_index}.json`),JSON.stringify(value,null,2),{flag:'wx'});
    }});
    const receipt=this.observer.accept(request,packet);
    if(!receipt.accepted)throw Error('OBSERVATION_NOT_ACCEPTED');
    const artifact=join(tmpdir(),`DAWLoop_NavigationLive5_${request.request_id}.jpg`);
    await this.observer.persist(packet,artifact);
    this.packet={request,packet,receipt,artifact};
    return {request_index:payload.request_index,target:payload.target,image_hash:packet.result.image_hash,
      capture_interval:packet.result.captured_at,image_dimensions:packet.result.image_dimensions};
  }
  async publishUI(review) {
    const payload=this.pending;
    const {packet,request,receipt,artifact}=this.packet;
    if(payload.action!=='OBSERVE_UI'||!review.confirmed||review.channel_name!==payload.target.expected_channel_name||
      review.pattern_number!==payload.target.expected_pattern_index)throw Error('PIANO_ROLL_TARGET_UNCONFIRMED');
    const stamp=value=>({clock_domain:value.clock_domain,monotonic:value.monotonic_ms/1000,wall:value.wall_unix_ms/1000});
    const result=packet.result;
    const published=stamp(this.observer.stamp());
    if((published.monotonic*1000-request.created_at.monotonic_ms)>55000)throw Error('HANDOFF_DELIVERY_TIMEOUT');
    const evidence={visible:true,confirmed:true,observer:'agent_visual_review',
      evidence_ref:`capture:${request.request_id}:${result.image_hash}`,pattern_number:review.pattern_number,
      channel_name:review.channel_name,window_pid:payload.pid,window_hwnd:payload.hwnd,session:payload.session,
      capture_started_unix:result.capture_started_at.wall_unix_ms/1000,
      observed_unix:result.capture_completed_at.wall_unix_ms/1000,
      capture_completed_unix:result.capture_completed_at.wall_unix_ms/1000,
      captured_at:stamp(result.capture_completed_at),published_at:published,capture_artifact:artifact,
      capture_sha256:result.image_hash,image_mime:result.image_mime,image_dimensions:result.image_dimensions,
      capture_interval:result.captured_at,raw_response_hash:result.raw_response_hash,
      observer_generation:result.observer_generation,request_id:request.request_id,operation_id:request.operation_id};
    const {execFile}=await import('node:child_process');
    const {promisify}=await import('node:util');
    // 直接复用生产契约的摘要函数，避免两种语言的数字序列化差异。
    const code=`import sys,json;sys.path.insert(0,${JSON.stringify(this.context.repository)});from research.observation_handoff import content_hash;print(content_hash(json.loads(sys.argv[1])))`;
    const hashed=await promisify(execFile)(this.context.python,['-c',code,JSON.stringify(evidence)],{cwd:this.context.repository,timeout:3000});
    const body={request:payload.request,evidence,evidence_hash:hashed.stdout.trim(),
      trace:{T2:stamp(result.observer_received_at),T3:stamp(result.capture_started_at),T4:stamp(result.capture_completed_at),T5:published}};
    await writeFile(join(this.context.mailbox,payload.request.request_id+'.result.json'),JSON.stringify(body),{flag:'wx'});
    this.handled.add(payload.request.request_id);this.packet=null;
    return {published:true,teardown:await this.observer.teardown(request,1000),receipt};
  }
  async publishPrimitive(outcome,rawInputs) {
    const payload=this.pending;
    if(payload.action!=='NAVIGATION_PRIMITIVE')throw Error('ACTION_MISMATCH');
    const body={request:payload.request,request_index:payload.request_index,value:{outcome,raw_input_count:rawInputs}};
    await writeFile(join(this.context.mailbox,payload.request.request_id+'.result.json'),JSON.stringify(body),{flag:'wx'});
    this.handled.add(payload.request.request_id);return {published:true};
  }
  async publishExit() {
    const payload=this.pending;
    if(payload.action!=='NO_SAVE_EXIT')throw Error('ACTION_MISMATCH');
    await writeFile(join(this.context.mailbox,payload.request.request_id+'.result.json'),JSON.stringify({request:payload.request,
      request_index:payload.request_index,value:{no_save_exit:true}}),{flag:'wx'});
    this.handled.add(payload.request.request_id);
  }
}
