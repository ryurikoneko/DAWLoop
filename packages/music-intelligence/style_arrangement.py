"""编曲研究草案：测量、用户偏好与创作选择分别保存。"""
import json
import re
from pathlib import Path

INTRO_TYPES = ('Motif-led', 'Atmosphere-led', 'Groove-led', 'Vocal-led', 'Texture-led', 'Hybrid')
ENTRY_FIELDS = ('vocals', 'melody', 'bass', 'kick', 'drums', 'mainTimbres', 'coreMotifEstablished')
NEGATIVE = (
    '过短的模板化 Intro', '开头立即出现上升鼓组', 'Snare Roll 和 Riser 强行制造起势',
    '尚未建立旋律就急于进入 Verse', '过度依赖传统 EDM Build-up', '突然收束后进入主歌的机械式过渡',
)
SCHEMES = (
    dict(id='motif', title='旋律动机先行', titleEn='Motif first', types=['Motif-led'],
         sections=['Intro', 'Verse 1', 'Drop 1', 'Breakdown', 'Verse 2', 'Build-up', 'Drop 2', 'Outro'],
         opening='A clear pluck motif opens alone; harmony and a light pulse join before the vocal verse continues that motif.',
         development='Let the first verse flow directly into a melodic drop. A spacious breakdown introduces a counter-melody; build later toward the final drop.'),
    dict(id='atmosphere', title='氛围与音色交接', titleEn='Atmosphere and texture', types=['Atmosphere-led', 'Texture-led'],
         sections=['Intro', 'Verse 1', 'Build-up', 'Drop 1', 'Breakdown', 'Verse 2', 'Drop 2', 'Outro'],
         opening='Warm sustained harmony and delicate textures gradually reveal a melodic phrase; the Japanese vocal enters over the same harmony.',
         development='Lift from the first verse into a melodic drop. Thin the texture into a breakdown, retain the motif through the second verse, then return to a varied drop.'),
    dict(id='groove', title='律动与旋律同步', titleEn='Groove and melody together', types=['Groove-led', 'Motif-led'],
         sections=['Intro', 'Verse 1', 'Drop 1', 'Verse 2', 'Breakdown', 'Build-up', 'Drop 2', 'Outro'],
         opening='A relaxed syncopated bass pulse and short melodic hook begin together; keep percussion sparse and steady as the verse enters.',
         development='Develop the hook into the first drop, carry its rhythm into a second verse, then open space in a breakdown before the final melodic lift.'),
)


def lyric_sections(lyrics):
    return re.findall(r'^\[([^\]:]+)(?::[^\]]*)?\]\s*$', lyrics, re.M)


def draft(scheme, lyric_blocks):
    sections = scheme['sections']
    if set(sections) - set(lyric_blocks):
        raise ValueError('ARRANGEMENT_LYRIC_SECTION_MISSING')
    parts = dict(
        direction='Kawaii future bass / Japanese electronic pop, airy Japanese female vocals.',
        language='Playful melodic hooks, syncopated bass answering the kick, sparkling plucks, warm sustained pads and rounded sub-bass; vary note length and layers rather than only loudness.',
        arrangement=scheme['opening'] + ' ' + scheme['development'],
        preferences='Establish the musical idea before lifting the energy; keep opening percussion steady and transitions connected.',
    )
    style = ' '.join(parts.values())
    lyrics = '\n\n'.join('[' + section + ']\n' + lyric_blocks[section] for section in sections)
    return dict(**scheme, parts=parts, style=style, lyrics=lyrics,
                structurePlan=' > '.join(sections), lyricCompatibility=lyric_sections(lyrics) == sections,
                status='CREATIVE_DRAFT_NOT_REFERENCE_CLASSIFICATION', source='MAINTAINER_DIRECTION_AND_EXPLICIT_PREFERENCES')


def opening_evidence(structure):
    duration = structure['coverage']['duration']
    first = structure.get('sections', [{}])[0]
    end = first.get('end')
    return dict(asset=structure['asset'], sourceSha256=structure['sourceSha256'], duration=duration,
                candidateOpeningRange=[0, end] if end else None,
                openingRangeStatus='CANDIDATE_NOT_VERIFIED_INTRO',
                entryTimes={key: None for key in ENTRY_FIELDS}, introTypes=[],
                transition=None, classificationStatus='INSUFFICIENT_ENTRY_AND_LISTENING_EVIDENCE',
                availableMethods=['full-song DSP', 'OMAR temporal structure candidate'],
                missingEvidence=['verified full intro boundary', 'timestamped instrument and motif observations', 'intro-to-verse listening review'])


def workspace(root):
    file = Path(root) / 'phase7.1' / 'arrangement-candidate.json'
    if not file.is_file():
        return None
    data = json.loads(file.read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('ARRANGEMENT_SCHEMA_UNSUPPORTED')
    return data
