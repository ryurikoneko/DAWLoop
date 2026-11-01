import {parseAbc} from './symbolic.mjs';
const revisions={SHEETSAGE2:'32c7c7473e7b59e1ed36bd8a8fefbd11ae8d468a',YUE2:'8f24312f187763b9854adeec87e437e2b03bbff1'};
export function validateScoreResult(result,provider){
 if(!revisions[provider]||!result||result.schemaVersion!==1||result.source!==provider||result.modelRevision!==revisions[provider]||typeof result.abc!=='string'||!Number.isFinite(result.elapsedMs)||result.elapsedMs<0)throw Error('MI_SCORE_PROVIDER_CONTRACT_REJECTED');
 if(provider==='YUE2'&&(!Number.isSafeInteger(result.seed)||result.seed<0||result.seed>0xffffffff))throw Error('MI_SCORE_PROVIDER_CONTRACT_REJECTED');
 // 当前编辑器明确支持的子集之外不能静默删去模型音符。
 const score=parseAbc(result.abc);return {...score,source:provider,provenance:{modelRevision:result.modelRevision,seed:result.seed,elapsedMs:result.elapsedMs}};
}
