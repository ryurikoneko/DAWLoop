"""像素候选须有音符结构及持续证据。"""

import sys
from pathlib import Path
import pytest

np = pytest.importorskip('numpy')

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
from preview_pixel_observer import PixelDetector, note_geometry


def fixture():
    blank = np.full((150,230,4),50,dtype=np.uint8)
    notes = blank.copy()
    for i in range(4):
        notes[100-i*17:110-i*17,40+i*38:57+i*38,:3] = (150,210,155)
    return blank, notes


def test_blank_fill_does_not_count_as_notes():
    blank, notes = fixture()
    detector = PixelDetector([blank]*40)
    for i in range(10):
        detector.feed(np.full_like(blank,130),i*100,i*100+20)
    assert detector.onset is None
    assert note_geometry(notes,detector.chroma_floor)[0]


def test_transient_does_not_confirm_and_interval_is_preserved():
    blank, notes = fixture()
    detector = PixelDetector([blank]*40)
    detector.feed(notes,100,110)
    detector.feed(blank,200,210)
    assert detector.onset is None
    for i in range(7):
        detector.feed(notes,300+i*100,310+i*100)
    assert detector.onset['observed_at_ns'] == 310
    assert detector.onset['confirmed_at_ns'] == 510
    assert detector.onset['last_absent_capture_start_ns'] == 200
    assert detector.stable_at == 910


def test_four_wrongly_arranged_rectangles_are_rejected():
    blank, notes = fixture()
    assert not note_geometry(np.flip(notes,axis=0),[8,8])[0]


def test_noise_threshold_is_derived_from_baseline():
    blank, notes = fixture()
    detector = PixelDetector([blank,blank+2]*20)
    assert detector.noise == 1
    assert detector.threshold > detector.noise
