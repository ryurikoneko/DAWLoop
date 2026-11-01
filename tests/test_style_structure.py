import sys
from pathlib import Path
import tempfile
import unittest
import json
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_lab import StyleLab,digest
from style_omar import VectorLab
from style_structure import coverage,features,edit_section,load_analysis,full_prompt


class FullCoverageTests(unittest.TestCase):
    def test_missing_tail_cannot_be_full_song(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'owned.wav';sf.write(p,np.zeros(44100*2+123),44100)
            lab=StyleLab(Path(folder)/'lab');asset=lab.import_audio([p])[0]
            v=object.__new__(VectorLab);v.lab=lab;v.version='TEST';v.root=lab.root
            lab.db.execute('CREATE TABLE vectors(id TEXT,asset TEXT,start REAL,end REAL,version TEXT,state TEXT,filename TEXT,metadata TEXT)')
            file=v.root/'test.npy';values=np.ones((50,1024),dtype='float32');np.save(file,values)
            meta=dict(sourceSha256=digest(p),vectorSha256=digest(file),globalTimestamps=(np.arange(50)/25).tolist())
            lab.db.execute('INSERT INTO vectors VALUES(?,?,?,?,?,?,?,?)',('x',asset,0,2,'TEST','READY',file.name,json.dumps(meta)));lab.db.commit()
            result=coverage(v,asset);self.assertFalse(result['complete']);self.assertEqual(result['gaps'],[[88200,88323]])
            with self.assertRaises(ValueError):features(v,asset)
            lab.db.close()

    def test_edit_keeps_continuous_timeline_and_original(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'owned.wav';sf.write(p,np.zeros(8000*10),8000)
            lab=StyleLab(Path(folder)/'lab');asset=lab.import_audio([p])[0]
            target=lab.root/'structure';target.mkdir()
            result=dict(asset=asset,sourceSha256=digest(p),coverage=dict(duration=10,complete=True),sections=[dict(id=0,start=0,end=5,label='Unknown'),dict(id=1,start=5,end=10,label='Unknown')])
            file=target/(asset+'.json');file.write_text(json.dumps(result),encoding='utf-8');original=file.read_bytes()
            value=edit_section(lab,asset,0,0,6,'Intro')
            self.assertEqual(value['sections'][1]['start'],6);self.assertEqual(file.read_bytes(),original)
            self.assertEqual(load_analysis(lab,asset)['sections'][0]['label'],'Intro')
            with self.assertRaises(ValueError):edit_section(lab,asset,0,1,6,'Intro')
            lab.db.close()
