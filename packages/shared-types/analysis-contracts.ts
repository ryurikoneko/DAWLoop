export type AnalysisCategory='MEASURED'|'ESTIMATED'|'DERIVED'|'GENERATED'|'USER_EDITED';
export type JsonValue=null|boolean|number|string|JsonValue[]|{[key:string]:JsonValue};
export interface AnalysisFieldV0_5 {
 name:string;category:AnalysisCategory;value:JsonValue;unit:string|null;method:string;range:[number,number]|null;
 status:'READY'|'UNKNOWN'|'NOT_READY'|'FAILED';reasonCode:string|null;
 confidenceLabel:'high'|'medium'|'low'|'very-low'|'unknown'|null;confidenceScore:null;
 calibrationStatus:'UNCALIBRATED'|'NOT_APPLICABLE';origin:'AUDIO_MEASUREMENT'|'ALGORITHM_ESTIMATE'|'DATA_DERIVATION'|'RULE_BASED_DRAFT'|'LLM_GENERATED'|'USER_INPUT';
 implementationVersion:string;observedAt:string;sourceFields?:string[];formulaVersion?:string;
}
export interface MusicAnalysisResultV0_5 {
 schemaVersion:'0.5';asset:{assetId:string;sourceSha256:string;duration:number|null;windowSha256?:string;windowEncoding?:'PCM_F32LE_INTERLEAVED_V1';windowRange?:[number,number]};
 analysis:{analysisId:string;analysisVersion:'0.5';implementationVersion:string;modelRevision:string|null;observedAt:string};fields:AnalysisFieldV0_5[];
}
export interface AnalysisUserEditV0_5 {
 schemaVersion:'0.5';category:'USER_EDITED';origin:'USER_INPUT';editId:string;sourceAnalysisId:string;assetId:string;sourceSha256:string;createdAt:string;changes:{name:string;value:JsonValue}[];
}
