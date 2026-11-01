export function workerErrorDetail(detail,home){
 // Python 的路径 repr 会重复反斜杠；先去除已知根，再保留后面的真实错误原因。
 for(const root of [home.replaceAll('\\','\\\\'),home.replaceAll('\\','/'),home])detail=detail.replaceAll(root,'[MUSIC_HOME]');
 return redactModelLog(detail);
}
export function redactModelLog(value){
 if(typeof value==='string')return value.replace(/https?:\/\/\S+/g,'[URL]').replace(/[A-Za-z]:[\\/][^\r\n]*/g,'[LOCAL_PATH]').replace(/\b(Bearer\s+|hf_)[A-Za-z0-9_.-]+/gi,'[CREDENTIAL]');
 if(Array.isArray(value))return value.map(redactModelLog);
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,/token|password|secret|authorization/i.test(k)?'[REDACTED]':redactModelLog(v)]));
 return value;
}
