import { unknownWorld, promotion } from './world.mjs';
const fail = code => { throw Object.assign(new Error(code), { code }); };

export class PublishedMixerAdapter {
  #publisher; #sequence=0; #snapshotId=null;
  constructor(publisher) { this.#publisher=publisher; }
  accept(envelope) {
    const s=this.#publisher.verify(envelope);
    if (s.sequence<this.#sequence || (s.sequence===this.#sequence && s.snapshotId!==this.#snapshotId)) { this.#publisher.invalidate('SNAPSHOT_SEQUENCE_ROLLBACK'); fail('SNAPSHOT_SEQUENCE_ROLLBACK'); }
    this.#sequence=s.sequence; this.#snapshotId=s.snapshotId;
    const metadata={schemaVersion:s.schemaVersion,snapshotId:s.snapshotId,observationId:s.observationId,sequence:s.sequence,publishedAt:s.publishedAt,sourceBackend:s.sourceBackend,freshness:s.freshness,levels:s.levels,reasonCodes:s.reasonCodes};
    const world=s.world;
    if (s.freshness.state==='stale') return {...unknownWorld(),state:'stale',presentation:'real-cached',reason:'WORLD_SNAPSHOT_STALE',observedAt:s.observedAt,publisher:metadata};
    if (!world) return {...unknownWorld(),state:s.levels.session==='available'?'current':'unknown',presentation:s.levels.session==='available'?'real-live':'unavailable',reason:s.reasonCodes[0]??'WORLD_SNAPSHOT_UNAVAILABLE',observedAt:s.observedAt,publisher:metadata,connection:s.connection,
      session:s.sessionBinding ? {hostId:s.sessionBinding.host_generation,sessionId:s.sessionBinding.session_id,projectGeneration:s.sessionBinding.project_generation,projectName:null}:null};
    const enabled=s.levels.structure==='available';
    const capabilities=world.capabilities.map(c=>{
      const p=promotion(world,c.id,['plugin.identity.read','plugin.parameter.layout','plugin.parameter.read'].includes(c.id)?world.target:null);
      const level={'mixer.track.read':'structure','plugin.enumerate':'structure','plugin.identity.read':'identity','plugin.parameter.layout':'layout','plugin.parameter.read':'values'}[c.id];
      if (!level || s.levels[level]!=='available') { p.enabled=false; p.liveEvidence=false; }
      return {...c,promotion:p};
    });
    const tracks=enabled ? world.tracks.map(t=>({...t,slots:t.slots.map(slot=>{
      if (!slot.plugin) return slot;
      const target={trackIndex:t.index,slotIndex:slot.index,instanceId:slot.plugin.instanceId};
      const identity=s.levels.identity==='available' && promotion(world,'plugin.identity.read',target).enabled;
      const layout=identity && s.levels.layout==='available' && promotion(world,'plugin.parameter.layout',target).enabled;
      const values=layout && s.levels.values==='available' && promotion(world,'plugin.parameter.read',target).enabled;
      return {...slot,plugin:identity ? {...slot.plugin,parameterCount:layout?slot.plugin.parameterCount:null,parameters:layout?slot.plugin.parameters.map(p=>({...p,value:values?p.value:null,readState:values?p.readState:'unavailable'})):[],identityVerified:true,layoutReadable:layout,valuesReadable:values,writeEnabled:false}:null};
    })})) : [];
    return {...world,tracks,capabilities,presentation:'real-live',publisher:metadata};
  }
  async world() {
    try { return {...this.accept(await this.#publisher.refresh()),history:this.#publisher.history}; }
    catch(error) { return {...unknownWorld(),presentation:'unavailable',history:this.#publisher.history,reason:/^[A-Z0-9_]{1,120}$/.test(error.code??'')?error.code:'WORLD_SNAPSHOT_REJECTED'}; }
  }
}
