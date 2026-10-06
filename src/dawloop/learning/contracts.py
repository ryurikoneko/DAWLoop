# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""Schema与跨文档证据检查；只有显式人工映射才能形成生成参数。"""

from copy import deepcopy
from importlib.resources import files
import hashlib
import json
from pathlib import Path
import statistics

from dawloop.music_plan import StyleConstraints


FIELDS = (
    'rhythm_syncopation', 'melody_leap_tendency',
    'harmony_tension_usage', 'motif_variation_strength',
)
METRICS = {
    'note_density': 'notes_per_bar',
    'register_center': 'midi_number',
    'mean_abs_interval': 'semitones',
    'offbeat_ratio': 'ratio',
    'tension_ratio': 'ratio',
    'motif_change_ratio': 'ratio',
    'tempo': 'beats_per_minute',
    'phrase_length': 'bars',
    'mean_velocity': 'midi_1_127',
}
KINDS = ('reference_track', 'extracted_features', 'learning_report', 'style_profile')


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def content_hash(value):
    """内容摘要用于关联，不声称证明作者或来源真实性。"""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def validate_document(kind, document):
    _require(kind in KINDS, 'LEARNING_KIND_UNSUPPORTED')
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as error:
        raise RuntimeError('LEARNING_DEPENDENCY_MISSING: pip install dawloop[learning]') from error
    schema = json.loads(files('dawloop.learning').joinpath(
        f'schemas/{kind}.schema.json').read_text(encoding='utf-8'))
    # JSON不允许NaN/Infinity；Python内存对象也不能借Schema数值检查绕过。
    json.dumps(document, allow_nan=False)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
                    key=lambda error: str(list(error.path)))
    _require(not errors, 'LEARNING_SCHEMA_INVALID: ' + ('; '.join(
        f'{list(error.path)}: {error.message}' for error in errors[:3])))
    if kind == 'extracted_features':
        names = [feature['name'] for feature in document['features']]
        _require(len(names) == len(set(names)), 'DUPLICATE_FEATURE')
        for feature in document['features']:
            _require(feature['unit'] == METRICS[feature['name']], 'FEATURE_UNIT_MISMATCH')
            value = feature['value']
            if value is not None:
                _require(feature['missing_reason'] is None and feature['evidence_ref'] is not None
                         and feature['method'] != 'unknown', 'FEATURE_EVIDENCE_REQUIRED')
                _require(value >= 0, 'FEATURE_RANGE_INVALID')
                if feature['unit'] == 'ratio':
                    _require(value <= 1, 'FEATURE_RANGE_INVALID')
                if feature['unit'] == 'midi_number':
                    _require(value <= 127, 'FEATURE_RANGE_INVALID')
                if feature['unit'] == 'midi_1_127':
                    _require(1 <= value <= 127, 'FEATURE_RANGE_INVALID')
            else:
                _require(feature['method'] == 'unknown' and feature['confidence'] == 0
                         and bool(feature['missing_reason']), 'UNKNOWN_FEATURE_INVALID')
    if kind == 'style_profile':
        StyleConstraints.from_dict(document['constraints'])
        _require(document['profile_id'] == document['constraints']['profile_id'], 'PROFILE_ID_MISMATCH')
        _require((document['revision'] == 1 and document['parent_hash'] is None)
                 or (document['revision'] > 1 and document['parent_hash'] is not None),
                 'PROFILE_PARENT_REQUIRED')
        reports = [feedback['report_id'] for feedback in document['feedback']]
        _require(len(reports) == len(set(reports)), 'DUPLICATE_FEEDBACK_REPORT')
        _require(document['revision'] == len(reports) + 1, 'PROFILE_REVISION_HISTORY_MISMATCH')
        if document['revision'] == 1:
            _require(not document['user_overrides'], 'INITIAL_PROFILE_OVERRIDES_INVALID')
    return document


def _scope_key(scope):
    return (scope['section_type'], scope['role'], scope['meter'])


def aggregate_features(references, analyses, *, group_id, holdout_source_ids=()):
    """同一独立作品/声部/段落仅接收一个分析；重复片段先在分析器中合并。"""
    refs = {}
    for reference in references:
        validate_document('reference_track', reference)
        _require(reference['source_id'] not in refs, 'DUPLICATE_SOURCE_ID')
        _require(reference['reference_group'] == group_id, 'REFERENCE_GROUP_MISMATCH')
        refs[reference['source_id']] = reference
    holdout = set(holdout_source_ids)
    _require(holdout <= refs.keys(), 'HOLDOUT_SOURCE_UNKNOWN')
    seen, independent, content_seen, included, excluded = set(), set(), set(), [], []
    buckets = {}
    scope = None
    for analysis in analyses:
        validate_document('extracted_features', analysis)
        source_id = analysis['source_id']
        _require(source_id in refs and source_id not in seen, 'ANALYSIS_SOURCE_INVALID')
        seen.add(source_id)
        reference = refs[source_id]
        _require(analysis['source_hash'] == reference['content_hash'], 'SOURCE_HASH_MISMATCH')
        if source_id in holdout or reference['rights_status'] == 'unknown':
            excluded.append({'source_id': source_id, 'reason': 'holdout' if source_id in holdout
                             else 'rights_unknown'})
            continue
        key = _scope_key(analysis['scope'])
        if scope is None:
            scope = analysis['scope']
        _require(key == _scope_key(scope), 'ANALYSIS_SCOPE_MISMATCH')
        work = reference['independent_work_id']
        _require(work not in independent, 'DUPLICATE_INDEPENDENT_WORK')
        _require(reference['content_hash'] not in content_seen, 'DUPLICATE_REFERENCE_CONTENT')
        independent.add(work)
        content_seen.add(reference['content_hash'])
        included.append({'source_id': source_id, 'analysis_hash': content_hash(analysis)})
        for feature in analysis['features']:
            if feature['value'] is None:
                continue
            key = (feature['name'], feature['unit'], feature['definition_version'], feature['method'])
            buckets.setdefault(key, []).append((source_id, feature['value'], feature['confidence']))
    _require(bool(included), 'NO_ELIGIBLE_LEARNING_INPUT')
    for source_id in sorted(refs.keys() - seen):
        excluded.append({'source_id': source_id, 'reason': 'holdout' if source_id in holdout
                         else 'analysis_missing'})
    distributions = []
    for (name, unit, definition, method), samples in sorted(buckets.items()):
        values = [sample[1] for sample in samples]
        distributions.append({'name': name, 'unit': unit, 'definition_version': definition,
            'method': method, 'samples': [{'source_id': s, 'value': v} for s, v, _ in samples],
            'count': len(values), 'coverage': len(values) / len(included),
            'min': min(values), 'max': max(values), 'mean': statistics.mean(values),
            'stdev': statistics.pstdev(values), 'confidence_min': min(s[2] for s in samples),
            'classification': 'DESCRIPTIVE_ONLY'})
    report = {'schema_version': 'dawloop-learning-report-v1', 'group_id': group_id,
        'scope': deepcopy(scope), 'included': included, 'excluded': excluded,
        'independent_work_count': len(included), 'distributions': distributions,
        'holdout_source_ids': sorted(holdout), 'holdout_result': 'NOT_EVALUATED',
        'generalization': 'NOT_CERTIFIED'}
    validate_document('learning_report', report)
    return report


def validate_bundle(references, analyses, report):
    """重新计算统计，拒绝丢来源、改单位和伪造样本数量的聚合报告。"""
    validate_document('learning_report', report)
    expected = aggregate_features(references, analyses, group_id=report['group_id'],
                                  holdout_source_ids=report['holdout_source_ids'])
    _require(report == expected, 'LEARNING_REPORT_CONTENT_MISMATCH')
    return {'valid': True, 'independent_work_count': report['independent_work_count'],
            'generalization': 'NOT_CERTIFIED'}


def build_profile(report, *, profile_id, decisions):
    """人工决策显式给出旋钮值与理由，不把观测统计冒充已校准映射。"""
    validate_document('learning_report', report)
    _require(type(decisions) is dict and set(decisions) == set(FIELDS), 'ALL_MAPPING_DECISIONS_REQUIRED')
    constraints = {'profile_id': profile_id}
    mappings = []
    names = {distribution['name'] for distribution in report['distributions']}
    for field in FIELDS:
        decision = decisions[field]
        _require(type(decision) is dict and set(decision) == {'value', 'reason', 'feature_names'},
                 'MAPPING_DECISION_INVALID')
        _require(bool(decision['feature_names']) and set(decision['feature_names']) <= names,
                 'MAPPING_FEATURE_UNKNOWN')
        constraints[field] = decision['value']
        mappings.append({'field': field, 'feature_names': decision['feature_names'],
                         'reason': decision['reason']})
    profile = {'schema_version': 'dawloop-profile-revision-v1', 'profile_id': profile_id,
        'revision': 1, 'parent_hash': None, 'constraints': constraints,
        'mapping_version': 'manual-review-v1', 'report_hash': content_hash(report),
        'mappings': mappings, 'user_overrides': {}, 'feedback': []}
    validate_profile(profile, report=report)
    return profile


def validate_profile(profile, *, report=None, parent=None):
    validate_document('style_profile', profile)
    _require({mapping['field'] for mapping in profile['mappings']} == set(FIELDS)
             and len(profile['mappings']) == len(FIELDS), 'PROFILE_MAPPING_COVERAGE_INVALID')
    if report is not None:
        validate_document('learning_report', report)
        _require(profile['report_hash'] == content_hash(report), 'PROFILE_REPORT_HASH_MISMATCH')
        names = {item['name'] for item in report['distributions']}
        _require(all(set(mapping['feature_names']) <= names for mapping in profile['mappings']),
                 'PROFILE_EVIDENCE_UNKNOWN')
    if parent is not None:
        validate_document('style_profile', parent)
        _require(profile['profile_id'] == parent['profile_id']
                 and profile['revision'] == parent['revision'] + 1
                 and profile['parent_hash'] == content_hash(parent), 'PROFILE_LINEAGE_MISMATCH')
        _require(profile['feedback'][:len(parent['feedback'])] == parent['feedback']
                 and len(profile['feedback']) == len(parent['feedback']) + 1,
                 'FEEDBACK_HISTORY_MISMATCH')
        _require(all(profile[key] == parent[key] for key in ('mapping_version', 'report_hash', 'mappings')),
                 'PROFILE_EVIDENCE_HISTORY_CHANGED')
        feedback = profile['feedback'][-1]
        _require(feedback['profile_hash'] == content_hash(parent), 'FEEDBACK_PARENT_MISMATCH')
        expected = dict(parent['constraints'])
        expected.update(feedback['changes'])
        _require(profile['constraints'] == expected, 'FEEDBACK_CHANGES_MISMATCH')
        overrides = dict(parent['user_overrides'])
        overrides.update(feedback['changes'])
        _require(profile['user_overrides'] == overrides, 'PROFILE_OVERRIDES_MISMATCH')
    _require(profile['revision'] == 1 or parent is not None, 'PROFILE_PARENT_DOCUMENT_REQUIRED')
    return StyleConstraints.from_dict(profile['constraints'])


def revise_profile(parent, *, feedback, plan):
    validate_document('style_profile', parent)
    _require(type(feedback) is dict and feedback.get('plan_hash') == content_hash(plan),
             'FEEDBACK_PLAN_MISMATCH')
    revision = deepcopy(parent)
    revision.update(revision=parent['revision'] + 1, parent_hash=content_hash(parent))
    revision['feedback'].append(deepcopy(feedback))
    revision['constraints'].update(feedback.get('changes', {}))
    revision['user_overrides'].update(feedback.get('changes', {}))
    validate_profile(revision, parent=parent)
    return revision


def write_revision(path, profile, *, parent=None):
    """排他创建，防止覆盖旧版本；权限与个人目录由用户自己选择。"""
    validate_profile(profile, parent=parent)
    payload = json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(payload)
