export function validateEmbedding(result){
 if(!result||result.schemaVersion!==1||result.source!=='OMAR_RQ'||result.rate!==25||result.resampledRate!==24000||result.semanticStyleClassification!==false||!Array.isArray(result.shape)||result.shape.length!==2||!Number.isSafeInteger(result.shape[0])||result.shape[0]<1||result.shape[0]>750||result.shape[1]!==1024||!Number.isFinite(result.duration)||result.duration<=0||result.duration>30||!Number.isFinite(result.elapsedMs)||result.elapsedMs<0)throw Error('MI_EMBEDDING_CONTRACT_REJECTED');
 for(const name of ['timestamps','norms'])if(!Array.isArray(result[name])||result[name].length!==result.shape[0]||result[name].some(v=>!Number.isFinite(v)||v<0))throw Error('MI_EMBEDDING_CONTRACT_REJECTED');
 if(result.timestamps.some((t,i)=>Math.abs(t-i/25)>1e-6||t>=result.duration))throw Error('MI_EMBEDDING_CONTRACT_REJECTED');
 return result;
}
