import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_lab import StyleLab,digest
from style_listening import audition,context,NUMERIC


class ListeningTests(unittest.TestCase):
    def setup_study(self,folder):
        lab=StyleLab(folder);p=lab.root/'owned.wav';sf.write(p,np.zeros(8000*60),8000)
        asset=lab.import_audio([p])[0];anchor=dict(asset=asset,name='TEST_FIXTURE',start=25,end=30,duration=60,sourceSha256=digest(p))
        anchor['context']=context(anchor,60,20)
        study=dict(schemaVersion=2,pairs=[dict(id=f'p-{i}',a=anchor,b=anchor,score=.5+i*.1) for i in range(3)],scoreScope='original5secondAnchors')
        target=lab.root/'phase5';target.mkdir();file=target/'study.json';file.write_text(json.dumps(study),encoding='utf-8')
        return lab,file

    def test_blinding_rating_recovery_and_immutable_study(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,file=self.setup_study(folder);original=file.read_bytes()
            row=audition(lab,'auditionList',{})[0]
            self.assertEqual(set(row),{'schemaVersion','id','status','durationA','durationB','ratings'});self.assertEqual(row['durationA'],20)
            with self.assertRaisesRegex(ValueError,'RATE_BEFORE_REVEAL'):audition(lab,'auditionReveal',dict(pair='p-0'))
            rating=dict.fromkeys(NUMERIC,None);rating.update(preference='unknown',notes='',reviewed=True)
            rating.update(overall=1,enjoymentA=5,enjoymentB=5,referenceA=5,preference='both')
            audition(lab,'auditionRate',dict(pair='p-0',ratings=rating));lab.db.close()
            lab=StyleLab(folder)
            self.assertEqual(audition(lab,'auditionList',{})[0]['ratings'],rating)
            self.assertEqual(audition(lab,'auditionReveal',dict(pair='p-0'))['score'],.5)
            audition(lab,'auditionRate',dict(pair='p-0',ratings=rating))
            result=audition(lab,'auditionSummary',{})
            self.assertEqual(result['ratedPairs'],1);self.assertEqual(len(result['references']),1)
            self.assertEqual(result['associations']['overall']['n'],0)
            self.assertIsNone(result['characteristics']['timbre']);self.assertIsNone(result['wholeSongPreferences'])
            self.assertEqual(file.read_bytes(),original);lab.db.close()

    def test_invalid_scores_and_preview_source(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,file=self.setup_study(folder)
            r=dict.fromkeys(NUMERIC,None);r.update(preference='unknown',notes='',reviewed=True)
            for bad in (True,0,6,'5',float('nan')):
                with self.assertRaises(ValueError):audition(lab,'auditionRate',dict(pair='p-0',ratings=dict(r,overall=bad)))
            with self.assertRaises(ValueError):audition(lab,'auditionRate',dict(pair='p-0',ratings=dict(r,reviewed=False)))
            for mode,seconds in [('context',20),('extended',40),('whole',60)]:
                clip=audition(lab,'auditionClip',dict(pair='p-0',side='a',mode=mode));self.assertEqual(clip['end']-clip['start'],seconds)
            with self.assertRaises(ValueError):audition(lab,'auditionClip',dict(pair='p-0',side='a',mode='../private'))
            (lab.root/'owned.wav').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'STUDY_SOURCE_CHANGED'):audition(lab,'auditionClip',dict(pair='p-0',side='a'))
            lab.db.close()

    def test_label_association_is_descriptive_and_not_preference(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,file=self.setup_study(folder)
            self.assertEqual(audition(lab,'auditionSummary',{})['status'],'WAITING_FOR_RATINGS')
            for i in range(3):
                r=dict.fromkeys(NUMERIC,None);r.update(overall=i+1,enjoymentA=5,enjoymentB=5,preference='both',notes='TEST_FIXTURE',reviewed=True)
                audition(lab,'auditionRate',dict(pair=f'p-{i}',ratings=r))
            result=audition(lab,'auditionSummary',{})
            self.assertAlmostEqual(result['associations']['overall']['spearman'],1);self.assertFalse(result['modelTrained'])
            self.assertEqual(result['references'],[]);lab.db.close()

    def test_leaving_blind_research_excludes_later_ratings(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,file=self.setup_study(folder)
            audition(lab,'auditionLeaveBlind',{})
            r=dict.fromkeys(NUMERIC,None);r.update(overall=5,preference='a',notes='',reviewed=True)
            audition(lab,'auditionRate',dict(pair='p-0',ratings=r))
            self.assertEqual(audition(lab,'auditionSummary',{})['associations']['overall']['n'],0)
            lab.db.close()

    def test_reference_value_does_not_require_liking(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,file=self.setup_study(folder)
            r=dict.fromkeys(NUMERIC,None);r.update(overall=1,enjoymentA=1,referenceA=5,enjoymentB=5,referenceB=1,preference='b',notes='',reviewed=True)
            audition(lab,'auditionRate',dict(pair='p-0',ratings=r));result=audition(lab,'auditionSummary',{})
            self.assertEqual([r['side'] for r in result['references']],['a'])
            self.assertEqual([r['side'] for r in result['favorites']],['b']);lab.db.close()
