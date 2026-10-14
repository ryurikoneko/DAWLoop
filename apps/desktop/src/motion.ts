import {useLayoutEffect,useRef} from 'react';

export function useWorkspaceMotion(key:string,active=true){
  const ref=useRef<HTMLElement|null>(null),previous=useRef(key);
  useLayoutEffect(()=>{
    const changed=previous.current!==key;previous.current=key;
    if(!changed||!active||!ref.current||document.documentElement.dataset.reducedMotion==='true'||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
    const animation=ref.current.animate?.([{opacity:1,transform:'translateY(0)'},{opacity:.82,transform:'translateY(3px)',offset:.25},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'cubic-bezier(.2,.7,.3,1)'});
    return()=>animation?.cancel();
  },[key,active]);
  return ref;
}
