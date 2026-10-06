"""离线音乐语义合同；不导入宿主、MCP或脚本执行器。"""

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math

from dawloop.note_plan import NoteEvent
from dawloop.time import MusicalGrid


SCHEMA_VERSION = 'dawloop-musical-plan-v1'
MAX_NOTES = 16
SCALES = {'major': (0, 2, 4, 5, 7, 9, 11), 'natural_minor': (0, 2, 3, 5, 7, 8, 10)}
CHORDS = {'major': (0, 4, 7), 'minor': (0, 3, 7), 'diminished': (0, 3, 6)}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _unit(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _text(value):
    return type(value) is str and bool(value.strip())


def _object(value, cls):
    _require(type(value) is dict and set(value) == {f.name for f in fields(cls)},
             f'{cls.__name__.upper()}_FIELDS_INVALID')
    return dict(value)


def _array(value):
    _require(type(value) is list, 'ARRAY_REQUIRED')
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class SectionBrief:
    section_type: str
    bars: int
    energy_start: float
    energy_end: float
    density: int
    motion: float
    tension: float
    role: str

    def __post_init__(self):
        _require(type(self.section_type) is str
                 and self.section_type in ('intro', 'verse', 'pre', 'drop', 'bridge', 'outro'),
                 'SECTION_TYPE_UNSUPPORTED')
        _require(_integer(self.bars, 1, 8), 'BAR_RANGE_INVALID')
        _require(_integer(self.density, 1, MAX_NOTES) and self.bars * self.density <= MAX_NOTES,
                 'OFFLINE_NOTE_BUDGET_EXCEEDED')
        _require(all(_unit(v) for v in (self.energy_start, self.energy_end, self.motion, self.tension)),
                 'PREFERENCE_RANGE_INVALID')
        _require(type(self.role) is str and self.role in ('melody', 'pluck', 'bass'), 'ROLE_UNSUPPORTED')


@dataclass(frozen=True)
class ChordRegion:
    chord_id: str
    start_bar: int
    end_bar: int
    root: int
    quality: str

    def __post_init__(self):
        _require(_text(self.chord_id), 'CHORD_ID_REQUIRED')
        _require(_integer(self.start_bar, 1, 8) and _integer(self.end_bar, self.start_bar, 8),
                 'CHORD_REGION_INVALID')
        _require(_integer(self.root, 0, 11) and type(self.quality) is str and self.quality in CHORDS,
                 'CHORD_UNSUPPORTED')

    @property
    def pitch_classes(self):
        return frozenset((self.root + interval) % 12 for interval in CHORDS[self.quality])


@dataclass(frozen=True)
class HarmonyContext:
    key: int
    scale: str
    progression: tuple[ChordRegion, ...]
    harmonic_rhythm: int
    allowed_tensions: tuple[int, ...]

    def __post_init__(self):
        _require(_integer(self.key, 0, 11) and type(self.scale) is str and self.scale in SCALES,
                 'KEY_SCALE_UNSUPPORTED')
        _require(type(self.progression) is tuple and bool(self.progression)
                 and all(type(c) is ChordRegion for c in self.progression), 'CHORD_REGIONS_REQUIRED')
        _require(_integer(self.harmonic_rhythm, 1, 8), 'HARMONIC_RHYTHM_INVALID')
        _require(type(self.allowed_tensions) is tuple
                 and all(_integer(p, 0, 11) for p in self.allowed_tensions)
                 and len(set(self.allowed_tensions)) == len(self.allowed_tensions)
                 and set(self.allowed_tensions) <= self.pitch_classes, 'TENSIONS_INVALID')

    @property
    def pitch_classes(self):
        return frozenset((self.key + interval) % 12 for interval in SCALES[self.scale])


@dataclass(frozen=True)
class VoiceConstraints:
    min_pitch: int
    max_pitch: int
    preferred_center: int
    max_leap: int
    polyphony_limit: int
    overlap_policy: str

    def __post_init__(self):
        _require(_integer(self.min_pitch, 0, 127) and _integer(self.max_pitch, self.min_pitch, 127)
                 and _integer(self.preferred_center, self.min_pitch, self.max_pitch), 'REGISTER_INVALID')
        _require(_integer(self.max_leap, 0, 127), 'MAX_LEAP_INVALID')
        _require(_integer(self.polyphony_limit, 1, MAX_NOTES), 'POLYPHONY_INVALID')
        _require(self.overlap_policy in ('forbid', 'allow'), 'OVERLAP_POLICY_UNSUPPORTED')


@dataclass(frozen=True)
class VariationConstraints:
    motif_length: int
    repeat_count: int
    variation_strength: float
    preserve_rhythm: bool
    preserve_contour: bool
    phrase_boundary_behavior: str

    def __post_init__(self):
        _require(_integer(self.motif_length, 1, 8) and _integer(self.repeat_count, 1, 8),
                 'MOTIF_STRUCTURE_INVALID')
        _require(_unit(self.variation_strength), 'VARIATION_STRENGTH_INVALID')
        _require(type(self.preserve_rhythm) is bool and type(self.preserve_contour) is bool,
                 'PRESERVATION_FLAG_INVALID')
        _require(self.phrase_boundary_behavior in ('stop_at_boundary', 'allow_tie'),
                 'PHRASE_BOUNDARY_UNSUPPORTED')


@dataclass(frozen=True)
class StyleConstraints:
    profile_id: str
    rhythm_syncopation: float
    melody_leap_tendency: float
    harmony_tension_usage: float
    motif_variation_strength: float

    def __post_init__(self):
        _require(_text(self.profile_id), 'PROFILE_ID_REQUIRED')
        _require(all(_unit(value) for value in (self.rhythm_syncopation,
            self.melody_leap_tendency, self.harmony_tension_usage, self.motif_variation_strength)),
            'PROFILE_PREFERENCE_INVALID')

    @classmethod
    def from_dict(cls, value):
        return cls(**_object(value, cls))


@dataclass(frozen=True)
class PlanningRequest:
    intent: str
    grid: MusicalGrid
    section: SectionBrief
    harmony: HarmonyContext
    voice: VoiceConstraints
    variation: VariationConstraints
    style_constraints: StyleConstraints | None = None

    def __post_init__(self):
        _require(_text(self.intent), 'INTENT_REQUIRED')
        _require(type(self.grid) is MusicalGrid and type(self.section) is SectionBrief
                 and type(self.harmony) is HarmonyContext and type(self.voice) is VoiceConstraints
                 and type(self.variation) is VariationConstraints, 'TYPED_REQUEST_REQUIRED')
        _require(self.style_constraints is None or type(self.style_constraints) is StyleConstraints,
                 'STYLE_CONSTRAINTS_INVALID')
        _require(self.grid.beats_per_bar == 4 and self.grid.beat_unit == 4,
                 'V1_FOUR_FOUR_REQUIRED')
        _require(self.voice.polyphony_limit == 1, 'V1_MONOPHONIC_REQUEST_REQUIRED')
        _require(self.variation.motif_length * self.variation.repeat_count == self.section.bars,
                 'MOTIF_COVERAGE_INVALID')
        next_bar = 1
        ids = set()
        for chord in self.harmony.progression:
            _require(chord.start_bar == next_bar and chord.chord_id not in ids
                     and chord.end_bar - chord.start_bar + 1 == self.harmony.harmonic_rhythm,
                     'HARMONY_COVERAGE_INVALID')
            _require(chord.pitch_classes <= self.harmony.pitch_classes, 'CHORD_OUTSIDE_SCALE')
            next_bar = chord.end_bar + 1
            ids.add(chord.chord_id)
        _require(next_bar == self.section.bars + 1, 'HARMONY_COVERAGE_INVALID')

    def to_dict(self):
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, value):
        data = _object(value, cls)
        data['grid'] = MusicalGrid(**_object(data['grid'], MusicalGrid))
        data['section'] = SectionBrief(**_object(data['section'], SectionBrief))
        harmony = _object(data['harmony'], HarmonyContext)
        harmony['progression'] = tuple(ChordRegion(**_object(c, ChordRegion))
                                       for c in _array(harmony['progression']))
        harmony['allowed_tensions'] = tuple(_array(harmony['allowed_tensions']))
        data['harmony'] = HarmonyContext(**harmony)
        data['voice'] = VoiceConstraints(**_object(data['voice'], VoiceConstraints))
        data['variation'] = VariationConstraints(**_object(data['variation'], VariationConstraints))
        if data['style_constraints'] is not None:
            data['style_constraints'] = StyleConstraints.from_dict(data['style_constraints'])
        return cls(**data)


@dataclass(frozen=True)
class PlannedNote:
    note_id: str
    pitch: int
    start: int
    length: int
    velocity: int
    chord_id: str
    harmonic_function: str

    def __post_init__(self):
        _require(_text(self.note_id) and _text(self.chord_id), 'NOTE_REFERENCES_REQUIRED')
        NoteEvent(self.start, self.length, self.pitch, self.velocity)
        _require(self.harmonic_function in ('chord_tone', 'tension'), 'HARMONIC_FUNCTION_INVALID')


@dataclass(frozen=True)
class Phrase:
    phrase_id: str
    start_bar: int
    end_bar: int
    function: str
    motif_id: str
    derived_from: str | None
    note_ids: tuple[str, ...]
    pitch_changes: int
    rhythm_changes: int
    contour_changes: int
    mean_register_shift: float

    def __post_init__(self):
        _require(_text(self.phrase_id) and _text(self.motif_id)
                 and (self.derived_from is None or _text(self.derived_from)), 'PHRASE_ID_INVALID')
        _require(_integer(self.start_bar, 1, 8) and _integer(self.end_bar, self.start_bar, 8)
                 and self.function in ('establish', 'variation'), 'PHRASE_FIELDS_INVALID')
        _require(type(self.note_ids) is tuple and bool(self.note_ids)
                 and all(_text(n) for n in self.note_ids), 'PHRASE_NOTE_REFERENCES_REQUIRED')
        _require(all(_integer(n, 0, MAX_NOTES) for n in (self.pitch_changes,
                 self.rhythm_changes, self.contour_changes))
                 and type(self.mean_register_shift) in (int, float)
                 and math.isfinite(self.mean_register_shift), 'VARIATION_SUMMARY_INVALID')


@dataclass(frozen=True)
class Motif:
    motif_id: str
    source_phrase_id: str
    note_ids: tuple[str, ...]

    def __post_init__(self):
        _require(_text(self.motif_id) and _text(self.source_phrase_id)
                 and type(self.note_ids) is tuple and bool(self.note_ids)
                 and all(_text(n) for n in self.note_ids), 'MOTIF_FIELDS_INVALID')


@dataclass(frozen=True)
class MusicalPlan:
    schema_version: str
    metadata: dict
    target_role: str
    ppq: int
    bars: int
    notes: tuple[PlannedNote, ...]
    phrase_map: tuple[Phrase, ...]
    motif_map: tuple[Motif, ...]
    constraints_snapshot: PlanningRequest
    provenance: dict

    def to_dict(self):
        # 每次输出独立副本，避免调用方通过序列化结果改写原计划。
        validate_musical_plan(self)
        return json.loads(json.dumps(asdict(self), ensure_ascii=False, allow_nan=False))

    @classmethod
    def from_dict(cls, value):
        data = _object(value, cls)
        data['constraints_snapshot'] = PlanningRequest.from_dict(data['constraints_snapshot'])
        data['notes'] = tuple(PlannedNote(**_object(n, PlannedNote)) for n in _array(data['notes']))
        phrases = []
        for item in _array(data['phrase_map']):
            phrase = _object(item, Phrase)
            phrase['note_ids'] = tuple(_array(phrase['note_ids']))
            phrases.append(Phrase(**phrase))
        data['phrase_map'] = tuple(phrases)
        motifs = []
        for item in _array(data['motif_map']):
            motif = _object(item, Motif)
            motif['note_ids'] = tuple(_array(motif['note_ids']))
            motifs.append(Motif(**motif))
        data['motif_map'] = tuple(motifs)
        plan = cls(**data)
        validate_musical_plan(plan)
        return plan


def chord_at(request, tick):
    bar = tick // request.grid.ticks_per_bar + 1
    for chord in request.harmony.progression:
        if chord.start_bar <= bar <= chord.end_bar:
            return chord
    raise ValueError('NOTE_OUTSIDE_HARMONY')


def eligible_pitches(request, tick):
    chord = chord_at(request, tick)
    allowed = (chord.pitch_classes | set(request.harmony.allowed_tensions)) & request.harmony.pitch_classes
    return tuple(p for p in range(request.voice.min_pitch, request.voice.max_pitch + 1)
                 if p % 12 in allowed)


def _sign(value):
    return (value > 0) - (value < 0)


def _contour(notes):
    return tuple(_sign(b.pitch - a.pitch) for a, b in zip(notes, notes[1:]))


def _phrase_map(request, notes):
    width = request.variation.motif_length * request.grid.ticks_per_bar
    base = tuple(n for n in notes if n.start < width)
    _require(bool(base), 'BASE_MOTIF_REQUIRED')
    phrases = []
    for index in range(request.variation.repeat_count):
        group = tuple(n for n in notes if index * width <= n.start < (index + 1) * width)
        _require(len(group) == len(base), 'MOTIF_NOTE_COUNT_MISMATCH')
        pitch_changes = sum(a.pitch != b.pitch for a, b in zip(base, group))
        rhythm_changes = sum((a.start, a.length) != (b.start - index * width, b.length)
                             for a, b in zip(base, group))
        contour_changes = sum(a != b for a, b in zip(_contour(base), _contour(group)))
        shift = sum(b.pitch - a.pitch for a, b in zip(base, group)) / len(base)
        phrases.append(Phrase(f'phrase-{index + 1}', index * request.variation.motif_length + 1,
            (index + 1) * request.variation.motif_length,
            'establish' if index == 0 else 'variation', 'motif-A',
            None if index == 0 else 'phrase-1', tuple(n.note_id for n in group),
            pitch_changes, rhythm_changes, contour_changes, shift))
    return tuple(phrases), (Motif('motif-A', 'phrase-1', tuple(n.note_id for n in base)),)


def validate_musical_plan(plan):
    _require(type(plan) is MusicalPlan and plan.schema_version == SCHEMA_VERSION, 'PLAN_VERSION_INVALID')
    request = plan.constraints_snapshot
    _require(type(request) is PlanningRequest, 'CONSTRAINTS_SNAPSHOT_REQUIRED')
    _require(plan.metadata == {'intent': request.intent, 'time_unit': 'ticks',
                              'pitch_unit': 'midi_number', 'velocity_unit': 'midi_1_127'},
             'PLAN_METADATA_INVALID')
    _require(type(plan.ppq) is int and plan.ppq == request.grid.ppq
             and type(plan.bars) is int and plan.bars == request.section.bars
             and plan.target_role == request.section.role, 'PLAN_CONTEXT_MISMATCH')
    _require(type(plan.provenance) is dict and set(plan.provenance) == {'builder', 'input_hash', 'notes_origin'}
             and plan.provenance['builder'] == SCHEMA_VERSION
             and plan.provenance['input_hash'] == _digest(request.to_dict())
             and plan.provenance['notes_origin'] in ('agent_structured', 'deterministic_reference'),
             'PROVENANCE_INVALID')
    notes = plan.notes
    _require(type(notes) is tuple and len(notes) == request.section.bars * request.section.density
             and all(type(n) is PlannedNote for n in notes), 'NOTE_COUNT_INVALID')
    _require(len({n.note_id for n in notes}) == len(notes), 'DUPLICATE_NOTE_ID')
    _require(notes == tuple(sorted(notes, key=lambda n: (n.start, n.note_id))), 'NOTE_ORDER_INVALID')
    per_bar = [0] * request.section.bars
    intervals = []
    for note in notes:
        _require(note.start + note.length <= request.section.bars * request.grid.ticks_per_bar,
                 'NOTE_OUTSIDE_SECTION')
        per_bar[note.start // request.grid.ticks_per_bar] += 1
        chord = chord_at(request, note.start)
        _require(note.pitch in eligible_pitches(request, note.start), 'NOTE_NOT_ELIGIBLE')
        function = 'chord_tone' if note.pitch % 12 in chord.pitch_classes else 'tension'
        _require(note.chord_id == chord.chord_id and note.harmonic_function == function,
                 'NOTE_HARMONY_ANNOTATION_MISMATCH')
        for region in request.harmony.progression:
            start = (region.start_bar - 1) * request.grid.ticks_per_bar
            end = region.end_bar * request.grid.ticks_per_bar
            if note.start < end and note.start + note.length > start:
                _require(note.pitch in eligible_pitches(request, start), 'SUSTAINED_NOTE_NOT_ELIGIBLE')
        width = request.variation.motif_length * request.grid.ticks_per_bar
        if request.variation.phrase_boundary_behavior == 'stop_at_boundary':
            _require(note.start + note.length <= (note.start // width + 1) * width,
                     'NOTE_CROSSES_PHRASE_BOUNDARY')
        intervals.extend(((note.start, 1), (note.start + note.length, -1)))
    _require(all(count == request.section.density for count in per_bar), 'DENSITY_MISMATCH')
    active = 0
    peak = 0
    for _, change in sorted(intervals):
        active += change
        peak = max(peak, active)
    _require(peak <= request.voice.polyphony_limit, 'POLYPHONY_EXCEEDED')
    _require(request.voice.overlap_policy == 'allow' or peak <= 1, 'OVERLAP_FORBIDDEN')
    # 多声部需要显式voice id才能定义逐声部跳进，首版不靠排序猜声部。
    _require(peak <= 1, 'V1_MONOPHONIC_PLAN_REQUIRED')
    _require(all(abs(b.pitch - a.pitch) <= request.voice.max_leap for a, b in zip(notes, notes[1:])),
             'MAX_LEAP_EXCEEDED')
    phrases, motifs = _phrase_map(request, notes)
    _require(plan.phrase_map == phrases and plan.motif_map == motifs, 'MUSIC_EXPLANATION_MISMATCH')
    base = tuple(n for n in notes if n.note_id in motifs[0].note_ids)
    width = request.variation.motif_length * request.grid.ticks_per_bar
    budget = math.floor(request.variation.variation_strength * len(base))
    for index, phrase in enumerate(phrases[1:], 1):
        group = tuple(n for n in notes if n.note_id in phrase.note_ids)
        changed = sum((a.pitch, a.start, a.length) != (b.pitch, b.start - index * width, b.length)
                      for a, b in zip(base, group))
        _require(changed <= budget, 'VARIATION_BUDGET_EXCEEDED')
        _require(not request.variation.preserve_rhythm or phrase.rhythm_changes == 0,
                 'RHYTHM_PRESERVATION_FAILED')
        _require(not request.variation.preserve_contour or phrase.contour_changes == 0,
                 'CONTOUR_PRESERVATION_FAILED')
    return {'schema_valid': True, 'note_count': len(notes), 'notes_per_bar': per_bar,
            'peak_polyphony': peak, 'tension_note_count': sum(n.harmonic_function == 'tension' for n in notes),
            'audible_usefulness': 'NOT_EVALUATED', 'live_certification': 'NONE'}


def compile_musical_plan(request, events, *, notes_origin='agent_structured'):
    _require(type(request) is PlanningRequest and type(events) is tuple
             and all(type(event) is NoteEvent for event in events), 'STRUCTURED_EVENTS_REQUIRED')
    events = tuple(sorted(events, key=lambda e: (e.start_tick, e.pitch, e.duration, e.velocity)))
    notes = []
    for index, event in enumerate(events):
        chord = chord_at(request, event.start_tick)
        notes.append(PlannedNote(f'n{index + 1:03}', event.pitch, event.start_tick, event.duration,
            event.velocity, chord.chord_id,
            'chord_tone' if event.pitch % 12 in chord.pitch_classes else 'tension'))
    _require(bool(notes), 'NOTES_REQUIRED')
    notes = tuple(notes)
    phrases, motifs = _phrase_map(request, notes)
    plan = MusicalPlan(SCHEMA_VERSION,
        {'intent': request.intent, 'time_unit': 'ticks', 'pitch_unit': 'midi_number',
         'velocity_unit': 'midi_1_127'}, request.section.role, request.grid.ppq, request.section.bars,
        notes, phrases, motifs, request,
        {'builder': SCHEMA_VERSION, 'input_hash': _digest(request.to_dict()), 'notes_origin': notes_origin})
    validate_musical_plan(plan)
    return plan


def generate_reference_plan(request):
    """受限单声部参考求解器；偏好决定排序，硬约束无解时拒绝。"""
    _require(type(request) is PlanningRequest, 'TYPED_REQUEST_REQUIRED')
    grid, section, voice, variation = request.grid, request.section, request.voice, request.variation
    _require(grid.ticks_per_bar % section.density == 0, 'DENSITY_NOT_RESOLVABLE')
    step = grid.ticks_per_bar // section.density
    length = max(1, min(grid.ppq, step // 2))
    style = request.style_constraints
    motion = section.motion * (1 if style is None else style.melody_leap_tendency)
    tension = section.tension * (1 if style is None else style.harmony_tension_usage)
    strength = variation.variation_strength * (1 if style is None else style.motif_variation_strength)
    _require(style is None or style.rhythm_syncopation == 0 or grid.ppq % 2 == 0,
             'PROFILE_RHYTHM_NOT_RESOLVABLE')
    offbeat = (0 if style is None else min(step - length,
        round(style.rhythm_syncopation * (grid.ppq // 2))))

    def onset(phrase_index, slot):
        return (phrase_index * count + slot) * step + (offbeat if slot % 2 else 0)

    count = section.density * variation.motif_length
    base = None
    previous = None
    events = []
    for phrase_index in range(variation.repeat_count):
        # 状态包含已变化的音符数；不能为了拟合后续和弦悄悄突破变奏预算。
        states = {(previous, 0): (0, ())}
        for slot in range(count):
            tick = onset(phrase_index, slot)
            energy = section.energy_start + (section.energy_end - section.energy_start) * (
                tick / max(1, (section.bars * section.density - 1) * step))
            center = voice.preferred_center + (energy - section.energy_start) * (
                voice.max_pitch - voice.min_pitch) / 2
            target_leap = motion * voice.max_leap
            chord = chord_at(request, tick)
            next_states = {}
            for pitch in eligible_pitches(request, tick):
                for (last, changed), (cost, path) in states.items():
                    leap = 0 if last is None else abs(pitch - last)
                    if last is not None and leap > voice.max_leap:
                        continue
                    edits = changed + int(base is not None and pitch != base[slot])
                    if base is not None and edits > math.floor(strength * count):
                        continue
                    if (base is not None and variation.preserve_contour and slot > 0
                            and _sign(pitch - last) != _sign(base[slot] - base[slot - 1])):
                        continue
                    is_tension = pitch % 12 not in chord.pitch_classes
                    extra = (pitch - center) ** 2 + 3 * (leap - target_leap) ** 2 + (
                        (1 - tension) if is_tension else tension) * 12
                    candidate = (cost + extra, path + (pitch,))
                    key = (pitch, edits)
                    if key not in next_states or candidate < next_states[key]:
                        next_states[key] = candidate
            _require(bool(next_states), 'REFERENCE_SEARCH_NO_FEASIBLE_CONTINUATION')
            states = next_states
        pitches = min(states.values())[1]
        if base is None:
            base = pitches
        previous = pitches[-1]
        for slot, pitch in enumerate(pitches):
            tick = onset(phrase_index, slot)
            energy = section.energy_start + (section.energy_end - section.energy_start) * (
                tick / max(1, (section.bars * section.density - 1) * step))
            events.append(NoteEvent(tick, length, pitch, round(56 + 56 * min(1, energy))))
    return compile_musical_plan(request, tuple(events), notes_origin='deterministic_reference')
