import {useTranslation} from 'react-i18next';
import type {Model} from '../../../packages/shared-types/music-contracts';

export function TranscriptionAvailability({model,developer,configure}:{model:Model|undefined;developer:boolean;configure:()=>void}){
  const {t}=useTranslation('music');
  return <section aria-label={t('song.transcriptionStatus')} className="mi-provider-status"><h4>{model?.modelId??t('unknown')}</h4><p>{model?t('states.'+model.status,{defaultValue:t('unknown')}):t('song.checkPending')}</p>{model?.reason&&<p role="status">{t('errors.'+model.reason,{defaultValue:t('modelNotReady')})}</p>}{model?.id==='sheetsage2'&&<p>{t('sheetTimingWarning')}</p>}<p>{t('song.componentNeed')}</p>{model?.requiredBytes!=null&&<p>{t('song.installSize',{gib:(model.requiredBytes/1073741824).toFixed(2)})}</p>}{model&&<p>{model.license}</p>}<button onClick={configure}>{t('models')}</button>{developer&&model&&<pre>{JSON.stringify(model,null,2)}</pre>}</section>;
}
