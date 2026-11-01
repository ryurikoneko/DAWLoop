import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_semantics import plan,aggregate,GROUPS,write_json
import test_style_listening
from style_listening import audition,NUMERIC,load,event,summary,latest


class SemanticTests(unittest.TestCase):
    def test_exact_coverage_and_section_cache_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,_=test_style_listening.ListeningTests().setup_study(folder);asset=lab.search()[0]
            structure=dict(sourceSha256=asset['sha'],sections=[dict(id=0,start=0,end=21.3),dict(id=1,start=21.3,end=60)])
            write_json(lab.root/'structure'/(asset['id']+'.json'),structure)
            rows=plan(lab,'fixed-revision');self.assertEqual(rows[0]['start'],0);self.assertEqual(rows[-1]['end'],60)
            self.assertTrue(all(a['end']==b['start'] for a,b in zip(rows,rows[1:])));self.assertTrue(all(r['end']-r['start']<=10 for r in rows))
            self.assertNotEqual(rows[0]['id'],plan(lab,'other-revision')[0]['id']);lab.db.close()

    def test_candidate_ambiguity_not_fact_or_probability(self):
        structure=dict(asset='test',sourceSha256='test',coverage=dict(duration=10),sections=[dict(id=0,start=0,end=10)])
        groups={g:[dict(id=i,cosine=.2) for i,_,_ in values] for g,values in GROUPS.items()}
        result=aggregate(structure,[dict(id='window',section=0,start=0,end=10,groups=groups)],'revision')
        section=result['sections'][0]
        self.assertTrue(all(g['top'] is None for g in section['groups'].values()));self.assertIsNone(section['chords']);self.assertIsNone(section['function'])


class ScopeTests(unittest.TestCase):
    def rating(self):
        return dict(dict.fromkeys(NUMERIC,None),overall=5,enjoymentA=5,referenceA=5,preference='a',notes='',reviewed=True)

    def test_whole_song_is_supplement_not_rating_target(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,_=test_style_listening.ListeningTests().setup_study(folder)
            audition(lab,'auditionClip',dict(pair='p-0',side='a',mode='whole'));audition(lab,'auditionClip',dict(pair='p-0',side='b',mode='whole'))
            audition(lab,'auditionRate',dict(pair='p-0',ratings=self.rating()))
            result=audition(lab,'auditionSummary',{});q=result['qualifications']['p-0']
            self.assertTrue(q['retrievalEligible']);self.assertNotEqual(q['ratingRanges']['a']['start'],q['ratingRanges']['b']['start'])
            self.assertEqual(result['associations']['overall']['n'],1)
            audition(lab,'auditionDisposition',dict(pair='p-0',status='INVALID',reason='User rejected this comparison'))
            self.assertEqual(audition(lab,'auditionSummary',{})['associations']['overall']['n'],0)
            self.assertEqual(len(list(lab.db.execute("SELECT * FROM listening_events WHERE kind='RATING'"))),1);lab.db.close()

    def test_legacy_scope_mismatch_missing_null_and_time_dedup(self):
        with tempfile.TemporaryDirectory() as folder:
            lab,_=test_style_listening.ListeningTests().setup_study(folder);study,key=load(lab)
            for p in study['pairs']:
                event(lab,key,p['id'],'RATING',dict(schemaVersion=2,ratings=self.rating(),revealedBeforeRating=False,previewRequests={s:dict(p[s]['context']) for s in ('a','b')}))
            result=summary(lab,study,key,latest(lab,key));self.assertEqual(result['associations']['overall']['n'],0)
            self.assertTrue(all(not q['retrievalEligible'] for q in result['qualifications'].values()))
            self.assertIsNone(result['associations']['rhythm']['spearman']);lab.db.close()
