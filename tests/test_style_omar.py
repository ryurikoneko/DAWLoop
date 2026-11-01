import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).parents[1]/'packages/music-intelligence'))
from style_lab import StyleLab,digest
from style_omar import VectorLab


class VectorContractTests(unittest.TestCase):
    def test_timeline_retrieval_feedback_and_cache_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            lab=StyleLab(temporary)
            vectors=object.__new__(VectorLab)
            vectors.lab=lab;vectors.root=Path(temporary);vectors.version='TEST_FIXTURE'
            lab.db.executescript('CREATE TABLE vectors(id TEXT PRIMARY KEY,asset TEXT,start REAL,end REAL,version TEXT,state TEXT,filename TEXT,metadata TEXT);CREATE TABLE vector_feedback(query_id TEXT,candidate_id TEXT,liked INTEGER,created REAL);')
            for i in range(4):
                file=Path(temporary)/f'{i}.npy'
                values=np.random.default_rng(i).normal(size=(125,1024)).astype('float32')
                np.save(file,values,allow_pickle=False)
                start=(i//2)*25
                meta=dict(globalTimestamps=(np.arange(125)/25+start).tolist(),vectorSha256=digest(file))
                lab.db.execute('INSERT INTO vectors VALUES(?,?,?,?,?,?,?,?)',(str(i),str(i%2),start,start+5,'TEST_FIXTURE','READY',file.name,json.dumps(meta)))
            lab.db.commit()
            rows=vectors.descriptors();query=rows[0]['id']
            results=vectors.search(query)
            self.assertTrue(all(r['asset']!=rows[0]['asset'] for r in results))
            self.assertEqual(results,vectors.search(query))
            within=vectors.search(query,'within')
            self.assertTrue(all(abs(r['start']-rows[0]['start'])>=15 for r in within))
            vectors.feedback(query,results[0]['id'],-1)
            self.assertNotEqual(results,vectors.search(query))
            self.assertEqual(vectors.clusters(2),vectors.clusters(2))
            self.assertIsInstance(vectors.save_profile('TEST_FIXTURE',[query]),int)
            with lab.db:
                lab.db.execute("UPDATE vectors SET state='PROCESSING' WHERE id='0'")
            vectors.recover()
            self.assertEqual(lab.db.execute("SELECT state FROM vectors WHERE id='0'").fetchone()[0],'QUEUED')
            (Path(temporary)/'1.npy').write_bytes(b'corrupt fixture')
            with self.assertRaises(ValueError):
                vectors.descriptors()
            lab.db.close()
