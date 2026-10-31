"""固定数据集检索对照；分数及排名不冒充带标签的音乐质量指标。"""
import json
import hashlib
import math
from pathlib import Path
import time
import numpy as np
from style_structure import coverage


def unit(x):
    return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-12)


def timelines(vectors):
    result={}
    for a in vectors.lab.search():
        report=coverage(vectors,a['id'])
        if not report['complete']:raise ValueError('INCOMPLETE_EXPERIMENT_SONG')
        pieces=[];times=[];contexts=[]
        rows=vectors.lab.db.execute("SELECT * FROM vectors WHERE asset=? AND version=? AND state='READY' ORDER BY start",(a['id'],vectors.version)).fetchall()
        for i,r in enumerate(rows):
            meta=json.loads(r['metadata']);t=np.asarray(meta['globalTimestamps'])
            end=rows[i+1]['start'] if i+1<len(rows) else report['duration']
            keep=(t>=r['start'])&(t<end)
            pieces.append(np.load(vectors.root/r['filename'],allow_pickle=False)[keep]);times.append(t[keep])
            contexts.append(dict(start=r['start'],end=r['end'],ownedEnd=end))
        result[a['id']]=dict(asset=a['id'],name=a['name'],duration=report['duration'],values=np.concatenate(pieces),times=np.concatenate(times),contexts=contexts)
    return result


def excerpts(data,seconds=5,hop=5):
    result=[]
    for a,d in data.items():
        for start in np.arange(0,d['duration']-seconds+1e-7,hop):
            block=d['values'][(d['times']>=start)&(d['times']<start+seconds)]
            if len(block)<seconds*25-1:raise ValueError('EXPERIMENT_FRAME_GAP')
            context=[(c['start'],c['end']) for c in d['contexts'] if c['start']<start+seconds and c['ownedEnd']>start]
            result.append(dict(id=f'{a}:{start:.3f}:{seconds}',asset=a,start=float(start),end=float(start+seconds),values=block,contexts=context))
    return result


def representation(rows,method):
    if method in ('raw_mean_cosine','l2_mean_cosine','centered_mean_cosine_experimental'):
        x=np.stack([r['values'].mean(axis=0,dtype=np.float64) for r in rows])
        if method=='centered_mean_cosine_experimental':x-=x.mean(axis=0)
        return unit(x)
    if method=='mean_frame_l2':return unit(np.stack([unit(r['values']).mean(axis=0) for r in rows]))
    if method=='median_l2':return unit(np.stack([np.median(r['values'],axis=0) for r in rows]))
    if method=='mean_std_l2':return unit(np.stack([np.concatenate([r['values'].mean(axis=0),r['values'].std(axis=0)]) for r in rows]))
    if method=='ordered_1s_sequence_cosine':
        # 同长度片段依次比较1秒子序列；不允许任意打乱帧后仍冒充相同序列。
        return np.stack([unit(np.stack([b.mean(axis=0) for b in np.array_split(r['values'],5)])) for r in rows])
    raise ValueError('UNKNOWN_METHOD')


def pair_scores(x):
    return np.einsum('itd,jtd->ij',x,x,optimize=True)/x.shape[1] if x.ndim==3 else x@x.T


def stats(values):
    x=np.asarray(values)
    return dict(n=len(x),min=float(x.min()),p05=float(np.quantile(x,.05)),median=float(np.median(x)),p95=float(np.quantile(x,.95)),max=float(x.max())) if len(x) else dict(n=0)


def allowed(a,b,scope='cross'):
    if a['id']==b['id']:return False
    if scope=='cross':return a['asset']!=b['asset']
    if any(x[0]<y[1] and y[0]<x[1] for x in a.get('contexts',[]) for y in b.get('contexts',[])):return False
    return a['asset']==b['asset'] and (a['end']+15<=b['start'] or b['end']+15<=a['start'])


def run_experiment(vectors,root):
    started=time.perf_counter();cpu=time.process_time();root=Path(root)
    plan=json.loads((root/'EXPERIMENT_PLAN.json').read_text(encoding='utf-8'))
    data=timelines(vectors);rows=excerpts(data);rng=np.random.default_rng(plan['seed'])
    queries=[next(i for i,r in enumerate(rows) if r['asset']==a and r['start']==math.floor(d['duration']/2/5)*5) for a,d in data.items()]
    pairs=[tuple(rng.choice(len(rows),2,replace=False)) for _ in range(3000)]
    pairs=[(i,j) for i,j in pairs if rows[i]['asset']!=rows[j]['asset']]+[(i,j) for i in range(len(rows)) for j in range(i+1,len(rows)) if rows[i]['asset']==rows[j]['asset']]
    structures={a:json.loads((vectors.lab.root/'structure'/(a+'.json')).read_text(encoding='utf-8')) for a in data}
    def section(a):
        return next((s['id'] for s in structures[a['asset']]['sections'] if s['start']<=a['start']<s['end']),None)
    methods={};scores={};rankings={};raw_values={}
    for method in plan['methods']:
        t=time.perf_counter();x=representation(rows,method);matrix=pair_scores(x);scores[method]=matrix
        groups={'adjacentDiagnostic':[],'sameSongSeparated':[],'sameSongDifferentSections':[],'crossSong':[]}
        for i,j in pairs:
            a,b=rows[i],rows[j]
            if a['asset']!=b['asset']:group='crossSong'
            elif allowed(a,b,'within'):group='sameSongDifferentSections' if section(a)!=section(b) else 'sameSongSeparated'
            else:group='adjacentDiagnostic'
            groups[group].append(float(matrix[i,j]))
        ranks=[]
        for q in queries:
            eligible=[i for i,r in enumerate(rows) if allowed(rows[q],r)]
            order=sorted(eligible,key=lambda i:(-float(matrix[q,i]),rows[i]['id']))
            ranks.append(order)
        rankings[method]=ranks
        methods[method]=dict(groups={k:stats(v) for k,v in groups.items()},seconds=time.perf_counter()-t,top5=[[dict(id=rows[i]['id'],asset=rows[i]['asset'],start=rows[i]['start'],end=rows[i]['end'],score=float(matrix[q,i])) for i in order[:5]] for q,order in zip(queries,ranks)])
        raw_values[method]=groups
    raw=scores['raw_mean_cosine'];difference=float(np.max(np.abs(raw-scores['l2_mean_cosine'])))
    stability={}
    for method in plan['methods']:
        jaccard=[];rho=[]
        for baseline,other in zip(rankings['raw_mean_cosine'],rankings[method]):
            one=set(baseline[:5]);two=set(other[:5]);jaccard.append(len(one&two)/len(one|two))
            pos={v:i for i,v in enumerate(other)};n=len(baseline)
            rho.append(1-6*sum((i-pos[v])**2 for i,v in enumerate(baseline))/(n*(n*n-1)))
        stability[method]=dict(top5JaccardMean=float(np.mean(jaccard)),spearmanMean=float(np.mean(rho)),labelBasedQuality=False)
    windows=[]
    for setting in plan['windows']:
        alt=excerpts(data,setting['seconds'],setting['hop']);x=representation(alt,'raw_mean_cosine');values=[];eligible_counts=[]
        for a,d in data.items():
            q=next(i for i,r in enumerate(alt) if r['asset']==a and r['start']>=d['duration']/2)
            permitted=[i for i,r in enumerate(alt) if allowed(alt[q],r)]
            values.extend((x[permitted]@x[q]).tolist());eligible_counts.append(len(permitted))
        top=[]
        for a,d in data.items():
            q=next(i for i,r in enumerate(alt) if r['asset']==a and r['start']>=d['duration']/2)
            order=sorted([i for i,r in enumerate(alt) if allowed(alt[q],r)],key=lambda i:(-float(x[i]@x[q]),alt[i]['id']))[:5]
            top.append(dict(query=alt[q]['id'],candidates=[dict(id=alt[i]['id'],score=float(x[i]@x[q])) for i in order]))
        windows.append(dict(**setting,segments=len(alt),crossQueryScores=stats(values),eligibleCandidates=eligible_counts,top5=top))
    whole=[]
    for a,d in data.items():
        pooled=unit(d['values'].mean(axis=0,dtype=np.float64));idx=[i for i,r in enumerate(rows) if r['asset']!=a]
        vals=representation(rows,'raw_mean_cosine')[idx]@pooled
        whole.append(dict(asset=a,localDistribution=stats(vals),warning='whole-mean baseline only, not a whole-song style definition'))
    audit=[]
    for a,s in structures.items():
        boundaries=s['sections'];duration=data[a]['duration'];issues=[]
        for i,seg in enumerate(boundaries):
            if seg['end']<=seg['start'] or i and abs(seg['start']-boundaries[i-1]['end'])>1e-6:issues.append('GAP_OR_ORDER')
        if boundaries[0]['start']!=0 or abs(boundaries[-1]['end']-duration)>1e-6:issues.append('ENDPOINT')
        audit.append(dict(asset=a,sections=len(boundaries),technicalIssues=issues,boundaries=[dict(start=b['start'],end=b['end'],novelty=b['novelty'],rms=b['rmsMean'],repeatCandidates=b['repeats'],musicalValidity='PENDING_HUMAN') for b in boundaries],humanLabels=0))
    # 先冻结16组待审，禁止借后续人工分数重挑“效果好”的展示对。
    selected=[];seen=set()
    for category in ('cross_top','within_different_section','random_cross','cross_low'):
        for q in queries:
            if sum(p['category']==category for p in selected)>=4:break
            eligible=[i for i,r in enumerate(rows) if allowed(rows[q],r,'within' if category=='within_different_section' else 'cross')]
            if category=='within_different_section':eligible=[i for i in eligible if section(rows[q])!=section(rows[i])]
            order=sorted(eligible,key=lambda i:(-raw[q,i],rows[i]['id']))
            if category=='random_cross':order=list(rng.permutation(order))
            if category=='cross_low':order=order[::-1]
            target=next((i for i in order if tuple(sorted([rows[q]['id'],rows[i]['id']])) not in seen),None)
            if target is None:continue
            seen.add(tuple(sorted([rows[q]['id'],rows[target]['id']])))
            def clip(r):return dict(asset=r['asset'],name=data[r['asset']]['name'],start=r['start'],end=r['end'],id=r['id'])
            pair=dict(id=f'pair-{len(selected)+1:02}',category=category,a=clip(rows[q]),b=clip(rows[target]),score=float(raw[q,target]),status='PENDING',ratings=None)
            if rng.integers(2):pair['a'],pair['b']=pair['b'],pair['a']
            selected.append(pair)
    rng.shuffle(selected)
    gaps={method:[float(scores[method][q,order[0]]-scores[method][q,order[4]]) for q,order in zip(queries,rankings[method])] for method in plan['methods']}
    result=dict(methods=methods,stability=stability,top1MinusTop5=gaps,queries=[{k:rows[q][k] for k in ('id','asset','start','end')} for q in queries],l2CosineMaximumDifference=difference,windows=windows,wholeVsLocal=whole,queryCount=len(queries),candidateCount=len(rows),structureAudit=audit,precisionAtK=None,recallAtK=None,humanLabelCount=0,elapsedSeconds=time.perf_counter()-started,cpuSeconds=time.process_time()-cpu,status='COMPUTATION_COMPLETE_EFFECTIVENESS_UNPROVEN')
    (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'raw-score-distributions.json').write_text(json.dumps(raw_values),encoding='utf-8')
    (root/'audition-pairs.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def audition(lab,method,params):
    manifest=(lab.root/'phase4/audition-pairs.json').read_bytes()
    pairs=json.loads(manifest.decode('utf-8'));study=hashlib.sha256(manifest).hexdigest()
    lab.db.execute('CREATE TABLE IF NOT EXISTS audition_events(id INTEGER PRIMARY KEY,study TEXT,pair TEXT,kind TEXT,body TEXT,created REAL)')
    if method=='auditionList':
        rated={}
        for r in lab.db.execute("SELECT pair,body FROM audition_events WHERE study=? AND kind='RATING' ORDER BY id DESC",(study,)):
            if r['pair'] not in rated:rated[r['pair']]=json.loads(r['body'])['ratings']
        return [dict(id=p['id'],status='RATED' if p['id'] in rated else 'PENDING',ratings=rated.get(p['id']),durationA=p['a']['end']-p['a']['start'],durationB=p['b']['end']-p['b']['start']) for p in pairs]
    pair=next(p for p in pairs if p['id']==params['pair'])
    if method=='auditionReveal':
        with lab.db:lab.db.execute('INSERT INTO audition_events(study,pair,kind,body,created) VALUES(?,?,?,?,?)',(study,pair['id'],'REVEAL','{}',time.time()))
        return pair
    if method=='auditionClip':
        if params['side'] not in ('a','b'):raise ValueError('INVALID_SIDE')
        return pair[params['side']]
    if method!='auditionRate':raise ValueError('IPC_REJECTED')
    fields={'overall','rhythm','timbre','harmony','arrangement','reference'}
    ratings=params['ratings']
    if set(ratings)!=fields or any(v not in ('similar','different','unknown') for v in ratings.values()):raise ValueError('INVALID_AUDITION_RATING')
    revealed=lab.db.execute("SELECT 1 FROM audition_events WHERE study=? AND pair=? AND kind='REVEAL' LIMIT 1",(study,pair['id'])).fetchone() is not None
    with lab.db:lab.db.execute('INSERT INTO audition_events(study,pair,kind,body,created) VALUES(?,?,?,?,?)',(study,pair['id'],'RATING',json.dumps(dict(ratings=ratings,revealedBeforeRating=revealed)),time.time()))
    return True
