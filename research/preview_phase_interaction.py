"""固定四音符实验的预览阶段读像素，派发前仍使用原守卫。"""

import copy
import math

from dawloop.runtime.local_preview import LocalPreviewInteraction


class PreviewPhaseInteraction(LocalPreviewInteraction):
    def __init__(self, *args, diagnostic, transition_ms=1000, **kwargs):
        if (isinstance(transition_ms, bool) or not isinstance(transition_ms, (int, float))
                or not math.isfinite(transition_ms) or not 0 < transition_ms <= 1000):
            raise ValueError('INVALID_PREVIEW_TRANSITION_LIMIT')
        super().__init__(*args, **kwargs)
        self.diagnostic = diagnostic
        self.transition_ns = int(transition_ms*1_000_000)
        self.phase_confirmed = False
        self.preview_hwnd = None
        self.phase_rows = []

    def before_dispatch(self):
        super().before_dispatch()
        self.diagnostic.mark_dispatch(self.dispatch_at)

    def _fingerprint(self, stage):
        if stage != 'POST_DISPATCH_SAMPLE':
            return super()._fingerprint(stage)
        try:
            snapshot = self.viewport.preview_snapshot()
            current = snapshot['fingerprint']
            if current != self.baseline_fingerprint:
                self._record_invalidation(stage, 'FINGERPRINT_CHANGED', self.baseline_fingerprint, current)
                raise ValueError('VIEWPORT_INVALIDATED')
            active = snapshot['preview_confirmed'] is True
            sampled_at = self.clock()
            if not self.phase_confirmed and sampled_at-self.dispatch_at > self.transition_ns:
                raise ValueError('FIXED_PREVIEW_NOT_CONFIRMED')
            if not active and self.phase_confirmed:
                raise ValueError('FIXED_PREVIEW_NOT_CONFIRMED')
            if active:
                hwnd = (snapshot.get('preview') or {}).get('hwnd')
                if isinstance(hwnd, bool) or not isinstance(hwnd, int) or hwnd <= 0:
                    raise ValueError('PREVIEW_WINDOW_IDENTITY_UNAVAILABLE')
                if self.preview_hwnd is not None and hwnd != self.preview_hwnd:
                    raise ValueError('PREVIEW_WINDOW_REPLACED')
                self.preview_hwnd = hwnd
            self.phase_confirmed = active
            self.phase_rows.append(dict(timestamp_ns=sampled_at, preview_confirmed=active,
                preview=copy.deepcopy(snapshot.get('preview')),
                sampling_scope='FIXED_PREVIEW_VISUAL_OBSERVATION_ONLY'))
            return current
        except Exception as error:
            self.phase_confirmed = False
            self._record_invalidation(stage, getattr(error, 'reason', str(error)),
                self.baseline_fingerprint, details=getattr(error, 'details', {}))
            self._invalidate(str(error))
            raise

    def _preview_confirmation_allowed(self):
        return self.phase_confirmed

    def metrics(self):
        result = super().metrics()
        result.update(preview_phase_rows=self.phase_rows,
            preview_phase_scope='EXPERIMENTAL_FIXED_FOUR_NOTES_ONLY',
            confirmed_preview_hwnd=self.preview_hwnd,
            transition_limit_ms=self.transition_ns/1e6)
        return result
