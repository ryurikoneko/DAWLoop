from __future__ import annotations

from dawloop.note_plan import NoteEvent, NotePlan


def plan_to_mcp_notes(plan: NotePlan) -> list[dict[str, int | float]]:
    notes = []
    for event in plan.events:
        start = event.start_tick / plan.grid.ppq
        duration = event.duration / plan.grid.ppq
        if int(start * plan.grid.ppq) != event.start_tick:
            raise ValueError("音符起点不能无损映射到上游四分音符时值")
        if int(duration * plan.grid.ppq) != event.duration:
            raise ValueError("音符时长不能无损映射到上游四分音符时值")
        notes.append({
            "midi": event.pitch,
            "time": start,
            "duration": duration,
            "velocity": event.velocity / 127,
        })
    return notes


def state_to_events(state: dict, expected_ppq: int) -> tuple[NoteEvent, ...]:
    if state.get("ppq") != expected_ppq:
        raise ValueError(f"FL Studio PPQ 不匹配：预期 {expected_ppq}，实际 {state.get('ppq')}")
    raw_notes = state.get("notes")
    if not isinstance(raw_notes, list):
        raise ValueError("Piano Roll 读回没有 notes 数组")

    events = []
    for index, note in enumerate(raw_notes):
        if not isinstance(note, dict):
            raise ValueError(f"第 {index} 个读回音符格式无效")
        start = note.get("time_ticks")
        duration = note.get("length_ticks")
        pitch = note.get("midi")
        velocity = note.get("velocity")
        if type(start) is not int or type(duration) is not int:
            raise ValueError(f"第 {index} 个读回音符缺少整数 tick 字段")
        if type(pitch) is not int or isinstance(velocity, bool) or not isinstance(velocity, (int, float)):
            raise ValueError(f"第 {index} 个读回音符缺少有效音高或力度")
        normalized_velocity = round(float(velocity) * 127)
        events.append(NoteEvent(start, duration, pitch, normalized_velocity))
    return tuple(events)
