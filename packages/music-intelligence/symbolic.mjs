// 只接受已明确支持的 ABC 子集；未知语法拒绝，避免静默丢声部或时值。
export function parseAbc(text) {
  if(typeof text!=='string'||text.length>65536)throw Error('INVALID_ABC');
  const lines=text.split(/\r?\n/);let tempo=120,meter=[4,4],unit=.5,key='C';const body=[];
  for(const line of lines){const m=line.match(/^([A-Z]):\s*(.*)$/);if(!m){if(line.trim()&&!line.startsWith('%'))body.push(line);continue;}
    if(m[1]==='Q')tempo=Number(m[2].split('=').at(-1));if(m[1]==='M')meter=m[2].split('/').map(Number);if(m[1]==='L'){const [a,b]=m[2].split('/').map(Number);unit=4*a/b;}if(m[1]==='K')key=m[2];if(!['X','T','Q','M','L','K'].includes(m[1]))throw Error('ABC_UNSUPPORTED');}
  if(key!=='C'||!Number.isFinite(unit)||unit<=0)throw Error('ABC_UNSUPPORTED');
  const tokens=body.join(' ').replace(/\|/g,' ').match(/\^[A-Ga-g][,']*\d*(?:\/\d*)?|_[A-Ga-g][,']*\d*(?:\/\d*)?|[A-Ga-gz][,']*\d*(?:\/\d*)?|\S+/g)??[];
  let time=0;const notes=[];const pitches={C:60,D:62,E:64,F:65,G:67,A:69,B:71};
  for(const token of tokens){const m=token.match(/^([\^_]?)([A-Ga-gz])([,']*)(\d*)(?:\/(\d*))?$/);if(!m)throw Error('ABC_UNSUPPORTED');
    const duration=unit*(Number(m[4])||1)/(token.includes('/')?(Number(m[5])||2):1);if(!(duration>0))throw Error('INVALID_NOTE');
    if(m[2]!=='z'){const pitch=pitches[m[2].toUpperCase()]+(m[2]===m[2].toLowerCase()?12:0)+12*([...m[3]].filter(x=>x==="'").length-[...m[3]].filter(x=>x===',').length)+(m[1]==='^'?1:m[1]==='_'?-1:0);notes.push({pitch,start:time,duration,velocity:90,part:0});}time+=duration;}
  return {schemaVersion:1,tempo,meter,tempoMap:[{start:0,bpm:tempo}],notes,source:'USER_EDITED',edits:[]};
}
