import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {validAsset,validId} from './analysis-contract.mjs';

export class AssetVisibility {
  constructor(home){this.home=home;this.saved=new Map();this.session=new Set();this.removed=new Set();this.queue=Promise.resolve();}
  async initialize(){
    try {
      const file=path.join(this.home,'saved-assets.json');
      if((await fs.stat(file)).size>1024*1024)throw Error('MI_SAVED_ASSETS_REJECTED');
      const data=JSON.parse(await fs.readFile(file,'utf8'));
      if(data.schemaVersion!==1||!Array.isArray(data.assets))throw Error('MI_SAVED_ASSETS_REJECTED');
      for(const row of data.assets){validAsset(row.assetId);if(!['USER_SAVED_PROJECT','USER_SAVED_ANALYSIS'].includes(row.kind)||!Number.isFinite(Date.parse(row.savedAt)))throw Error('MI_SAVED_ASSETS_REJECTED');if(row.analysisId!==null)validId(row.analysisId);this.saved.set(row.assetId,row);}
      for(const id of data.removedAssets??[]){validAsset(id);this.removed.add(id);}
    } catch(e){if(e.code!=='ENOENT')throw e;}
  }
  visible(id){return this.session.has(id)||this.saved.has(id);}
  async mutate(work){
    const pending=this.queue.then(async()=>{
      const next=new Map(this.saved),removed=new Set(this.removed);work(next,removed);
      const temporary=path.join(this.home,'saved-assets-'+randomUUID()+'.tmp');
      try {await fs.writeFile(temporary,JSON.stringify({schemaVersion:1,assets:[...next.values()],removedAssets:[...removed]}),{encoding:'utf8',flag:'wx'});await fs.rename(temporary,path.join(this.home,'saved-assets.json'));this.saved=next;this.removed=removed;}
      finally{await fs.unlink(temporary).catch(e=>{if(e.code!=='ENOENT')throw e;});}
    });
    this.queue=pending.catch(()=>{});return pending;
  }
  async save(assetId,kind,analysisId=null){validAsset(assetId);if(!['USER_SAVED_PROJECT','USER_SAVED_ANALYSIS'].includes(kind))throw Error('MI_SAVE_KIND_REJECTED');if(analysisId!==null)validId(analysisId);await this.mutate((next,removed)=>{next.set(assetId,{assetId,kind,analysisId,savedAt:new Date().toISOString()});removed.delete(assetId);});return true;}
  async remove(assetId){validAsset(assetId);await this.mutate((next,removed)=>{next.delete(assetId);removed.add(assetId);});this.session.delete(assetId);return true;}
}
