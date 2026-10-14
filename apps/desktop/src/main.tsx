import React,{useEffect,useState} from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { I18nextProvider } from 'react-i18next';
import { createDesktopI18n } from './i18n';
import {Splash} from './Splash';
import './style.css';
import './brand.css';
function DesktopStart(){
 const [product,setProduct]=useState<import('../../../packages/shared-types/contracts').DesktopEnvironment>(),[loaded,setLoaded]=useState(false),[ready,setReady]=useState(false);
 const [i18n]=useState(()=>createDesktopI18n('en-US'));
 useEffect(()=>{let mounted=true;void window.dawloop.call('getDesktopEnvironment').then(async result=>{if(!mounted)return;if(result.ok){setProduct(result.data);document.documentElement.dataset.reducedMotion=String(result.data.reducedMotion??false);await i18n.changeLanguage(result.data.language);}setLoaded(true);}).catch(()=>setLoaded(true));return()=>{mounted=false;};},[i18n]);
 useEffect(()=>{document.documentElement.lang=i18n.language;const update=(language:string)=>{document.documentElement.lang=language;};i18n.on('languageChanged',update);return()=>{i18n.off('languageChanged',update);};},[i18n]);
 return <I18nextProvider i18n={i18n}>{loaded&&<App development={product?.development} environment={product} onInitialized={()=>setReady(true)}/>}<Splash version={product?.appVersion} ready={ready} reduced={product?.reducedMotion}/></I18nextProvider>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><DesktopStart/></React.StrictMode>);
