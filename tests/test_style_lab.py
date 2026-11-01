import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('style_lab', Path(__file__).parents[1] / 'packages/music-intelligence/style_lab.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StyleLabTests(unittest.TestCase):
    def test_dedup_persistence_and_missing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'owned.wav'
            source.write_bytes(b'owned invalid audio for import-only test')
            root = Path(folder) / 'lab'
            lab = module.StyleLab(root)
            first = lab.import_audio([source])[0]
            self.assertEqual(lab.import_audio([source]), [first])
            job = lab.enqueue(first)
            self.assertEqual(lab.enqueue(first), job)
            lab.db.close()
            source.unlink()
            restored = module.StyleLab(root)
            self.assertEqual(restored.search()[0]['availability'], 'MISSING_SOURCE')
            self.assertEqual(restored.db.execute('SELECT count(*) FROM jobs').fetchone()[0], 1)
            restored.db.close()

    def test_cancel_retry_and_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'owned.mp3'
            source.write_bytes(b'owned fixture')
            lab = module.StyleLab(Path(folder) / 'lab')
            asset = lab.import_audio([source])[0]
            job = lab.enqueue(asset)
            lab.cancel(job)
            self.assertEqual(lab.db.execute('SELECT state FROM jobs').fetchone()[0], 'CANCELLED')
            lab.retry(job)
            self.assertEqual(lab.db.execute('SELECT state FROM jobs').fetchone()[0], 'QUEUED')
            with self.assertRaises(ValueError):
                lab.enqueue(asset, 10, 5)
            with self.assertRaises(ValueError):
                lab.rate(asset, 8)
            lab.db.close()

    def test_recovery_does_not_promote_incomplete_result(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'owned.wav'
            source.write_bytes(b'owned fixture')
            lab = module.StyleLab(Path(folder) / 'lab')
            asset = lab.import_audio([source])[0]
            lab.enqueue(asset)
            with lab.db:
                lab.db.execute("UPDATE jobs SET state='PROCESSING'")
            lab.recover()
            self.assertEqual(lab.db.execute('SELECT state FROM jobs').fetchone()[0], 'INTERRUPTED')
            lab.db.close()
