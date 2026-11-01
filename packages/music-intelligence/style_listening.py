"""保留模型锚点，独立管理有上下文的个人听审。"""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from style_lab import digest

SIMILARITY=('overall','rhythm','drumsBass','melodyHarmony','timbre','arrangement')
NUMERIC=SIMILARITY+('enjoymentA','enjoymentB','referenceA','referenceB')


def context(anchor,duration,seconds):
    width=min(seconds,duration)
    start=max(0,min((anchor['start']+anchor['end'])/2-width/2,duration-width))
    return dict(asset=anchor['asset'],start=start,end=start+width)


def prepare(vectors):
    from style_quality import timelines,excerpts,representation,allowed
    lab=vectors.lab;target=lab.root/'phase5/study.json'
    if target.exists():raise FileExistsError('STUDY_ALREADY_EXISTS')
    old=(lab.root/'phase4/audition-pairs.json').read_bytes();previous=json.loads(old)
    selected=[]
    for category,count in [('cross_top',4),('cross_low',3),('random_cross',3),('within_different_section',3)]:
        selected.extend([p for p in previous if p['category']==category][:count])
    data=timelines(vectors);rows=excerpts(data);x=representation(rows,'raw_mean_cosine')
    queries=json.loads((lab.root/'phase4/results.json').read_text(encoding='utf-8'))['queries']
    seen={tuple(sorted((p['a']['id'],p['b']['id']))) for p in selected}
    for q in queries:
        qi=next(i for i,r in enumerate(rows) if r['id']==q['id']);scores=x@x[qi]
        ranked=sorted([i for i,r in enumerate(rows) if allowed(rows[qi],r)],key=lambda i:(scores[i],rows[i]['id']))
        middle=len(ranked)//2
        candidates=sorted(ranked,key=lambda i:abs(ranked.index(i)-middle))
        j=next(i for i in candidates if tuple(sorted((rows[qi]['id'],rows[i]['id']))) not in seen)
        def anchor(r):return {k:r[k] for k in ('asset','start','end','id')}
        pair=dict(id='medium-'+str(len(selected)),category='cross_middle',a=anchor(rows[qi]),b=anchor(rows[j]),score=float(scores[j]))
        selected.append(pair);seen.add(tuple(sorted((pair['a']['id'],pair['b']['id']))))
        if len(selected)==16:break
    if len(selected)!=16:raise ValueError('STUDY_REQUIRES_16_PAIRS')
    assets={a['id']:a for a in lab.search()};sources={};checks=[]
    for identity,a in assets.items():
        if digest(a['path'])!=a['sha']:raise ValueError('SOURCE_CHANGED')
        info=sf.info(a['path']);sources[identity]=dict(name=a['name'],sha256=a['sha'],duration=info.duration,sampleRate=info.samplerate)
    rng=np.random.default_rng(20261101);rng.shuffle(selected)
    for n,p in enumerate(selected):
        p['previousPairId']=p['id'];p['id']=f'listening-{n+1:02}';p.pop('ratings',None);p.pop('status',None)
        if rng.integers(2):p['a'],p['b']=p['b'],p['a']
        for side in ('a','b'):
            a=p[side];source=sources[a['asset']]
            if not 0<=a['start']<a['end']<=source['duration']:raise ValueError('ANCHOR_OUT_OF_RANGE')
            a['name']=source['name'];a['sourceSha256']=source['sha256'];a['duration']=source['duration'];a['context']=context(a,a['duration'],20)
            checks.append(dict(pair=p['id'],side=side,source=a['asset'],sourceSha256=source['sha256'],anchorStart=a['start'],anchorEnd=a['end'],**{f'play{k.title()}':v for k,v in a['context'].items() if k!='asset'},seconds=a['context']['end']-a['context']['start'],status='SOURCE_AND_RANGE_VERIFIED'))
    study=dict(schemaVersion=2,id='style-lab-personal-listening-v1',previousStudySha256=hashlib.sha256(old).hexdigest(),vectorVersion=vectors.version,modelRevision=vectors.settings['revision'],scoreScope='original5secondAnchors',defaultSeconds=20,pairs=selected)
    target.parent.mkdir(exist_ok=True)
    with target.open('x',encoding='utf-8') as stream:json.dump(study,stream,ensure_ascii=False,indent=2)
    (target.parent/'material-checks.json').write_text(json.dumps(dict(sources=sources,clips=checks,counts={c:sum(p['category']==c for p in selected) for c in {p['category'] for p in selected}},humanRatings=0),ensure_ascii=False,indent=2),encoding='utf-8')
    return study


def load(lab):
    raw=(lab.root/'phase5/study.json').read_bytes();study=json.loads(raw)
    if study['schemaVersion']!=2:raise ValueError('STUDY_SCHEMA_MISMATCH')
    key=hashlib.sha256(raw).hexdigest()
    lab.db.execute('CREATE TABLE IF NOT EXISTS listening_events(id INTEGER PRIMARY KEY,study TEXT,pair TEXT,kind TEXT,body TEXT,created REAL)')
    return study,key


def latest(lab,key):
    result={}
    for r in lab.db.execute("SELECT id,pair,body FROM listening_events WHERE study=? AND kind='RATING' ORDER BY id DESC",(key,)):
        if r['pair'] not in result:result[r['pair']]=dict(json.loads(r['body']),eventId=r['id'])
    return result


def event(lab,key,pair,kind,body):
    with lab.db:lab.db.execute('INSERT INTO listening_events(study,pair,kind,body,created) VALUES(?,?,?,?,?)',(key,pair,kind,json.dumps(body,ensure_ascii=False),time.time()))


def validate_rating(rating):
    if not isinstance(rating,dict) or set(rating)!=set(NUMERIC)|{'preference','notes','reviewed'}:raise ValueError('INVALID_LISTENING_RATING')
    if any(v is not None and (type(v)!=int or not 1<=v<=5) for v in (rating[k] for k in NUMERIC)):raise ValueError('INVALID_LISTENING_SCORE')
    if rating['preference'] not in ('a','b','both','neither','unknown') or rating['reviewed'] is not True:raise ValueError('REVIEW_CONFIRMATION_REQUIRED')
    if not isinstance(rating['notes'],str) or len(rating['notes'])>2000:raise ValueError('INVALID_REVIEW_NOTE')


def qualifications(lab,study,key,ratings):
    dispositions={r['pair']:json.loads(r['body']) for r in lab.db.execute("SELECT pair,body FROM listening_events WHERE study=? AND kind='DISPOSITION' ORDER BY id",(key,))}
    result={};seen={}
    for p in study['pairs']:
        r=ratings.get(p['id'])
        if not r:continue
        status=dispositions.get(p['id'],{}).get('status','VALID')
        ranges=r.get('primaryRanges',{}) if r.get('schemaVersion',0)>=3 else r.get('previewRequests',{})
        comparable=all(s in ranges and all(ranges[s].get(k)==p[s][k] for k in ('asset','start','end')) for s in ('a','b'))
        signature=tuple(sorted((v.get('asset'),v.get('start'),v.get('end')) for v in ranges.values())) if len(ranges)==2 else None
        duplicate=seen.get(signature) if signature else None
        if signature and status=='VALID':seen.setdefault(signature,p['id'])
        identical=bool(signature and signature[0]==signature[1])
        reason='EXCLUDED_BY_REVIEW' if status!='VALID' else 'IDENTICAL_PLAYBACK' if identical else 'DUPLICATE_RANGE_PAIR' if duplicate else 'RANGE_MISMATCH' if not comparable else 'SOURCE_REVEALED' if r['revealedBeforeRating'] else None
        result[p['id']]=dict(status=status,ratingEventId=r['eventId'],ratingRanges=ranges,featureRanges={s:{k:p[s][k] for k in ('asset','start','end')} for s in ('a','b')},scopeComparable=comparable,retrievalEligible=reason is None,exclusionReason=reason,duplicateOf=duplicate,disposition=dispositions.get(p['id']))
    return result


def audition(lab,method,params):
    study,key=load(lab);ratings=latest(lab,key)
    if method=='auditionList':
        q=qualifications(lab,study,key,ratings)
        return [dict(schemaVersion=2,id=p['id'],status='RATED' if p['id'] in ratings else 'PENDING',durationA=p['a']['context']['end']-p['a']['context']['start'],durationB=p['b']['context']['end']-p['b']['context']['start'],ratings=ratings.get(p['id'],{}).get('ratings'),qualification=q.get(p['id'])) for p in study['pairs']]
    if method=='auditionSummary':return summary(lab,study,key,ratings)
    if method=='auditionLeaveBlind':
        event(lab,key,'*','RESEARCH_EXPOSURE',{})
        return True
    pair=next((p for p in study['pairs'] if p['id']==params['pair']),None)
    if pair is None:raise ValueError('UNKNOWN_LISTENING_PAIR')
    if method=='auditionDisposition':
        if pair['id'] not in ratings or params['status'] not in ('VALID','INVALID','SKIPPED') or not isinstance(params['reason'],str) or not 1<=len(params['reason'])<=2000:raise ValueError('INVALID_DISPOSITION')
        event(lab,key,pair['id'],'DISPOSITION',dict(status=params['status'],reason=params['reason'],source='USER_REVIEW',ratingEventId=ratings[pair['id']]['eventId']))
        return True
    if method=='auditionReveal':
        if pair['id'] not in ratings:raise ValueError('RATE_BEFORE_REVEAL')
        event(lab,key,pair['id'],'REVEAL',{})
        result=dict(pair)
        for side in ('a','b'):result[side]=dict(pair[side],auditionRange=ratings[pair['id']].get('previewRequests',{}).get(side,pair[side]['context']))
        return result
    if method=='auditionClip':
        if params['side'] not in ('a','b'):raise ValueError('INVALID_SIDE')
        anchor=pair[params['side']];mode=params.get('mode','context')
        if mode not in ('anchor','context','extended','whole'):raise ValueError('INVALID_LISTENING_MODE')
        row={k:anchor[k] for k in ('asset','start','end')} if mode=='anchor' else dict(anchor['context']) if mode=='context' else context(anchor,anchor['duration'],40) if mode=='extended' else dict(asset=anchor['asset'],start=0,end=anchor['duration'])
        a=lab.db.execute('SELECT * FROM assets WHERE id=?',(row['asset'],)).fetchone()
        if not a or digest(a['path'])!=anchor['sourceSha256']:raise ValueError('STUDY_SOURCE_CHANGED')
        event(lab,key,pair['id'],'PREVIEW_REQUEST',dict(side=params['side'],mode=mode,purpose='SUPPLEMENTAL_SONG' if mode=='whole' else 'RATING_PRIMARY',**row))
        return row
    if method!='auditionRate':raise ValueError('IPC_REJECTED')
    if pair['id'] in ratings:raise ValueError('EXISTING_REVIEW_PRESERVED')
    validate_rating(params['ratings'])
    revealed=lab.db.execute("SELECT 1 FROM listening_events WHERE study=? AND ((pair=? AND kind='REVEAL') OR kind='RESEARCH_EXPOSURE') LIMIT 1",(key,pair['id'])).fetchone() is not None
    requests={};primary={}
    for r in lab.db.execute("SELECT body FROM listening_events WHERE study=? AND pair=? AND kind='PREVIEW_REQUEST' ORDER BY id DESC",(key,pair['id'])):
        body=json.loads(r['body'])
        if body['side'] not in requests:requests[body['side']]=body
        if body.get('purpose')=='RATING_PRIMARY' and body['side'] not in primary:primary[body['side']]=body
    if len(primary)!=2:raise ValueError('LISTEN_TO_BOTH_PRIMARY_EXCERPTS')
    event(lab,key,pair['id'],'RATING',dict(schemaVersion=3,ratings=params['ratings'],revealedBeforeRating=revealed,modelScore=pair['score'],scoreScope=study['scoreScope'],previewRequests=requests,primaryRanges=primary))
    return True


def rank(values):
    values=np.asarray(values);order=np.argsort(values,kind='stable');result=np.empty(len(values),dtype=float)
    for v in np.unique(values):
        positions=np.flatnonzero(values[order]==v);result[order[positions]]=positions.mean()
    return result


def summary(lab,study,key,ratings):
    associations={};references=[];favorites=[];notes=[]
    eligibility=qualifications(lab,study,key,ratings)
    for field in SIMILARITY:
        pairs=[(p['score'],ratings[p['id']]['ratings'][field]) for p in study['pairs'] if eligibility.get(p['id'],{}).get('retrievalEligible') and ratings[p['id']]['ratings'][field] is not None]
        rho=None
        if len(pairs)>=3:
            x=rank([p[0] for p in pairs]);y=rank([p[1] for p in pairs])
            if x.std()>0 and y.std()>0:rho=float(np.corrcoef(x,y)[0,1])
        associations[field]=dict(n=len(pairs),spearman=rho,status='DESCRIPTIVE_ONLY' if rho is not None else 'INSUFFICIENT_LABELS')
    for p in study['pairs']:
        if p['id'] not in ratings:continue
        r=ratings[p['id']]['ratings']
        if r['notes'].strip():notes.append(dict(pair=p['id'],text=r['notes'],source='USER_AUTHORED'))
        if eligibility[p['id']]['status']!='VALID':continue
        for side in ('a','b'):
            suffix=side.upper();enjoy=r['enjoyment'+suffix];ref=r['reference'+suffix]
            a=p[side];requested=ratings[p['id']].get('primaryRanges',ratings[p['id']].get('previewRequests',{})).get(side)
            region={k:requested[k] for k in ('asset','start','end')} if requested else a['context']
            entry=dict(pair=p['id'],side=side,asset=a['asset'],range=region,rangeSource='PREVIEW_REQUEST' if requested else 'DEFAULT_CONTEXT',ratingEventId=ratings[p['id']]['eventId'],sourceSha256=a['sourceSha256'],enjoyment=enjoy,reference=ref)
            if ref is not None and ref>=4:references.append(dict(entry,source='USER_RATED_REFERENCE'))
            if enjoy is not None and enjoy>=4:favorites.append(dict(entry,source='USER_LIKED_EXCERPT'))
    event_ids=sorted(r['eventId'] for r in ratings.values())
    disposition_ids=[r[0] for r in lab.db.execute("SELECT id FROM listening_events WHERE study=? AND kind='DISPOSITION' ORDER BY id",(key,))]
    version=hashlib.sha256((key+json.dumps([event_ids,disposition_ids])).encode()).hexdigest()[:16]
    return dict(schemaVersion=1,profileId='personal-'+version,study=key,sourceRatingEvents=event_ids,status='WAITING_FOR_RATINGS' if not ratings else 'PROVISIONAL_PERSONAL_PROFILE',ratedPairs=len(ratings),totalPairs=len(study['pairs']),references=references,favorites=favorites,userDescriptions=notes,associations=associations,qualifications=eligibility,wholeSongPreferences=None,characteristics={k:None for k in ('rhythm','drumsBass','timbre','melodyHarmony','arrangement')},unansweredReason='NO_VALIDATED_DESCRIPTOR_OR_WHOLE_SONG_RATINGS',modelTrained=False)
