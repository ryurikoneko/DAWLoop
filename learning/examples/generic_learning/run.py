# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""离线合成例子：用本地自有音符生成分析、报告、profile和MusicalPlan。"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics

from dawloop.learning import aggregate_features, build_profile, content_hash
from dawloop.learning import revise_profile, validate_bundle, validate_profile, write_revision
from dawloop.music_plan import PlanningRequest, generate_reference_plan


HERE = Path(__file__).resolve().parent


def build_example():
    references, analyses = [], []
    for source_id in ('sample-a', 'sample-b', 'sample-holdout'):
        path = HERE / f'{source_id}.json'
        payload = path.read_bytes()
        sample = json.loads(payload.decode('utf-8'))
        reference = {
            'schema_version': 'dawloop-reference-v1', 'source_id': source_id,
            'source_label': 'Synthetic exercise', 'reference_group': 'generic-learning',
            'independent_work_id': source_id, 'material_kind': 'synthetic',
            'local_ref': f'references/{source_id}.json',
            'content_hash': hashlib.sha256(payload).hexdigest(), 'rights_status': 'owned',
            'rights_note': 'Synthetic notes supplied with this MIT example',
        }
        notes = sample['notes']
        values = {
            'note_density': (len(notes) / sample['bars'], 'notes_per_bar'),
            'mean_abs_interval': (statistics.mean(abs(b['pitch'] - a['pitch'])
                for a, b in zip(notes, notes[1:])), 'semitones'),
            'offbeat_ratio': (sum(n['start'] % sample['ppq'] != 0 for n in notes) / len(notes), 'ratio'),
            'tension_ratio': (sum(n['pitch'] % 12 not in (0, 4, 7) for n in notes) / len(notes), 'ratio'),
            'motif_change_ratio': (sum(notes[i]['pitch'] != notes[i + 2]['pitch']
                for i in range(2)) / 2, 'ratio'),
        }
        analyses.append({
            'schema_version': 'dawloop-features-v1', 'source_id': source_id,
            'source_hash': reference['content_hash'],
            'scope': {'section_type': 'verse', 'role': 'pluck', 'meter': '4/4'},
            'analyzer': {'id': 'synthetic-example', 'version': '1'},
            'features': [{'name': name, 'value': value, 'unit': unit,
                'definition_version': 'dawloop-feature-v1', 'method': 'observed',
                'confidence': 1, 'evidence_ref': f'{source_id}.json#/notes', 'missing_reason': None}
                for name, (value, unit) in values.items()],
        })
        references.append(reference)
    report = aggregate_features(references, analyses, group_id='generic-learning',
                                holdout_source_ids=('sample-holdout',))
    validate_bundle(references, analyses, report)
    decisions = {
        'rhythm_syncopation': {'value': 0.2, 'feature_names': ['offbeat_ratio'],
            'reason': 'Illustrative reviewer choice; no calibrated conversion from offbeat ratio'},
        'melody_leap_tendency': {'value': 0.25, 'feature_names': ['mean_abs_interval'],
            'reason': 'Illustrative mild motion preference within hard leap limits'},
        'harmony_tension_usage': {'value': 0.25, 'feature_names': ['tension_ratio'],
            'reason': 'Illustrative low tension preference; eligibility remains a hard constraint'},
        'motif_variation_strength': {'value': 1, 'feature_names': ['motif_change_ratio'],
            'reason': 'Allow existing variation budget; not a measured artistic characteristic'},
    }
    profile = build_profile(report, profile_id='generic-example', decisions=decisions)
    request = json.loads((HERE / 'request.json').read_text(encoding='utf-8'))
    request['style_constraints'] = deepcopy(profile['constraints'])
    plan = generate_reference_plan(PlanningRequest.from_dict(request)).to_dict()
    feedback = {
        'report_id': 'synthetic-feedback-1', 'source': 'HUMAN', 'context': 'SYNTHETIC_EXAMPLE',
        'profile_hash': content_hash(profile), 'plan_hash': content_hash(plan),
        'reported_at': '2026-10-07T00:00:00Z', 'outcome': 'VISUAL_REVIEW_ONLY',
        'reason': 'Synthetic feedback fixture; nobody has listened or approved this output',
        'changes': {'rhythm_syncopation': 0.1},
    }
    revised = revise_profile(profile, feedback=feedback, plan=plan)
    validate_profile(revised, report=report, parent=profile)
    return {'references': references, 'analyses': analyses, 'report': report,
            'profile_v1': profile, 'profile_v2': revised, 'request': request, 'plan': plan}


def main():
    parser = argparse.ArgumentParser(description='生成合成学习合同示例；不会访问FL')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # 整个输出目录必须是新的，避免例子覆盖用户已有分析或profile。
    args.output.mkdir(parents=True, exist_ok=False)
    result = build_example()
    references_dir = args.output / 'references'
    references_dir.mkdir()
    for reference in result['references']:
        (references_dir / f"{reference['source_id']}.json").write_bytes(
            (HERE / f"{reference['source_id']}.json").read_bytes())
    for name, value in result.items():
        path = args.output / f'{name}.json'
        if name.startswith('profile_'):
            write_revision(path, value, parent=result['profile_v1'] if name == 'profile_v2' else None)
        else:
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'valid': True, 'note_count': len(result['plan']['notes']),
                      'live_certification': 'NONE', 'audition': 'NOT_PERFORMED'}))


if __name__ == '__main__':
    main()
