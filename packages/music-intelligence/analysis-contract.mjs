const categories={MEASURED:['AUDIO_MEASUREMENT'],ESTIMATED:['ALGORITHM_ESTIMATE'],DERIVED:['DATA_DERIVATION'],GENERATED:['RULE_BASED_DRAFT','LLM_GENERATED'],USER_EDITED:['USER_INPUT']};
export const ANALYSIS_VERSION='0.5';
export const MAX_ANALYSIS_BYTES=4*1024*1024;
export const GATE_B_CONFIG=Object.freeze({analysisRate:22050,nFft:2048,hopLength:512,window:'hann',fluxCenter:false,fluxNormalization:'L1_PER_FRAME',fluxDifference:'POSITIVE_L1',channelAggregation:'PEAK_MAX_RMS_MEAN_SQUARE_ALL_SAMPLES',pcmFullScale:1,decodeBlockFrames:65536,maxSeconds:30,maxSampleRate:192000,maxChannels:8,resampler:'soxr_hq'});
export const SONG_CONFIG=Object.freeze({...GATE_B_CONFIG,maxSeconds:7200,resampler:'soxr_hq_stream',featureCoreFrames:660992,featureMarginFrames:22016,maxCurvePoints:1200,chromaFft:8192,chromaHop:2048});
export function requireValue(condition,code='MI_ANALYSIS_SCHEMA_REJECTED'){if(!condition)throw Error(code);}
export function safeJson(value,limit=MAX_ANALYSIS_BYTES){
 const visit=(v,depth)=>{requireValue(depth<=24);if(v===null||typeof v==='boolean')return;if(typeof v==='number'){requireValue(Number.isFinite(v));return;}if(typeof v==='string'){requireValue(v.length<=100000);return;}requireValue(typeof v==='object');if(Array.isArray(v)){requireValue(v.length<=100000);for(const x of v)visit(x,depth+1);return;}requireValue(Object.getPrototypeOf(v)===Object.prototype||Object.getPrototypeOf(v)===null);for(const [k,x] of Object.entries(v)){requireValue(!['__proto__','prototype','constructor'].includes(k),'MI_ANALYSIS_PROTOTYPE_REJECTED');visit(x,depth+1);}};
 visit(value,0);const text=JSON.stringify(value);requireValue(Buffer.byteLength(text)<=limit,'MI_ANALYSIS_TOO_LARGE');return text;
}
export function canonicalJson(value){safeJson(value);const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;return JSON.stringify(ordered(value));}
function keys(v,required,optional=[]){requireValue(v&&typeof v==='object'&&!Array.isArray(v));requireValue(required.every(k=>Object.hasOwn(v,k))&&Object.keys(v).every(k=>required.includes(k)||optional.includes(k)));}
function str(v,max=200){requireValue(typeof v==='string'&&v.length>0&&v.length<=max);}
export function validId(v){requireValue(typeof v==='string'&&/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(v),'MI_ANALYSIS_ID_REJECTED');return v;}
export function validAsset(v){requireValue(typeof v==='string'&&/^[a-f0-9]{32}$/.test(v),'MI_ANALYSIS_ASSET_REJECTED');return v;}
export function validSha(v){requireValue(typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),'MI_ANALYSIS_SOURCE_REJECTED');return v;}
function time(v){requireValue(typeof v==='string'&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString()===v);}
function freeze(v){if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;}
export function validateAnalysis(value,{userEdit=false}={}){
 const text=safeJson(value);const v=JSON.parse(text);keys(v,['schemaVersion','asset','analysis','fields']);requireValue(v.schemaVersion===ANALYSIS_VERSION);
 keys(v.asset,['assetId','sourceSha256','duration'],['windowSha256','windowEncoding','windowRange']);validAsset(v.asset.assetId);validSha(v.asset.sourceSha256);requireValue(v.asset.duration===null||Number.isFinite(v.asset.duration)&&v.asset.duration>=0);
 if(Object.hasOwn(v.asset,'windowSha256')){validSha(v.asset.windowSha256);requireValue(v.asset.windowEncoding==='PCM_F32LE_INTERLEAVED_V1'&&Array.isArray(v.asset.windowRange)&&v.asset.windowRange.length===2&&v.asset.windowRange.every(Number.isFinite)&&v.asset.windowRange[0]>=0&&v.asset.windowRange[1]>v.asset.windowRange[0]&&v.asset.windowRange[1]-v.asset.windowRange[0]<=7200.000000001&&(v.asset.duration===null||v.asset.windowRange[1]<=v.asset.duration));}else requireValue(!Object.hasOwn(v.asset,'windowEncoding')&&!Object.hasOwn(v.asset,'windowRange'));
 keys(v.analysis,['analysisId','analysisVersion','implementationVersion','modelRevision','observedAt']);validId(v.analysis.analysisId);requireValue(v.analysis.analysisVersion===ANALYSIS_VERSION);str(v.analysis.implementationVersion);requireValue(v.analysis.modelRevision===null||typeof v.analysis.modelRevision==='string'&&v.analysis.modelRevision.length<=200);time(v.analysis.observedAt);
 requireValue(Array.isArray(v.fields)&&v.fields.length>0&&v.fields.length<=128);const names=new Set();
 for(const f of v.fields){keys(f,['name','category','value','unit','method','range','status','reasonCode','confidenceLabel','confidenceScore','calibrationStatus','origin','implementationVersion','observedAt'],['sourceFields','formulaVersion']);
  str(f.name,100);requireValue(!names.has(f.name),'MI_ANALYSIS_DUPLICATE_FIELD');names.add(f.name);requireValue(Object.hasOwn(categories,f.category)&&categories[f.category].includes(f.origin),'MI_ANALYSIS_ORIGIN_REJECTED');str(f.method);str(f.implementationVersion);time(f.observedAt);
  requireValue(f.unit===null||typeof f.unit==='string'&&f.unit.length>0&&f.unit.length<=100);if(f.category==='MEASURED')requireValue(f.unit!==null);
  requireValue(f.range===null||Array.isArray(f.range)&&f.range.length===2&&f.range.every(Number.isFinite)&&f.range[0]>=0&&f.range[1]>=f.range[0]&&(v.asset.duration===null||f.range[1]<=v.asset.duration));
  requireValue(['READY','UNKNOWN','NOT_READY','FAILED'].includes(f.status));requireValue(f.reasonCode===null||typeof f.reasonCode==='string'&&/^[A-Z0-9_]{1,100}$/.test(f.reasonCode));
  requireValue(f.status==='READY'?f.value!==null&&f.reasonCode===null:f.value===null&&f.reasonCode!==null);
  if(f.status==='READY'){
   if(['duration','sampleRate','channels','peak','samplePeak','samplePeakDbfs','rms','rmsDbfs','crestFactor'].includes(f.name))requireValue(typeof f.value==='number'&&Number.isFinite(f.value));
   if(['samplePeak','rms','crestFactor'].includes(f.name))requireValue(f.value>=0);
   if(['sampleRate','channels'].includes(f.name))requireValue(Number.isInteger(f.value)&&f.value>0);
   if(['energy','spectralCentroid','chroma','bpmCandidates','beats','onsets','tonalCandidates','segmentCandidates'].includes(f.name))requireValue(Array.isArray(f.value));
   if(['energy','spectralCentroid'].includes(f.name))requireValue(f.value.every(x=>Array.isArray(x)&&x.length===2&&x.every(Number.isFinite)));
   if(['chroma','bpmCandidates','beats','onsets','segmentCandidates'].includes(f.name))requireValue(f.value.every(Number.isFinite));
   if(f.name==='chroma')requireValue(f.value.length===12);
   if(f.name==='tonalCandidates')requireValue(f.value.every(x=>x&&Number.isInteger(x.pitchClass)&&x.pitchClass>=0&&x.pitchClass<=11&&Number.isFinite(x.strength)));
   if(f.name==='spectralFlux')requireValue(Array.isArray(f.value)&&f.value.length<=1300&&f.value.every((x,i)=>Array.isArray(x)&&x.length===2&&x.every(Number.isFinite)&&x[1]>=0&&x[1]<=1.000001&&f.range&&x[0]>=f.range[0]&&x[0]<=f.range[1]&&(i===0||x[0]>f.value[i-1][0])));
   if(f.category==='GENERATED')requireValue(typeof f.value==='string');
  }
  requireValue([null,'high','medium','low','very-low','unknown'].includes(f.confidenceLabel));requireValue(['CALIBRATED','UNCALIBRATED','NOT_APPLICABLE'].includes(f.calibrationStatus));
  if(f.category==='ESTIMATED')requireValue(f.confidenceLabel!==null&&f.calibrationStatus==='UNCALIBRATED');
  // 本合同尚未登记校准证据格式，不能凭调用者自报 CALIBRATED 放行概率。
  requireValue(f.calibrationStatus!=='CALIBRATED'&&f.confidenceScore===null,'MI_ANALYSIS_CALIBRATION_UNQUALIFIED');
  requireValue(userEdit?f.category==='USER_EDITED':f.category!=='USER_EDITED','MI_ANALYSIS_EDIT_AREA_REJECTED');
  if(['bpmCandidates','beats','onsets','tonalCandidates','segmentCandidates'].includes(f.name))requireValue(f.category==='ESTIMATED','MI_ANALYSIS_CATEGORY_REJECTED');
  if(['samplePeak','rms','spectralFlux'].includes(f.name))requireValue(f.category==='MEASURED'&&f.confidenceLabel===null&&f.calibrationStatus==='NOT_APPLICABLE','MI_ANALYSIS_CATEGORY_REJECTED');
  if(['samplePeakDbfs','rmsDbfs','crestFactor'].includes(f.name))requireValue(f.category==='DERIVED'&&f.confidenceLabel===null&&f.calibrationStatus==='NOT_APPLICABLE','MI_ANALYSIS_CATEGORY_REJECTED');
  if(f.name==='lufs'){
   if(f.status==='READY')requireValue(f.category==='MEASURED'&&f.unit==='LUFS'&&f.method==='bs1770-stream-1; ITU-R BS.1770-5; mono/stereo; K-weighting;400ms/100ms;-70LUFS/-10LU gating'&&f.implementationVersion.startsWith('song-dsp-1/')&&typeof f.value==='number'&&f.value>=-70&&f.value<=30&&f.confidenceLabel===null&&f.calibrationStatus==='NOT_APPLICABLE','MI_ANALYSIS_LUFS_UNQUALIFIED');
   else requireValue(f.value===null&&['MI_LUFS_STANDARD_NOT_READY','MI_LUFS_TOO_SHORT','MI_LUFS_BELOW_GATE','MI_LUFS_CHANNEL_LAYOUT_UNKNOWN'].includes(f.reasonCode),'MI_ANALYSIS_LUFS_UNQUALIFIED');
  }
  if(f.name==='key'&&f.status==='READY')requireValue(f.value&&Number.isInteger(f.value.tonic)&&f.value.tonic>=0&&f.value.tonic<=11&&['major','minor'].includes(f.value.mode)&&Number.isFinite(f.value.score)&&Math.abs(f.value.score)<=1&&f.category==='ESTIMATED');
  if(f.name==='analysisWindows'&&f.status==='READY')requireValue(Array.isArray(f.value)&&f.value.length>0&&f.value.length<=241&&f.range&&f.value.every((w,i)=>w&&Number.isFinite(w.start)&&Number.isFinite(w.end)&&w.end>w.start&&w.start>=f.range[0]&&w.end<=f.range[1]&&Number.isInteger(w.featureFrames)&&w.featureFrames>=0&&Number.isFinite(w.contextStart)&&Number.isFinite(w.contextEnd)&&w.contextStart<=w.start&&w.contextEnd>=w.end&&(i===0?Math.abs(w.start-f.range[0])<1e-8:Math.abs(w.start-f.value[i-1].end)<1e-8))&&Math.abs(f.value.at(-1).end-f.range[1])<1e-8,'MI_ANALYSIS_WINDOWS_REJECTED');
  if(f.name==='keyCandidates'&&f.status==='READY')requireValue(Array.isArray(f.value)&&f.value.length<=24&&f.category==='ESTIMATED'&&f.value.every(x=>Number.isInteger(x.tonic)&&x.tonic>=0&&x.tonic<=11&&['major','minor'].includes(x.mode)&&Number.isFinite(x.score)&&Math.abs(x.score)<=1));

  if(f.category==='DERIVED'){requireValue(Array.isArray(f.sourceFields)&&f.sourceFields.length>0&&f.sourceFields.every(x=>typeof x==='string'));str(f.formulaVersion);}
 }
 for(const f of v.fields.filter(f=>f.category==='DERIVED'))requireValue(f.sourceFields.every(n=>n!==f.name&&names.has(n)),'MI_ANALYSIS_DERIVATION_REJECTED');
 requireValue(!v.asset.windowRange||v.asset.windowRange[1]-v.asset.windowRange[0]<=30.000000001||v.analysis.implementationVersion.startsWith('song-dsp-1/'),'MI_ANALYSIS_WINDOW_BUDGET');
 return freeze(v);
}
export function fromBasicAnalysis(result,{analysisId,observedAt}){
 requireValue(result?.schemaVersion===1&&result.kind==='MusicAnalysis'&&result.source==='BASIC_DSP'&&typeof result.provenance?.version==='string','MI_ANALYSIS_PRODUCER_REJECTED');
 requireValue(Array.isArray(result.range)&&result.range.length===2);const measurement=result.measurements;
 if(measurement){requireValue(['GATE_B_DSP_1','SONG_DSP_1'].includes(measurement.version)&&canonicalJson(measurement.config)===canonicalJson(measurement.version==='SONG_DSP_1'?SONG_CONFIG:GATE_B_CONFIG)&&measurement.windowEncoding==='PCM_F32LE_INTERLEAVED_V1','MI_ANALYSIS_FEATURE_CONFIG_REJECTED');str(measurement.implementationVersion);validSha(measurement.windowSha256);}
 const song=measurement?.version==='SONG_DSP_1';
 const implementationVersion=measurement?measurement.implementationVersion:'basic-adapter-0.5.0/librosa-'+result.provenance.version;
 const field=(name,value,unit,method,estimated=false,full=false)=>({name,value,unit,method,range:full?[0,result.duration]:result.range,status:value===null?'UNKNOWN':'READY',reasonCode:value===null?'LEGACY_FIELD_UNAVAILABLE':null,category:estimated?'ESTIMATED':'MEASURED',origin:estimated?'ALGORITHM_ESTIMATE':'AUDIO_MEASUREMENT',confidenceLabel:estimated?(value===null?'unknown':'low'):null,confidenceScore:null,calibrationStatus:estimated?'UNCALIBRATED':'NOT_APPLICABLE',implementationVersion,observedAt});
 const fields=[field('duration',result.duration,'s','soundfile.info',false,true),field('sampleRate',result.sampleRate,'Hz','soundfile.info',false,true),field('channels',result.channels,'count','soundfile.info',false,true),field('energy',result.energy,'linear_amplitude','librosa.feature.rms'),field('spectralCentroid',result.spectralCentroid,'Hz','librosa.feature.spectral_centroid'),field('chroma',result.chroma,'chroma_strength','librosa.feature.chroma_stft')];
 if(measurement){
  fields[3].method='librosa.rms; mono-channel-mean; soxr_hq:22050Hz; frame:2048; hop:512; center:true; zero-pad; max120-frame-samples';
  fields[4].method='librosa.spectral_centroid; mono-channel-mean;22050Hz; FFT:2048;hop:512;Hann;center:true;zero-pad';
  fields[5].method='librosa.chroma_stft; mono-channel-mean;22050Hz;FFT:2048;hop:512;Hann;center:true;norm:inf;frame-mean';
  fields.push(field('samplePeak',measurement.samplePeak,'linear_full_scale','max(abs(native PCM)); all channels; full-scale=1; no clipping'));
  fields.push(field('rms',measurement.rms,'linear_full_scale','sqrt(sum(native PCM^2)/(frames*channels)); entire selected window; full-scale=1; no downmix'));
  for(const [name,unit,method,sourceFields,formulaVersion] of [
   ['samplePeakDbfs','dBFS','20*log10(samplePeak/1); zero signal undefined',['samplePeak'],'amplitude-dbfs-1'],
   ['rmsDbfs','dBFS','20*log10(rms/1); zero signal undefined',['rms'],'amplitude-dbfs-1'],
   ['crestFactor','ratio','samplePeak/rms; same native PCM window/channels; not dynamic range',['samplePeak','rms'],'peak-over-rms-1']]){
   const f=field(name,measurement[name],unit,method);Object.assign(f,{category:'DERIVED',origin:'DATA_DERIVATION',sourceFields,formulaVersion});if(f.value===null)f.reasonCode=name==='crestFactor'?'ZERO_SIGNAL_UNDEFINED_RATIO':'ZERO_SIGNAL_DBFS_UNDEFINED';fields.push(f);
  }
  fields.push(field('spectralFlux',measurement.spectralFlux,'normalized_positive_L1','STFT mono22050Hz;Hann2048;hop512;center:false;L1-normalized magnitude;sum positive frame diff;frame-center time;omit first'));
  if(song){
   requireValue(measurement.implementationVersion.startsWith('song-dsp-1/')&&measurement.lufs?.version==='bs1770-stream-1'&&measurement.key?.version==='kk-chroma-1','MI_ANALYSIS_FEATURE_CONFIG_REJECTED');
   const loudness=measurement.lufs;requireValue(['READY','UNKNOWN','NOT_READY'].includes(loudness.status)&&((result.channels<=2&&loudness.channelLayout===(result.channels===1?'mono':'stereo'))||(result.channels>2&&loudness.status==='NOT_READY')),'MI_ANALYSIS_LUFS_UNQUALIFIED');
   fields.push({...field('lufs',loudness.value,'LUFS','bs1770-stream-1; ITU-R BS.1770-5; mono/stereo; K-weighting;400ms/100ms;-70LUFS/-10LU gating'),status:loudness.status,reasonCode:loudness.reasonCode});
   fields.push(field('loudnessDetails',loudness,'metadata','native rate; continuous K-weighting; full-range absolute/relative gating; no true peak'));
   const key=measurement.key;
   fields.push({...field('key',key.primary,'key',key.method,true),status:key.status,reasonCode:key.reasonCode});
   fields.push(field('keyCandidates',key.candidates,'raw_correlation',key.method,true));
   fields.push(field('analysisWindows',measurement.windows,'s','unique half-open core ownership; streaming soxr; overlapped context'));
   fields.push(field('aggregation',measurement.aggregation,'metadata','native sample-weighted RMS; global loudness gates; frame-weighted chroma; bounded peak-bucket curves'));
   fields[3].method='non-centered RMS2048/hop512; continuous soxr22050; unique global frame centers; max1200 peak buckets';
   fields[4].method='spectral centroid; same unique global frames; max1200 peak buckets';
   fields[5].method='chroma_stft;FFT8192/hop2048;tuning:0;norm:inf;time-weighted unique frame mean;continuous soxr22050';
  }else fields.push({...field('lufs',null,'LUFS','standard loudness implementation not qualified'),status:'NOT_READY',reasonCode:'MI_LUFS_STANDARD_NOT_READY'});
 }
 for(const [name,method,unit] of [['bpmCandidates','librosa.beat.beat_track','BPM'],['beats','librosa.beat.beat_track','s'],['onsets','librosa.onset.onset_detect','s'],['tonalCandidates','chroma_peak_not_key_classifier','pitch_class'],['segmentCandidates','chroma_block_difference','s']])fields.push(field(name,result[name]??null,unit,method,true));
 return validateAnalysis({schemaVersion:ANALYSIS_VERSION,asset:{assetId:result.assetId,sourceSha256:result.sourceSha256,duration:result.duration,...(measurement?{windowSha256:measurement.windowSha256,windowEncoding:measurement.windowEncoding,windowRange:result.range}:{})},analysis:{analysisId,analysisVersion:ANALYSIS_VERSION,implementationVersion,modelRevision:null,observedAt},fields});
}
export function legacyProfileAdapter(value){
 const copy=JSON.parse(safeJson(value));requireValue(copy.schemaVersion===1,'MI_LEGACY_PROFILE_REJECTED');
 return freeze({format:'LEGACY_MI_0_4',data:copy,missingEvidence:['analysisVersion','sourceSha256','modelRevision','observedAt'].filter(k=>!Object.hasOwn(copy,k)),evidenceStatus:'LEGACY_UNQUALIFIED'});
}
export function validateUserEdit(value){
 const v=JSON.parse(safeJson(value,65536));keys(v,['schemaVersion','category','origin','editId','sourceAnalysisId','assetId','sourceSha256','createdAt','changes']);
 requireValue(v.schemaVersion===ANALYSIS_VERSION&&v.category==='USER_EDITED'&&v.origin==='USER_INPUT','MI_PROFILE_REJECTED');validId(v.editId);validId(v.sourceAnalysisId);validAsset(v.assetId);validSha(v.sourceSha256);time(v.createdAt);
 requireValue(Array.isArray(v.changes)&&v.changes.length>0&&v.changes.length<=32,'MI_PROFILE_REJECTED');const names=new Set();
 for(const c of v.changes){keys(c,['name','value']);str(c.name,100);requireValue(!names.has(c.name)&&!['assetId','sourceSha256','windowSha256','windowEncoding','windowRange','analysisId','modelRevision','observedAt'].includes(c.name),'MI_PROFILE_REJECTED');names.add(c.name);}
 return freeze(v);
}
