"""人工生成对照：独立存储提示词、来源与评分，不调用生成平台。"""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import uuid
import numpy as np
import soundfile as sf
from style_lab import StyleLab,digest

SCORES=('liking','productionQuality','targetCloseness','melody','harmonyEmotion','timbre','groove','arrangement','vocals','direction')
DEFAULT_LYRICS='[Verse]\nCity lights are drifting by\nPaper stars across the sky\nEvery step becomes a sound\nWe can turn this night around\n[Chorus]\nCarry this little spark with me\nLet it rise and let it breathe\nThrough the quiet, through the glow\nFind a place where we can grow\n[Bridge]\nWhen the world begins to slow\nHear the heartbeat down below'
BASE='Japanese electronic pop with kawaii future bass influences. Create an original song with a new melody and harmony.'
MEASURED='Let the energy rise and fall across the full song, with noticeable contrast between quieter passages and stronger peaks.'
PERSONAL='Use a nimble singable melody, expressive vocals, a bouncy bass groove, soft atmospheric pads and deep sub bass. Balance powerful passages with a smooth emotional transition and a satisfying ending.'
DEFAULTS=dict(platform='Suno',modelVersion='',language='English',vocalType='light melodic female',targetSeconds=120,bpm=140,lyrics=DEFAULT_LYRICS,replicates=3)
KEYS={'generationWorkspace':set(),'generationAnalysis':{'trial'},'generationCreate':{'settings'},'generationImport':{'prompt','metadata','path'},'generationFailure':{'prompt','reason'},'generationReject':{'trial','reason'},'generationRate':{'trial','ratings'},'generationReveal':{'trial'},'generationClip':{'trial','start','end'},'generationRevise':{'prompt','old','new','reason','trials'}}


def encoded(value):return json.dumps(value,ensure_ascii=False,allow_nan=False)
def identity():return uuid.uuid4().hex
def text(value,maximum=2000):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum:raise ValueError('INVALID_GENERATION_TEXT')
    return value.strip()


class GenerationLab:
    def __init__(self,root):
        self.root=Path(root).resolve();self.folder=self.root/'phase7';self.folder.mkdir(exist_ok=True)
        self.db=sqlite3.connect(self.folder/'generation.sqlite',timeout=10);self.db.row_factory=sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,settings TEXT,evidence TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS prompts(id TEXT PRIMARY KEY,experiment TEXT,group_name TEXT,version INTEGER,parent TEXT,body TEXT,reason TEXT,evidence TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS trials(id TEXT PRIMARY KEY,prompt TEXT,asset TEXT,source_sha TEXT,metadata TEXT,blind_order TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,trial TEXT,kind TEXT,body TEXT,created REAL);
        ''')

    def event(self,trial,kind,body):
        with self.db:self.db.execute('INSERT INTO events(trial,kind,body,created) VALUES(?,?,?,?)',(trial,kind,encoded(body),time.time()))

    def audit(self):
        evidence=[];excluded=[];reference=self.root/'structure'
        for p in sorted(reference.glob('*.json')):
            s=json.loads(p.read_text(encoding='utf-8'));energy=np.asarray(s['curves']['energy'],dtype=float)
            if not len(energy) or not np.isfinite(energy).all():continue
            low,high=np.quantile(energy[:,1],[.1,.9]);delta=float(20*np.log10(max(high,1e-12)/max(low,1e-12)))
            evidence.append(dict(asset=s['asset'],sourceSha256=s['sourceSha256'],range=[0,s['coverage']['duration']],dspJob=s['dspJob'],vectorVersion=s['vectorVersion'],method='full-song RMS q90/q10 dB contrast',energyContrastDb=delta,structureValidation='CANDIDATE_ONLY',structureSha256=digest(p)))
        if not evidence:raise ValueError('REFERENCE_ANALYSIS_REQUIRED')
        personal=self.root/'phase6/personal-profile.json';preferences=json.loads(personal.read_text(encoding='utf-8')) if personal.exists() else None
        if not preferences or not preferences.get('sourceRatingEvents'):raise ValueError('PERSONAL_EVIDENCE_REQUIRED')
        excluded=['CLAP voice classifications','CLAP dense label','unverified timbre/instrument identities','uncalibrated BPM/key','unverified chorus/drop labels','artist-specific causal attribution']
        return dict(measurements=evidence,energyContrastMedianDb=float(np.median([e['energyContrastDb'] for e in evidence])),personalSourceSha256=digest(personal),ratingEvents=preferences['sourceRatingEvents'],personalClaims=preferences['claims'],excluded=excluded,oldDraftSourceSha256=digest(self.root/'phase6/suno-experiment.json') if (self.root/'phase6/suno-experiment.json').exists() else None)

    def create(self,settings):
        required={'platform','modelVersion','language','vocalType','targetSeconds','bpm','lyrics','replicates'}
        if not isinstance(settings,dict) or not required.issubset(settings) or set(settings)-required-{'structurePlan'}:raise ValueError('INVALID_EXPERIMENT_SETTINGS')
        if 'structurePlan' in settings and (not isinstance(settings['structurePlan'],str) or len(settings['structurePlan'])>2000):raise ValueError('INVALID_STRUCTURE_PLAN')
        for k in ('platform','modelVersion','language','vocalType'):text(settings[k],100)
        text(settings['lyrics'],8000)
        if type(settings['targetSeconds'])!=int or not 30<=settings['targetSeconds']<=600 or type(settings['bpm'])!=int or not 60<=settings['bpm']<=220 or type(settings['replicates'])!=int or not 2<=settings['replicates']<=5:raise ValueError('INVALID_EXPERIMENT_SETTINGS')
        audit=self.audit();experiment=identity();now=time.time()
        audit['structureControl']=dict(text=settings.get('structurePlan',''),source='USER_DEFINED_CREATIVE_CONTROL_NOT_DETECTED_STRUCTURE')
        if audit['energyContrastMedianDb']<=1:raise ValueError('REFERENCE_ENERGY_CONTRAST_NOT_SUPPORTED')
        common=f" {settings['bpm']} BPM; {settings['language']} lyrics; {settings['vocalType']} vocals; target duration {settings['targetSeconds']} seconds. Use the same supplied lyrics."
        if settings.get('structurePlan','').strip():common+=' '+settings['structurePlan'].strip()
        with self.db:
            self.db.execute('INSERT INTO experiments VALUES(?,?,?,?)',(experiment,encoded(settings),encoded(audit),now))
            for group,body,evidence in [('A',BASE+common,dict(source='GENERIC_EXPERIMENT_TASK_NO_PERSONAL_DATA')),('B',BASE+common+' '+MEASURED,dict(source='MEASURED_ENERGY_CONTRAST_TO_COMPOSITION_REQUEST',measurementIds=[e['asset'] for e in audit['measurements']])),('C',BASE+common+' '+MEASURED+' '+PERSONAL,dict(source='MEASURED_CONTRAST_PLUS_USER_EXPLICIT_PREFERENCES',ratingEvents=audit['ratingEvents'],weights=None))]:
                self.db.execute('INSERT INTO prompts VALUES(?,?,?,?,?,?,?,?,?)',(identity(),experiment,group,1,None,body,'Initial controlled comparison',encoded(evidence),now))
        return experiment

    def prompt(self,identity):
        row=self.db.execute('SELECT * FROM prompts WHERE id=?',(identity,)).fetchone()
        if not row:raise ValueError('UNKNOWN_EXPERIMENT_PROMPT')
        return row

    def trial(self,identity):
        row=self.db.execute('SELECT * FROM trials WHERE id=?',(identity,)).fetchone()
        if not row:raise ValueError('UNKNOWN_GENERATION_TRIAL')
        return row

    def latest(self,trial,kind):
        row=self.db.execute('SELECT id,body,created FROM events WHERE trial=? AND kind=? ORDER BY id DESC LIMIT 1',(trial,kind)).fetchone()
        return dict(id=row['id'],created=row['created'],**json.loads(row['body'])) if row else None

    def imported(self,prompt,metadata,path):
        p=self.prompt(prompt)
        fields={'generatedAt','modelVersion','platform','batchId','seed','settings','sourceNote'}
        if not isinstance(metadata,dict) or set(metadata)!=fields:raise ValueError('INVALID_GENERATION_METADATA')
        for k in ('generatedAt','modelVersion','platform'):text(metadata[k],100)
        from datetime import datetime
        try:datetime.fromisoformat(metadata['generatedAt'].replace('Z','+00:00'))
        except ValueError:raise ValueError('INVALID_GENERATION_DATE')
        if metadata['seed'] is not None and (type(metadata['seed']) not in (int,str) or len(str(metadata['seed']))>100):raise ValueError('INVALID_GENERATION_SEED')
        if not isinstance(metadata['settings'],dict) or len(encoded(metadata))>20000:raise ValueError('INVALID_GENERATION_METADATA')
        if metadata['batchId'] is not None:text(metadata['batchId'],100)
        if not isinstance(metadata['sourceNote'],str) or len(metadata['sourceNote'])>1000:raise ValueError('INVALID_GENERATION_METADATA')
        path=Path(path).resolve()
        if path.suffix.lower() not in ('.wav','.mp3','.flac'):raise ValueError('INVALID_GENERATION_AUDIO')
        sha=digest(path)
        reference=sqlite3.connect(self.root/'library.sqlite')
        try:
            if reference.execute('SELECT 1 FROM assets WHERE sha=?',(sha,)).fetchone():raise ValueError('REFERENCE_AUDIO_IS_NOT_GENERATED_RESULT')
        finally:reference.close()
        if self.db.execute('SELECT 1 FROM trials WHERE source_sha=?',(sha,)).fetchone():raise ValueError('GENERATION_AUDIO_ALREADY_IMPORTED')
        info=sf.info(path)
        if not 0<info.duration<=7200 or not 1<=info.channels<=8:raise ValueError('GENERATION_AUDIO_BUDGET')
        lab=StyleLab(self.folder/'audio-research');asset=lab.import_audio([path])[0];lab.db.close()
        trial=identity()
        with self.db:self.db.execute('INSERT INTO trials VALUES(?,?,?,?,?,?,?)',(trial,prompt,asset,sha,encoded(metadata),identity(),time.time()))
        settings=json.loads(self.db.execute('SELECT settings FROM experiments WHERE id=?',(p['experiment'],)).fetchone()[0])
        comparable=metadata['platform']==settings['platform'] and metadata['modelVersion']==settings['modelVersion'] and all(metadata['settings'].get(k)==settings[k] for k in ('language','vocalType','targetSeconds','bpm','lyrics'))
        comparable=comparable and metadata['settings'].get('structurePlan','')==settings.get('structurePlan','')
        self.event(trial,'IMPORTED',dict(source='USER_REPORTED_GENERATION',metadataVerifiedByPlatform=False,settingsMatch=comparable,sourceSha256=sha,promptVersion=p['version'],fileDuration=info.duration))
        return trial

    def failure(self,prompt,reason):
        self.prompt(prompt);trial=identity()
        with self.db:self.db.execute('INSERT INTO trials VALUES(?,?,?,?,?,?,?)',(trial,prompt,None,None,'{}',identity(),time.time()))
        self.event(trial,'GENERATION_FAILED',dict(reason=text(reason)))
        return trial

    def reject(self,trial,reason):self.trial(trial);self.event(trial,'REJECTED',dict(reason=text(reason)));return True

    def clip(self,trial,start,end):
        t=self.trial(trial)
        if not t['asset']:raise ValueError('GENERATION_AUDIO_MISSING')
        lab=StyleLab(self.folder/'audio-research');a=lab.db.execute('SELECT * FROM assets WHERE id=?',(t['asset'],)).fetchone();lab.db.close()
        if digest(a['path'])!=t['source_sha']:raise ValueError('GENERATION_SOURCE_CHANGED')
        info=sf.info(a['path'])
        if not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end)) or not 0<=start<end<=info.duration:raise ValueError('INVALID_GENERATION_RANGE')
        # 盲听素材名称只含随机身份；原音频不改写。
        name=hashlib.sha256(f'{trial}:{start}:{end}'.encode()).hexdigest()+'.wav';folder=self.root/'audition';folder.mkdir(exist_ok=True);target=folder/name
        if not target.exists():
            with sf.SoundFile(a['path']) as reader,sf.SoundFile(target.with_suffix('.partial'),'w',samplerate=info.samplerate,channels=info.channels,format='WAV',subtype='PCM_16') as writer:
                reader.seek(round(start*info.samplerate));remaining=round(end*info.samplerate)-round(start*info.samplerate)
                while remaining:
                    block=reader.read(min(65536,remaining),dtype='float32',always_2d=True)
                    if not len(block):raise ValueError('GENERATION_AUDIO_TRUNCATED')
                    writer.write(block);remaining-=len(block)
            target.with_suffix('.partial').replace(target)
        self.event(trial,'PREVIEW',dict(start=start,end=end,sourceSha256=t['source_sha']))
        return str(target)

    def rate(self,trial,ratings):
        t=self.trial(trial)
        if not t['asset'] or self.latest(trial,'GENERATION_FAILED') or self.latest(trial,'REJECTED'):raise ValueError('GENERATION_NOT_RATEABLE')
        fields=set(SCORES)|{'wouldKeep','notes','reviewed'}
        if not isinstance(ratings,dict) or set(ratings)!=fields or ratings['reviewed'] is not True:raise ValueError('INVALID_GENERATION_REVIEW')
        if any(x is not None and (type(x)!=int or not 1<=x<=5) for x in (ratings[k] for k in SCORES)):raise ValueError('INVALID_GENERATION_SCORE')
        if ratings['wouldKeep'] not in ('yes','no','unknown') or not isinstance(ratings['notes'],str) or len(ratings['notes'])>4000:raise ValueError('INVALID_GENERATION_REVIEW')
        preview=self.latest(trial,'PREVIEW')
        if not preview:raise ValueError('LISTEN_BEFORE_GENERATION_REVIEW')
        self.event(trial,'RATING',dict(ratings=ratings,range=dict(start=preview['start'],end=preview['end']),sourceSha256=t['source_sha'],revealedBeforeRating=self.latest(trial,'REVEALED') is not None))
        return True

    def reveal(self,trial):
        t=self.trial(trial)
        if not self.latest(trial,'RATING'):raise ValueError('RATE_BEFORE_REVEAL')
        self.event(trial,'REVEALED',{})
        p=self.prompt(t['prompt'])
        return dict(group=p['group_name'],promptVersion=p['version'],prompt=p['body'],metadata=json.loads(t['metadata']))

    def revise(self,prompt,old,new,reason,trials):
        p=self.prompt(prompt);old=text(old,1000);new=text(new,1000);reason=text(reason)
        if old==new or p['body'].count(old)!=1 or not isinstance(trials,list) or not 1<=len(trials)<=30:raise ValueError('ONE_PROMPT_CHANGE_REQUIRED')
        evidence=[]
        for trial in trials:
            t=self.trial(trial);r=self.latest(trial,'RATING')
            if t['prompt']!=prompt or not r or self.latest(trial,'REJECTED'):raise ValueError('RATED_PROMPT_EVIDENCE_REQUIRED')
            evidence.append(dict(trial=trial,ratingEventId=r['id']))
        version=self.db.execute('SELECT MAX(version) FROM prompts WHERE experiment=? AND group_name=?',(p['experiment'],p['group_name'])).fetchone()[0]+1
        body=p['body'].replace(old,new,1);identity_=identity()
        if len(body)>10000:raise ValueError('PROMPT_TOO_LONG')
        with self.db:self.db.execute('INSERT INTO prompts VALUES(?,?,?,?,?,?,?,?,?)',(identity_,p['experiment'],p['group_name'],version,prompt,body,reason,encoded(dict(source='USER_CONFIRMED_SINGLE_SPAN_REVISION',old=old,new=new,trials=evidence,causalImprovementProven=False)),time.time()))
        return identity_

    def workspace(self,experiment=None):
        experiments=[dict(id=r['id'],created=r['created'],modelVersion=json.loads(r['settings'])['modelVersion']) for r in self.db.execute('SELECT * FROM experiments ORDER BY created DESC')]
        e=self.db.execute('SELECT * FROM experiments WHERE id=?',(experiment,)).fetchone() if experiment else self.db.execute('SELECT * FROM experiments ORDER BY created DESC LIMIT 1').fetchone()
        if experiment and not e:raise ValueError('UNKNOWN_EXPERIMENT')
        if not e:return dict(experiment=None,prompts=[],trials=[],blind=[],summary=[],audit=None,defaults=DEFAULTS,suggestions=[],experiments=experiments)
        prompts=[dict(p,evidence=json.loads(p['evidence'])) for p in self.db.execute('SELECT * FROM prompts WHERE experiment=? ORDER BY group_name,version',(e['id'],))];ids={p['id']:p for p in prompts}
        rows=[t for t in self.db.execute('SELECT * FROM trials ORDER BY created') if t['prompt'] in ids];visible=[];blind=[];buckets={g:[] for g in 'ABC'}
        audio=StyleLab(self.folder/'audio-research')
        for t in rows:
            r=self.latest(t['id'],'RATING');imported=self.latest(t['id'],'IMPORTED');rejected=self.latest(t['id'],'REJECTED');failed=self.latest(t['id'],'GENERATION_FAILED');analysis=self.latest(t['id'],'ANALYSIS')
            a=audio.db.execute('SELECT * FROM assets WHERE id=?',(t['asset'],)).fetchone() if t['asset'] else None
            available=bool(a and Path(a['path']).is_file());duration=sf.info(a['path']).duration if available else None
            row=dict(id=t['id'],prompt=t['prompt'],group=ids[t['prompt']]['group_name'],promptVersion=ids[t['prompt']]['version'],state='FAILED' if failed else 'REJECTED' if rejected else 'SOURCE_MISSING' if not available else 'IMPORTED',duration=duration,metadata=json.loads(t['metadata']),ratings=r['ratings'] if r else None,analysis=analysis,settingsMatch=imported['settingsMatch'] if imported else False)
            visible.append(row);buckets[row['group']].append(row)
            if available and not failed and not rejected:blind.append(dict(id=t['id'],order=t['blind_order'],duration=duration,ratings=row['ratings']))
        audio.db.close();blind.sort(key=lambda t:t.pop('order'))
        for i,t in enumerate(blind):t['alias']=f'Track {i+1:02}'
        summary=[]
        for prompt in prompts:
            group=prompt['group_name'];items=[t for t in buckets[group] if t['prompt']==prompt['id']]
            valid=[t for t in items if t['ratings'] and t['state']=='IMPORTED' and t['settingsMatch']]
            metrics={}
            for k in SCORES:
                values=[t['ratings'][k] for t in valid if t['ratings'][k] is not None]
                metrics[k]=dict(n=len(values),mean=float(np.mean(values)) if values else None)
            summary.append(dict(group=group,version=prompt['version'],prompt=prompt['id'],attempts=len(items),failed=sum(t['state']=='FAILED' for t in items),rejected=sum(t['state']=='REJECTED' for t in items),matchedRated=len(valid),metrics=metrics,interpretation='DESCRIPTIVE_ONLY_NO_CAUSAL_WINNER'))
        suggestions=[]
        rules=[('melody','Japanese electronic pop','Melody-led Japanese pop','尝试加强旋律主导'),('timbre','electronic pop','soft-toned electronic pop','尝试柔和一点的音色'),('arrangement',MEASURED,'Build a gradual emotional transition between quieter passages and stronger peaks.','尝试更明确的渐进过渡')]
        for p in prompts:
            rated=[t for t in visible if t['prompt']==p['id'] and t['state']=='IMPORTED' and t['ratings']]
            for field,old,new,description in rules:
                low=[t for t in rated if t['ratings'][field] is not None and t['ratings'][field]<=2]
                if low and p['body'].count(old)==1:suggestions.append(dict(prompt=p['id'],old=old,new=new,reason=description,trials=[t['id'] for t in low],causalEffectProven=False))
        return dict(experiment=dict(id=e['id'],settings=json.loads(e['settings']),created=e['created']),prompts=prompts,trials=visible,blind=blind,summary=summary,audit=json.loads(e['evidence']),defaults=DEFAULTS,suggestions=suggestions,experiments=experiments)

    def analysis(self,trial):
        t=self.trial(trial);result=json.loads((self.folder/'comparisons'/(t['id']+'.json')).read_text(encoding='utf-8'))
        if result['sourceSha256']!=t['source_sha']:raise ValueError('GENERATION_ANALYSIS_SOURCE_MISMATCH')
        a=StyleLab(self.folder/'audio-research');asset=a.db.execute('SELECT * FROM assets WHERE id=?',(t['asset'],)).fetchone();a.db.close()
        result['sourceState']='SOURCE_MISSING' if not Path(asset['path']).is_file() else 'SOURCE_CHANGED' if digest(asset['path'])!=t['source_sha'] else 'AVAILABLE'
        result['structure'].pop('selfSimilarity',None)
        return result


def dispatch(root,method,p):
    expected={'experiment'} if method=='generationWorkspace' and 'experiment' in p else KEYS.get(method)
    if expected is None or set(p)!=expected:raise ValueError('IPC_REJECTED')
    lab=GenerationLab(root)
    try:
        if method=='generationWorkspace':return lab.workspace(p.get('experiment'))
        if method=='generationAnalysis':return lab.analysis(p['trial'])
        if method=='generationCreate':return lab.create(p['settings'])
        if method=='generationImport':return lab.imported(p['prompt'],p['metadata'],p['path'])
        if method=='generationFailure':return lab.failure(p['prompt'],p['reason'])
        if method=='generationReject':return lab.reject(p['trial'],p['reason'])
        if method=='generationRate':return lab.rate(p['trial'],p['ratings'])
        if method=='generationReveal':return lab.reveal(p['trial'])
        if method=='generationClip':return lab.clip(p['trial'],p['start'],p['end'])
        return lab.revise(p['prompt'],p['old'],p['new'],p['reason'],p['trials'])
    finally:lab.db.close()


def analysis_trials(g,selection):
    batch=selection=='pending' or selection.startswith('pending:')
    experiment=selection.split(':',1)[1] if selection.startswith('pending:') else g.workspace()['experiment']['id'] if batch else None
    prompt_ids={r['id'] for r in g.db.execute('SELECT id FROM prompts WHERE experiment=?',(experiment,))} if batch else None
    return [dict(t) for t in g.db.execute('SELECT * FROM trials WHERE asset IS NOT NULL ORDER BY created') if (t['prompt'] in prompt_ids if batch else t['id']==selection) and not g.latest(t['id'],'REJECTED') and (not batch or (g.latest(t['id'],'ANALYSIS') or {}).get('state')!='READY')]


def analyze(root,runtime,selection):
    from style_omar import VectorLab
    from style_structure import store_analysis,coverage
    from style_semantics import write_json
    import threading,os
    g=GenerationLab(root);folder=g.folder;cancel=folder/'cancel.request'
    trials=analysis_trials(g,selection)
    if not trials:raise ValueError('NO_GENERATION_AUDIO_TO_ANALYZE')
    try:
        audio=StyleLab(folder/'audio-research');audio.recover();vectors=VectorLab(audio,runtime);vectors.recover()
    except Exception as error:
        for trial in trials:g.event(trial['id'],'ANALYSIS',dict(state='FAILED',stage='CHECKING_COMPONENTS',error=str(error)))
        g.db.close();raise
    done=threading.Event()
    def watch_cancel():
        connection=sqlite3.connect(audio.root/'library.sqlite',timeout=10)
        try:
            while not done.wait(.1):
                if cancel.exists():
                    with connection:connection.execute("UPDATE jobs SET state='CANCEL_REQUESTED' WHERE state='PROCESSING'")
                    return
        finally:connection.close()
    thread=threading.Thread(target=watch_cancel,daemon=True);thread.start();started=time.perf_counter()
    try:
        for trial in trials:
            if cancel.exists():raise InterruptedError('CANCELLED')
            g.event(trial['id'],'ANALYSIS',dict(state='PROCESSING',stage='DSP',progress=0))
            job=audio.enqueue(trial['asset'])
            with audio.db:audio.db.execute("UPDATE jobs SET state='QUEUED',error=NULL WHERE id=? AND state IN ('FAILED','CANCELLED','INTERRUPTED')",(job,))
        audio.run(timeout=300)
        if cancel.exists():raise InterruptedError('CANCELLED')
        accepted=[]
        for trial in trials:
            job=audio.db.execute("SELECT * FROM jobs WHERE asset=? AND start=0 AND end IS NULL ORDER BY rowid DESC LIMIT 1",(trial['asset'],)).fetchone()
            if job['state']!='READY':g.event(trial['id'],'ANALYSIS',dict(state='FAILED',stage='DSP',error=job['error']));continue
            vectors.plan([trial['asset']]);accepted.append(trial)
            g.event(trial['id'],'ANALYSIS',dict(state='PROCESSING',stage='OMAR',progress=1/3))
        metrics=vectors.run(cancelled=cancel.exists)
        if cancel.exists():raise InterruptedError('CANCELLED')
        reference=VectorLab(StyleLab(root),runtime);reference_rows=reference.descriptors();target=np.stack([r['vector'] for r in reference_rows]) if reference_rows else None
        generated=vectors.descriptors();asset_names={a['id']:a['name'] for a in reference.lab.search()}
        for trial in accepted:
            if cancel.exists():raise InterruptedError('CANCELLED')
            g.event(trial['id'],'ANALYSIS',dict(state='PROCESSING',stage='STRUCTURE',progress=2/3))
            try:
                structure=store_analysis(vectors,trial['asset']);covered=coverage(vectors,trial['asset'])
                matches=[]
                for row in generated:
                    if row['asset']!=trial['asset'] or target is None:continue
                    scores=target@row['vector'];top=np.argsort(-scores,kind='stable')[:3]
                    matches.append(dict(start=row['start'],end=row['end'],candidates=[dict(asset=reference_rows[int(i)]['asset'],name=asset_names[reference_rows[int(i)]['asset']],start=reference_rows[int(i)]['start'],end=reference_rows[int(i)]['end'],cosine=float(scores[i]),meaning='AUXILIARY_VECTOR_COMPARISON_NOT_STYLE_ACCURACY') for i in top]))
                output=dict(trial=trial['id'],asset=trial['asset'],sourceSha256=trial['source_sha'],coverage=covered,structure=structure,referenceMatches=matches,semanticQualityJudgment=None,modelRevision=vectors.settings['revision'],vectorVersion=vectors.version,resources=metrics)
                write_json(folder/'comparisons'/(trial['id']+'.json'),output)
                g.event(trial['id'],'ANALYSIS',dict(state='READY',stage='COMPLETE',progress=1,duration=covered['duration'],coverage=covered['coverage'],sections=len(structure['sections']),lufs=structure['loudness']['value'],elapsedSeconds=time.perf_counter()-started,comparisonFile=trial['id']+'.json'))
            except Exception as error:g.event(trial['id'],'ANALYSIS',dict(state='FAILED',stage='STRUCTURE',error=str(error)))
        reference.lab.db.close()
    except BaseException as error:
        for trial in trials:
            if (g.latest(trial['id'],'ANALYSIS') or {}).get('state')!='READY':g.event(trial['id'],'ANALYSIS',dict(state='CANCELLED' if isinstance(error,InterruptedError) else 'FAILED',error=str(error)))
        if not isinstance(error,InterruptedError):raise
    finally:done.set();thread.join(timeout=2);audio.db.close();g.db.close()


if __name__=='__main__':
    import sys
    analyze(sys.argv[1],sys.argv[2],sys.argv[3])
