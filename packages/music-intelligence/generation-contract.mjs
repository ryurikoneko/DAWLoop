export function generationRequest(p){
  if(!p||!['original','recomposition'].includes(p.mode)||typeof p.style!=='string'||p.style.length>10000||!Number.isSafeInteger(p.seed)||p.seed<0||p.seed>0xffffffff||!Number.isFinite(p.tempo??120)||(p.tempo??120)<20||(p.tempo??120)>300)throw Error('MI_GENERATION_REQUEST_REJECTED');
  if(p.profile&&JSON.stringify(p.profile).length>65536)throw Error('MI_PROFILE_REJECTED');
  if(p.mode==='original'&&p.abc!==undefined)throw Error('MI_ORIGINAL_MELODY_FORBIDDEN');
  if(p.mode==='recomposition'&&(p.confirmed!==true||typeof p.abc!=='string'||p.abc.length>65536))throw Error('MI_SCORE_CONFIRMATION_REQUIRED');
  return {schemaVersion:1,provider:'YUE2',mode:p.mode,style:p.style,seed:p.seed,tempo:p.tempo??120,profile:p.profile??null,...(p.mode==='recomposition'?{abc:p.abc,source:'USER_EDITED',confirmed:true}:{}),runtimeRevision:'8f24312f187763b9854adeec87e437e2b03bbff1'};
}
