import unittest
from dawloop.runtime.diagnostics import DiagnosticTrace, diagnostic_span, duration_ms, observe
from dawloop.runtime.native_write import PianoRollScriptRenderer


class DiagnosticTests(unittest.TestCase):
    def test_clock_domains_and_trace_identity(self):
        trace = DiagnosticTrace('t', 'op')
        trace.host_generation = 'host'
        observe(trace, 'a')
        observe(trace, 'b')
        first, last = trace.events
        self.assertGreaterEqual(duration_ms(first, last), 0)
        for key, value in [('clock_domain', 'webview_performance'), ('trace_id', 'other'),
                           ('host_generation', 'other'), ('timestamp_unit', 'ms')]:
            self.assertIsNone(duration_ms(first, dict(last, **{key: value})))
        self.assertIsNone(duration_ms(None, last))
        self.assertIsNone(duration_ms(last, dict(first, timestamp=last['timestamp'] - 1)))

    def test_diagnostic_failure_has_no_effect(self):
        class Broken:
            def emit(self, *args, **kwargs):
                raise OSError('诊断失败')
        with diagnostic_span(Broken(), 'test'):
            observe(Broken(), 'event')
        notes = [dict(number=84, time=3072, length=24, velocity=0.5)]
        self.assertEqual(PianoRollScriptRenderer(Broken()).render(notes),
                         PianoRollScriptRenderer().render(notes))

    def test_renderer_bytes_unchanged_and_spans_observed(self):
        notes = [dict(number=84+i, time=3072+i*48, length=24, velocity=0.5) for i in range(4)]
        trace = DiagnosticTrace('t', 'op')
        rendered = PianoRollScriptRenderer(trace).render(notes)
        self.assertEqual(rendered.sha256, 'ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75')
        self.assertEqual(rendered, PianoRollScriptRenderer().render(notes))
        self.assertEqual([e['event'] for e in trace.events], ['rendering_begin',
            'hash_validation_begin', 'hash_validation_complete', 'AST_validation_begin',
            'AST_validation_complete', 'rendering_complete'])
