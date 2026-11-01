"""从已有研究和歌词准备新草案；不修改原实验与评分。"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/music-intelligence'))
from style_arrangement import INTRO_TYPES, NEGATIVE, SCHEMES, draft, opening_evidence


def prepare(root, lyrics_file):
    root = Path(root)
    output = root / 'phase7.1'
    if output.exists():
        raise ValueError('NEW_ARRANGEMENT_CANDIDATE_REQUIRED')
    lyrics = Path(lyrics_file).read_text(encoding='utf-8')
    chunks = re.split(r'^\[([^\]]+)\]\s*\n', lyrics, flags=re.M)
    original = {chunks[i]: chunks[i + 1].strip() for i in range(1, len(chunks), 2)}
    blocks = dict(original)
    blocks['Build-up'] = original['Build-up 1']
    blocks['Drop 2'] = original['Build-up 2'] + '\n' + original['Drop 2']
    proposals = [draft(s, blocks) for s in SCHEMES]
    inventory = json.loads((root / 'phase3-library/inventory.json').read_text(encoding='utf-8'))
    references = []
    for item in inventory['files']:
        if item['status'] != 'VALID':
            continue
        file = root / 'structure' / (item['asset'] + '.json')
        structure = json.loads(file.read_text(encoding='utf-8'))
        if structure['sourceSha256'] != item['sha256']:
            raise ValueError('REFERENCE_IDENTITY_MISMATCH')
        row = opening_evidence(structure)
        row.update(name=item['name'], evidenceFile=str(file), credits=item['credits'])
        references.append(row)
    personal = json.loads((root / 'phase6/personal-profile.json').read_text(encoding='utf-8'))
    preferences = dict(schemaVersion=1, owner='MAINTAINER', source='EXPLICIT_MAINTAINER_PHASE_7_1_REQUEST',
        positiveSource=str(root / 'phase6/personal-profile.json'), positiveClaims=personal['claims'],
        sourceRatingEvents=personal['sourceRatingEvents'], negative=list(NEGATIVE),
        scope='DEFAULT_GENERATION_PREFERENCE_NOT_REFERENCE_FACT',
        exceptions='不排斥所有鼓组、Build-up 或渐进能量；具体作品观察与采用决定分开。',
        learnedWeights=None)
    data = dict(schemaVersion=1, policy='ADAPTIVE_REFERENCE_AND_USER_GOAL', introTypes=list(INTRO_TYPES),
                references=references, preferences=preferences, proposals=proposals,
                referenceClassificationComplete=False, generatedAudioCount=None,
                baseline='phase7/generation.sqlite remains unchanged')
    output.mkdir()
    (output / 'arrangement-candidate.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'personal-preferences.json').write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding='utf-8')
    text = ['# 动态编曲候选\n', '三套均为创作草案，不是十首参考曲的已识别编曲。原 A 组与全部评分保留。\n']
    for p in proposals:
        text += ['## ' + p['title'], '\n风格栏：\n```text\n' + p['style'] + '\n```',
                 '\n歌词栏：\n```text\n' + p['lyrics'] + '\n```', '\n段落：' + p['structurePlan'] + '\n']
    text += ['## 生成实验', '先选一套；保持同一平台模型、日语歌词、人声、BPM、时长及可控参数。每次只改开场策略，至少保留两次结果。三套段落不同，完整方案比较不能归因于 Intro 单因素。若只检验 Intro，固定下游段落和歌词，仅更换开头行为。记录实际输出段落、首个人声/鼓组进入时间、突变位置和用户评价；不自动填分。',
             '复制风格与对应歌词到两个输入栏。旧歌词不应直接配用新方案。Suno 是否遵循这些要求尚待真实生成检验。']
    (output / '可复制编曲草案.md').write_text('\n\n'.join(text), encoding='utf-8')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('lyrics')
    args = parser.parse_args()
    result = prepare(args.root, args.lyrics)
    print(json.dumps(dict(references=len(result['references']), proposals=len(result['proposals']), lyricsCompatible=all(p['lyricCompatibility'] for p in result['proposals']))))
