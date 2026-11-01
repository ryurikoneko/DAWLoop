import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/music-intelligence'))
from style_arrangement import SCHEMES, ENTRY_FIELDS, draft, lyric_sections, opening_evidence, workspace


class ArrangementTests(unittest.TestCase):
    def test_distinct_forms_and_matching_lyrics(self):
        blocks = {s: 'テストの歌' for p in SCHEMES for s in p['sections']}
        proposals = [draft(p, blocks) for p in SCHEMES]
        self.assertEqual(len({p['structurePlan'] for p in proposals}), 3)
        for p in proposals:
            self.assertTrue(p['lyricCompatibility'])
            self.assertEqual(lyric_sections(p['lyrics']), p['sections'])
            self.assertEqual(len(p['parts']), 4)
            self.assertLess(len(p['style']), 1100)
            self.assertNotIn('Yunomi', p['style'])

    def test_missing_lyrics_rejected(self):
        with self.assertRaisesRegex(ValueError, 'LYRIC_SECTION_MISSING'):
            draft(SCHEMES[0], {})

    def test_structure_does_not_prove_entry_or_class(self):
        row = opening_evidence(dict(asset='TEST_FIXTURE', sourceSha256='test', coverage=dict(duration=120), sections=[dict(start=0, end=23)]))
        self.assertEqual(row['candidateOpeningRange'], [0, 23])
        self.assertFalse(row['introTypes'])
        self.assertEqual(set(row['entryTimes']), set(ENTRY_FIELDS))
        self.assertTrue(all(v is None for v in row['entryTimes'].values()))
        self.assertIsNone(row['transition'])

    def test_optional_candidate_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(workspace(root))
            p = Path(root) / 'phase7.1'
            p.mkdir()
            file = p / 'arrangement-candidate.json'
            file.write_text(json.dumps(dict(schemaVersion=1, proposals=[])), encoding='utf-8')
            self.assertEqual(workspace(root), workspace(root))
            file.write_text('{"schemaVersion":2}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SCHEMA_UNSUPPORTED'):
                workspace(root)


if __name__ == '__main__':
    unittest.main()
