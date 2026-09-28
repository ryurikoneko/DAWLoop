# Portions adapted from whale-music-pipeline/scripts/score/sf2.py
# Original code: MIT License, Copyright (c) 2026 whale-music-pipeline contributors.
# See THIRD_PARTY_NOTICES.md.

# -*- coding: utf-8 -*-
"""从第三方实现改编的 SoundFont(sf2) 采样播放引擎。

This module parses a subset of the SF2 RIFF structure and renders notes from
sample zones using numpy. It is intentionally kept outside DAWProof Core and is
available through the optional Production Pipeline dependency set.
"""
import struct

try:
    import numpy as np
except ImportError as error:
    raise ImportError(
        "Optional dependency 'numpy' is required for Production SoundFont utilities. "
        'Install with: pip install "dawproof[production]"'
    ) from error


def _s16(v):
    return v - 65536 if v > 32767 else v


def _tc2s(tc):
    tc = max(-12000, min(8000, tc))
    return 2.0 ** (tc / 1200.0)


class Sf2:
    def __init__(self, path):
        with open(path, "rb") as handle:
            raw = handle.read()
        if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"sfbk":
            raise ValueError("not an SF2 file: %s" % path)
        riff_end = struct.unpack_from("<I", raw, 4)[0] + 8
        if riff_end > len(raw):
            raise ValueError("truncated SF2 RIFF container")
        ch = {}
        p = 12
        while p < riff_end:
            if p + 8 > riff_end:
                raise ValueError("truncated SF2 chunk header")
            cid = raw[p:p + 4]
            ln = struct.unpack_from("<I", raw, p + 4)[0]
            data_start = p + 8
            data_end = data_start + ln
            if data_end > riff_end:
                raise ValueError("truncated SF2 chunk data")
            data = raw[data_start:data_end]
            p += 8 + ln + (ln & 1)
            if p > riff_end:
                raise ValueError("truncated SF2 chunk padding")
            if cid == b"LIST":
                if len(data) < 4:
                    raise ValueError("invalid SF2 LIST chunk")
                typ = data[:4].decode("latin1")
                q = 4
                while q < len(data):
                    if q + 8 > len(data):
                        raise ValueError("truncated SF2 subchunk header")
                    sid = data[q:q + 4].decode("latin1")
                    sl = struct.unpack_from("<I", data, q + 4)[0]
                    sub_end = q + 8 + sl
                    if sub_end > len(data):
                        raise ValueError("truncated SF2 subchunk data")
                    ch[(typ, sid)] = data[q + 8:sub_end]
                    q += 8 + sl + (sl & 1)
                    if q > len(data):
                        raise ValueError("truncated SF2 subchunk padding")
            else:
                ch[cid.decode("latin1")] = data

        required = {("sdta", "smpl"), ("pdta", "phdr"), ("pdta", "pbag"), ("pdta", "pgen"),
                    ("pdta", "inst"), ("pdta", "ibag"), ("pdta", "igen"), ("pdta", "shdr")}
        missing = required - ch.keys()
        if missing:
            raise ValueError("SF2 is missing required chunks: " + ", ".join(f"{a}/{b}" for a, b in sorted(missing)))
        if len(ch[("sdta", "smpl")]) % 2:
            raise ValueError("invalid SF2 sample data length")
        self.pcm = np.frombuffer(ch[("sdta", "smpl")], dtype="<i2").astype(np.float32) / 32768.0
        try:
            self.phdr = self._rec(ch[("pdta", "phdr")], 38, "<20sHHHIII")
            self.pbag = self._rec(ch[("pdta", "pbag")], 4, "<HH")
            self.pgen = self._rec(ch[("pdta", "pgen")], 4, "<HH")
            self.inst = self._rec(ch[("pdta", "inst")], 22, "<20sH")
            self.ibag = self._rec(ch[("pdta", "ibag")], 4, "<HH")
            self.igen = self._rec(ch[("pdta", "igen")], 4, "<HH")
            self.shdr = self._rec(ch[("pdta", "shdr")], 46, "<20sIIIIIBbHH")
        except struct.error as error:
            raise ValueError("invalid SF2 table data") from error

        self.presets = [
            (
                i,
                self.phdr[i][0].split(b"\0")[0].decode("latin1", "ignore"),
                self.phdr[i][2],
                self.phdr[i][1],
            )
            for i in range(len(self.phdr) - 1)
        ]
        self.preset_i = None
        self._voices = {}

    @staticmethod
    def _rec(b, size, fmt):
        if len(b) % size:
            raise ValueError("invalid SF2 table length")
        return [struct.unpack_from(fmt, b, i * size) for i in range(len(b) // size)]

    @staticmethod
    def _zones(gen, bag, b0, b1):
        out = []
        for j in range(b0, b1):
            g0 = bag[j][0]
            g1 = bag[j + 1][0]
            g = {}
            for i in range(g0, g1):
                op, amt = gen[i]
                g[op] = amt
            out.append(g)
        return out

    @staticmethod
    def _match(g, key, vel):
        kr = g.get(43)
        if kr is not None and not ((kr & 0x7F) <= key <= ((kr >> 8) & 0x7F)):
            return False
        vr = g.get(44)
        if vr is not None and not ((vr & 0x7F) <= vel <= ((vr >> 8) & 0x7F)):
            return False
        return True

    def find_preset(self, want="string"):
        wanted = (want or "").lower()
        if wanted:
            for i, name, bank, prog in self.presets:
                if wanted in name.lower():
                    return i
        return 0 if self.presets else None

    def set_preset(self, idx):
        self.preset_i = idx
        self._voices = {}
        pz = self._zones(self.pgen, self.pbag, self.phdr[idx][3], self.phdr[idx + 1][3])
        for key in range(128):
            for vel in (32, 64, 96, 127):
                self._voices[(key, vel)] = self._resolve(pz, key, vel)

    def _resolve(self, pz, key, vel):
        for pg in pz:
            if not self._match(pg, key, vel):
                continue
            ii = pg.get(41)
            if ii is None or ii >= len(self.inst) - 1:
                continue
            zones = self._zones(self.igen, self.ibag, self.inst[ii][1], self.inst[ii + 1][1])
            for ig in zones:
                if not self._match(ig, key, vel):
                    continue
                sid = ig.get(53)
                if sid is None or sid >= len(self.shdr) - 1:
                    continue
                g = dict(ig)
                for op in (48, 8, 51, 52, 56):
                    if op in pg:
                        g[op] = g.get(op, 0) + _s16(pg[op])
                return self.shdr[sid], g
        return None

    def sample(self, key, vel, dur, sample_rate):
        """Render one note to a float waveform, or return None if no zone matches."""
        bucket = min((32, 64, 96, 127), key=lambda b: abs(b - vel))
        voice = self._voices.get((key, bucket))
        if voice is None:
            return None
        sh, g = voice
        start, end, loop_start, loop_end, source_rate, orig, corr = (
            sh[1], sh[2], sh[3], sh[4], sh[5], sh[6], sh[7]
        )
        source = self.pcm[start:end]
        if len(source) < 16:
            return None

        root = g.get(58, orig)
        cents = (
            (key - root) * g.get(56, 100)
            + _s16(g.get(51, 0)) * 100
            + _s16(g.get(52, 0))
            - corr
        )
        ratio = (2.0 ** (cents / 1200.0)) * (source_rate / float(sample_rate))
        if ratio <= 0:
            return None

        attack = _tc2s(_s16(g.get(35, -12000)))
        hold = _tc2s(_s16(g.get(36, -12000)))
        decay = _tc2s(_s16(g.get(37, -12000)))
        sustain = 10.0 ** (-g.get(38, 0) / 200.0)
        release = max(_tc2s(_s16(g.get(39, -12000))), 0.09)
        attenuation = 10.0 ** (-g.get(48, 0) / 200.0)

        dur = max(dur, 0.03)
        count = int((dur + release + 0.10) * sample_rate) + 2
        if count < 16:
            return None

        looping = False
        l0 = l1 = 0
        if (g.get(54, 0) & 3) in (1, 3):
            l0 = max(loop_start - start, 0)
            l1 = min(loop_end - start, len(source))
            looping = (l1 - l0) > 8

        idx = np.arange(count, dtype=np.float64) * ratio
        if looping:
            idx = np.where(idx < l1, idx, l0 + np.mod(idx - l0, l1 - l0))
        i0 = np.floor(idx).astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        np.clip(i0, 0, len(source) - 2, out=i0)
        waveform = source[i0] * (1.0 - frac) + source[i0 + 1] * frac

        timeline = np.arange(count, dtype=np.float32) / sample_rate
        a = min(attack, max(dur * 0.4, 0.002))
        h = min(hold, max(dur * 0.2, 0.0))
        d = min(decay, max(dur * 0.4, 0.002))
        note_off = max(dur, a + h + d + 1e-3)
        xs = np.array([0.0, a, a + h, a + h + d, note_off, note_off + release], dtype=np.float32)
        ys = np.array([0.0, 1.0, 1.0, sustain, sustain, 0.0], dtype=np.float32)
        envelope = np.interp(timeline, xs, ys)

        core = (
            source[l0:l1]
            if looping
            else source[len(source) // 3:max(len(source) // 3 + 1, int(len(source) * 0.8))]
        )
        source_rms = float(np.sqrt((core.astype(np.float32) ** 2).mean())) or 1e-4
        velocity_gain = (vel / 127.0) ** 1.6
        amp = float(np.clip(0.10 / (source_rms * attenuation * velocity_gain), 0.03, 12.0))

        return waveform * (envelope * velocity_gain * amp * attenuation).astype(np.float32)

    def info(self):
        return "samples=%d presets=%d" % (len(self.shdr) - 1, len(self.presets))
