import fs from 'node:fs';
import {MusicIntelligenceService} from '../../../packages/music-intelligence/service.mjs';
const s=new MusicIntelligenceService({home:process.argv[2]});await s.initialize();const a=await s.importAudio(process.argv[3]);s.runWorker=()=>new Promise(()=>{});const id=await s.analyze(a.id);
while(!await s.analysisRepository.store.readLifecycle(a.id,id))await new Promise(r=>setTimeout(r,5));
// 此子进程故意不调用 close，验证持久状态而非内存任务可决定重启结果。
fs.writeSync(1,JSON.stringify({assetId:a.id,analysisId:id,worker:'TEST_STUB'})+'\n');process.exit(23);
