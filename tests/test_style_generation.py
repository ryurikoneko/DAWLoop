import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_lab import StyleLab,digest
from style_generation import GenerationLab,DEFAULTS,SCORES,MEASURED,analysis_trials


class GenerationTests(unittest.TestCase):
    def fixture(self,folder):
        root=Path(folder);lab=StyleLab(root);reference=root/'reference.wav';sf.write(reference,np.sin(np.arange(8000)*.1)*.1,8000);a=lab.import_audio([reference])[0];lab.db.close()
        (root/'structure').mkdir();(root/'structure'/(a+'.json')).write_text(json.dumps(dict(asset=a,sourceSha256=digest(reference),coverage=dict(duration=1),dspJob='TEST_FIXTURE',vectorVersion='TEST_FIXTURE',curves=dict(energy=[[0,.01],[.5,.2]]))),encoding='utf-8')
        (root/'phase6').mkdir();(root/'phase6/personal-profile.json').write_text(json.dumps(dict(sourceRatingEvents=[7],claims=[dict(source='TEST_FIXTURE')])),encoding='utf-8')
        audio=root/'owned-generated-test.wav';sf.write(audio,np.sin(np.arange(16000)*.2)*.1,8000)
        g=GenerationLab(root);settings=dict(DEFAULTS,modelVersion='TEST_FIXTURE');g.create(settings);w=g.workspace()
        meta=dict(generatedAt='2026-10-31T00:00:00Z',modelVersion='TEST_FIXTURE',platform='Suno',batchId=None,seed=None,settings=settings,sourceNote='TEST_FIXTURE_NOT_SUNO_GENERATION')
        return g,w,meta,audio,reference

    def test_prompt_control_audit_and_append_only_revisions(self):
        with tempfile.TemporaryDirectory() as folder:
            g,w,m,a,_=self.fixture(folder);p={p['group_name']:p for p in w['prompts']}
            self.assertTrue(p['B']['body'].startswith(p['A']['body']));self.assertTrue(p['C']['body'].startswith(p['B']['body']));self.assertNotIn('CLAP',p['B']['body']);self.assertNotIn('nimble',p['A']['body'])
            t=g.imported(p['C']['id'],m,a);r=dict.fromkeys(SCORES,None);r.update(melody=1,liking=5,productionQuality=2,targetCloseness=3,wouldKeep='yes',notes='TEST_FIXTURE',reviewed=True)
            with self.assertRaisesRegex(ValueError,'LISTEN_BEFORE'):g.rate(t,r)
            with self.assertRaisesRegex(ValueError,'RATE_BEFORE'):g.reveal(t)
            g.clip(t,0,2);g.rate(t,r);version=g.revise(p['C']['id'],'Japanese electronic pop','Melody-led Japanese pop','TEST_FIXTURE single change',[t])
            self.assertEqual(g.prompt(p['C']['id'])['body'],p['C']['body']);self.assertEqual(g.prompt(version)['version'],2);self.assertEqual(g.prompt(version)['parent'],p['C']['id'])
            self.assertEqual(g.workspace()['summary'][2]['metrics']['liking']['mean'],5);self.assertIsNone(g.workspace()['summary'][2]['metrics']['groove']['mean'])
            self.assertTrue(g.workspace()['suggestions']);self.assertEqual(g.reveal(t)['group'],'C');g.db.close()
            g=GenerationLab(folder);self.assertEqual(g.workspace()['blind'][0]['ratings']['liking'],5);g.db.close()

    def test_duplicate_reference_mismatch_failure_and_no_zero_fill(self):
        with tempfile.TemporaryDirectory() as folder:
            g,w,m,a,reference=self.fixture(folder);p=w['prompts'][0]['id']
            with self.assertRaisesRegex(ValueError,'REFERENCE_AUDIO'):g.imported(p,m,reference)
            t=g.imported(p,dict(m,modelVersion='OTHER'),a)
            with self.assertRaisesRegex(ValueError,'ALREADY_IMPORTED'):g.imported(p,m,a)
            g.clip(t,0,2);r=dict.fromkeys(SCORES,None);r.update(liking=5,productionQuality=1,targetCloseness=2,wouldKeep='unknown',notes='',reviewed=True);g.rate(t,r)
            self.assertEqual(g.workspace()['summary'][0]['metrics']['liking']['n'],0)
            failed=g.failure(p,'TEST_FIXTURE generation failure');self.assertIsNone(g.trial(failed)['asset']);g.reject(t,'TEST_FIXTURE off task')
            row=g.workspace()['summary'][0];self.assertEqual((row['failed'],row['rejected']),(1,1));g.db.close()

    def test_blind_contract_missing_source_and_invalid_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            g,w,m,a,_=self.fixture(folder);t=g.imported(w['prompts'][0]['id'],m,a)
            blind=g.workspace()['blind'][0];self.assertEqual(set(blind),{'id','alias','duration','ratings'})
            g.clip(t,0,1);r=dict.fromkeys(SCORES,None);r.update(wouldKeep='no',notes='',reviewed=True)
            for bad in (0,6,True,'5',float('nan')):
                with self.assertRaises(ValueError):g.rate(t,dict(r,liking=bad))
            g.rate(t,r);a.unlink();self.assertEqual(g.workspace()['trials'][0]['state'],'SOURCE_MISSING');self.assertEqual(g.workspace()['blind'],[]);self.assertIsNotNone(g.latest(t,'RATING'));g.db.close()

    def test_batch_is_bound_to_experiment_and_versions_are_not_pooled(self):
        with tempfile.TemporaryDirectory() as folder:
            g,w,m,a,_=self.fixture(folder);old=w['experiment']['id'];t=g.imported(w['prompts'][2]['id'],m,a)
            new=g.create(dict(DEFAULTS,modelVersion='SECOND_TEST_FIXTURE'))
            self.assertEqual(analysis_trials(g,'pending:'+new),[]);self.assertEqual([r['id'] for r in analysis_trials(g,'pending:'+old)],[t])
            self.assertEqual(g.workspace(old)['experiment']['id'],old)
            g.clip(t,0,2);r=dict.fromkeys(SCORES,None);r.update(liking=5,wouldKeep='yes',notes='TEST_FIXTURE',reviewed=True);g.rate(t,r)
            g.revise(w['prompts'][2]['id'],'Japanese electronic pop','Melody-led electronic pop','TEST_FIXTURE',[t])
            rows=[x for x in g.workspace(old)['summary'] if x['group']=='C'];self.assertEqual([(x['version'],x['metrics']['liking']['n']) for x in rows],[(1,1),(2,0)]);g.db.close()
