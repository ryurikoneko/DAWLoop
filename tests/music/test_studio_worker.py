"""独立测试素材检验中文路径和同音重叠，不作为音乐分析结果。"""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path

class StudioWorkerTest(unittest.TestCase):
 def test_overlapping_repeated_notes_keep_end_times_and_utf8_path(self):
  with tempfile.TemporaryDirectory(prefix='dawloop-studio-') as folder:
   target=Path(folder)/'测试_声部.mid'
   notes=[dict(id='a',pitch=81,start=.123,end=.723,velocity=90),dict(id='b',pitch=81,start=.423,end=.923,velocity=80),dict(id='c',pitch=60,start=.123,end=.723,velocity=70)]
   session=dict(tempo=[dict(time=0,bpm=100),dict(time=.5,bpm=120)],beats=[[0,1,1,8],[.3,1,4,4],[.9,2,4,4]],tracks=[dict(id='vocal',notes=notes),dict(id='chords',notes=[dict(id='d',pitch=81,start=.123,end=.623,velocity=60)])])
   script=Path(__file__).resolve().parents[2]/'packages/music-intelligence/studio-worker.py'
   result=subprocess.run([sys.executable,str(script)],input=json.dumps(dict(method='export',params=dict(session=session,track='combined',path=str(target))),ensure_ascii=False)+'\n',encoding='utf-8',capture_output=True,check=True)
   payload=json.loads(result.stdout.strip());self.assertEqual(payload['kind'],'result',payload);self.assertTrue(target.is_file());self.assertEqual(target.read_bytes()[:4],b'MThd');self.assertEqual(payload['data']['notes'],4);self.assertLess(payload['data']['maxErrorSeconds'],.003)

if __name__=='__main__':unittest.main()
