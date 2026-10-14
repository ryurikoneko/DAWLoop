import {createHash} from 'node:crypto';
const scales={major:[0,2,4,5,7,9,11],minor:[0,2,3,5,7,8,10]};
const degrees={I:0,II:1,III:2,IV:3,V:4,VI:5,VII:6};
const number=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
export function compose(p){
  if(p.mode!=='original'||p.abc!==undefined||!number(p.seed,0,4294967295)||!Number.isInteger(p.seed)||!number(p.tempo,20,300)||!Number.isInteger(p.key)||!number(p.key,0,11)||!scales[p.scale]||!number(p.density,.1,1)||!Number.isInteger(p.bars)||!number(p.bars,1,32)||!['even','syncopated','sparse'].includes(p.rhythm)||!Number.isInteger(p.candidates)||!number(p.candidates,1,4)||!Array.isArray(p.meter)||p.meter.length!==2||!Number.isInteger(p.meter[0])||!number(p.meter[0],1,12)||![2,4,8].includes(p.meter[1])||!Array.isArray(p.energyCurve)||p.energyCurve.length<1||p.energyCurve.length>32||p.energyCurve.some(v=>!number(v,0,1)))throw Error('MI_COMPOSITION_REJECTED');
  const progression=String(p.progression).trim().split(/\s+/).map(v=>degrees[v.toUpperCase()]);
  if(!progression.length||progression.length>16||progression.some(v=>v===undefined))throw Error('MI_COMPOSITION_REJECTED');
  const scale=scales[p.scale],beats=p.meter[0]*4/p.meter[1],candidates=[];
  const mean=p.profile?.energy?.mean,profileEnergy=number(mean,0,10)?Math.min(1,mean*4):.5;
  const chroma=p.profile?.harmonic?.chroma;
  if(chroma!==undefined&&(!Array.isArray(chroma)||chroma.length!==12||chroma.some(v=>!number(v,0,100))))throw Error('MI_COMPOSITION_REJECTED');
  for(let c=0;c<p.candidates;c++){
    let state=(p.seed+c*2654435761)>>>0;
    const rand=()=>{state=(state+0x6D2B79F5)>>>0;let x=state;x=Math.imul(x^(x>>>15),x|1);x^=x+Math.imul(x^(x>>>7),x|61);return ((x^(x>>>14))>>>0)/4294967296;};
    const notes=[],chords=[];let last=60+p.key;
    for(let bar=0;bar<p.bars;bar++){
      const degree=progression[bar%progression.length],tones=[degree,(degree+2)%7,(degree+4)%7];
      const energy=p.energyCurve[Math.min(p.energyCurve.length-1,Math.floor(bar*p.energyCurve.length/p.bars))];
      const chordPitches=tones.map(d=>48+p.key+scale[d]);chords.push({start:bar*beats,duration:beats,degree:degree+1,pitches:chordPitches});
      for(const pitch of chordPitches)notes.push({pitch,start:bar*beats,duration:beats*.94,velocity:Math.round(40+energy*25),part:1});
      const step=p.rhythm==='sparse'?1:p.rhythm==='syncopated'?.5:1;
      for(let local=0;local<beats;local+=step){
        if(local>0&&rand()>p.density*(.5+.5*energy))continue;
        const strong=local===0||local%2===0,pool=strong?tones:[0,1,2,3,4,5,6];
        const choices=pool.flatMap(d=>[60+p.key+scale[d],72+p.key+scale[d]]).filter(n=>n<=84);
        const weights=choices.map(n=>1/(1+Math.abs(n-last))*(1+(chroma?.[n%12]??0)));
        let pick=rand()*weights.reduce((a,b)=>a+b,0),pitch=choices[0];
        for(let i=0;i<choices.length;i++){pick-=weights[i];if(pick<=0){pitch=choices[i];break;}}
        if(bar===p.bars-1&&local+step>=beats)pitch=60+p.key;
        last=pitch;notes.push({pitch,start:bar*beats+local,duration:Math.min(step*.85,beats-local),velocity:Math.round(55+energy*30+profileEnergy*12),part:0});
      }
    }
    candidates.push({schemaVersion:1,tempo:p.tempo,meter:p.meter,tempoMap:[{start:0,bpm:p.tempo}],notes,source:'RULE_BASED',edits:[],chords,provenance:{provider:'Lightweight Symbolic',version:'1',seed:p.seed,candidate:c,profileSource:p.profileSource??'USER_INPUT',profileSha256:p.profile?createHash('sha256').update(JSON.stringify(p.profile)).digest('hex'):null,usedProfileFields:['energy.mean','harmonic.chroma'],constraints:{key:p.key,scale:p.scale,progression:p.progression,density:p.density,rhythm:p.rhythm,bars:p.bars,energyCurve:p.energyCurve}}});
  }
  return {schemaVersion:1,source:'RULE_BASED',candidates};
}
