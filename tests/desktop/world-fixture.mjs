export function fixture(now=Date.now()) {
  const session={hostId:'test-host',sessionId:'test-session',projectGeneration:'test-generation',projectName:'Synthetic test project'};
  const target={trackIndex:1,slotIndex:0,instanceId:'test-instance'};
  const capabilities=['mixer.track.read','plugin.enumerate','plugin.identity.read','plugin.parameter.layout','plugin.parameter.read','plugin.parameter.write'].map(id=>({id,state:'available',confidence:'high',contractVersion:1,evidence:[{id:'synthetic-receipt',sha256:'a'.repeat(64),outcome:'passed',observedAt:new Date(now).toISOString(),binding:{hostId:session.hostId,sessionId:session.sessionId,projectGeneration:session.projectGeneration,...(id==='mixer.track.read'||id==='plugin.enumerate'?{trackIndex:null,slotIndex:null,instanceId:null}:target)}}]}));
  return {apiVersion:1,source:'core',observedAt:new Date(now).toISOString(),session,target,tracks:[{index:1,name:'Synthetic track',slots:[{index:0,state:'occupied',plugin:{instanceId:'test-instance',name:'Synthetic plugin',parameterCount:1,parameters:[{index:0,name:'Synthetic gain',value:0.5,readState:'available'}]}},{index:1,state:'empty',plugin:null}]}],capabilities};
}
