import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_lab import StyleLab
from style_quality import allowed,representation,pair_scores,audition


class QualityTests(unittest.TestCase):
    def test_cosine_invariant_and_temporal_order(self):
        a=np.vstack([np.tile([1.,0.],(25,1)),np.tile([0.,1.],(100,1))])
        rows=[dict(values=a),dict(values=a[::-1])]
        np.testing.assert_allclose(pair_scores(representation(rows,'raw_mean_cosine')),pair_scores(representation(rows,'l2_mean_cosine')))
        self.assertAlmostEqual(pair_scores(representation(rows,'raw_mean_cosine'))[0,1],1)
        self.assertLess(pair_scores(representation(rows,'ordered_1s_sequence_cosine'))[0,1],.7)

    def test_leakage_exclusion(self):
        a=dict(id='a',asset='one',start=0,end=5)
        for start in (0,2,5,19.99):
            self.assertFalse(allowed(a,dict(id='b',asset='one',start=start,end=start+5),'within'))
        self.assertTrue(allowed(a,dict(id='b',asset='one',start=20,end=25),'within'))
        self.assertFalse(allowed(a,dict(id='b',asset='one',start=20,end=25)))
        self.assertFalse(allowed(dict(a,contexts=[(0,30)]),dict(id='b',asset='one',start=25,end=30,contexts=[(25,55)]),'within'))

    def test_blind_records_append_and_validate(self):
        with tempfile.TemporaryDirectory() as folder:
            lab=StyleLab(folder);root=lab.root/'phase4';root.mkdir()
            p=dict(id='pair-01',score=.96,category='cross_top',a=dict(name='privateA',start=0,end=5),b=dict(name='privateB',start=10,end=15))
            file=root/'audition-pairs.json';file.write_text(json.dumps([p]),encoding='utf-8');original=file.read_bytes()
            self.assertEqual(audition(lab,'auditionList',{}),[dict(id='pair-01',status='PENDING',ratings=None,durationA=5,durationB=5)])
            rating=dict.fromkeys(('overall','rhythm','timbre','harmony','arrangement','reference'),'unknown')
            with self.assertRaises(ValueError):audition(lab,'auditionRate',dict(pair=p['id'],ratings={'overall':'similar'}))
            for _ in range(2):audition(lab,'auditionRate',dict(pair=p['id'],ratings=rating))
            self.assertEqual(lab.db.execute('SELECT count(*) FROM audition_events').fetchone()[0],2)
            self.assertEqual(audition(lab,'auditionList',{})[0]['status'],'RATED')
            self.assertEqual(audition(lab,'auditionList',{})[0]['ratings'],rating)
            audition(lab,'auditionReveal',dict(pair=p['id']))
            audition(lab,'auditionRate',dict(pair=p['id'],ratings=rating))
            last=json.loads(lab.db.execute('SELECT body FROM audition_events ORDER BY id DESC').fetchone()[0])
            self.assertTrue(last['revealedBeforeRating'])
            self.assertEqual(file.read_bytes(),original)
            with self.assertRaises(ValueError):audition(lab,'execute',dict(pair=p['id']))
            with self.assertRaises(ValueError):audition(lab,'auditionClip',dict(pair=p['id'],side='../private'))
            lab.db.close()
