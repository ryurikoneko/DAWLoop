"""控制器自行报告构建身份；仅在临时目录模拟宿主和MIDI。"""

import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from dawloop.adapters.fl_controller_identity import (ControllerIdentityBackend,
                                                     validate_controller_build_binding)
from dawloop.controller_runtime import inspect_runtime_status, installed_controller_identity
from dawloop.setup import _controller_build_id

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_controller_runtime import load_live_controller


class BuildBindingTests(unittest.TestCase):
    def test_missing_empty_and_wrong_type_build_ids_rejected(self):
        expected = dict(controller_build_id='build',controller_session_id='session',project_generation='project')
        for value in (None,'',' ',7,False,'source-uninstalled'):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError,'UNBOUND'):
                target = dict(expected,controller_session='session',controller_build_id=value)
                validate_controller_build_binding(target,expected)

    def test_mismatch_and_old_context_rejected(self):
        expected = dict(controller_build_id='build',controller_session_id='session',project_generation='project')
        for field in expected:
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError,'MISMATCH'):
                validate_controller_build_binding(dict(expected,controller_session='session',**{field:'old'}),expected)

    def test_source_build_is_stable_and_changes_with_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.py'
            source.write_text('value = 1\n',encoding='utf-8')
            first = _controller_build_id(source)
            self.assertEqual(first,_controller_build_id(source))
            source.write_text('value = 2\n',encoding='utf-8')
            self.assertNotEqual(first,_controller_build_id(source))

    def prepare_controller(self, directory):
        module = load_live_controller(Path(directory))
        module.CONTROLLER_BUILD_ID = 'offline-source-build'
        module.channels = types.SimpleNamespace(channelCount=lambda *args:1,
            getChannelIndex=lambda index:index,getChannelName=lambda *args:'测试通道',
            isChannelSelected=lambda *args:True)
        module.plugins = None
        module._target_identity = lambda:dict(source='fl_studio_midi_scripting',
            pattern_number=1,pattern_name='测试片段',channel_index=0,channel_name='测试通道',ppq=96,
            channel_index_type='global')
        module.OnInit()
        return module

    def test_producer_reports_build_and_session_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.prepare_controller(directory)
            first = module._identity_snapshot()
            module.OnInit()
            second = module._identity_snapshot()
            self.assertEqual(first['controller_build_id'],second['controller_build_id'])
            self.assertNotEqual(first['controller_session_id'],second['controller_session_id'])
            self.assertEqual(second['controller_session'],second['controller_session_id'])
            with self.assertRaisesRegex(ValueError,'CONTEXT_MISMATCH'):
                module._validate_identity_build_request(dict(expected_controller_build_id=first['controller_build_id'],
                    controller_session_id=first['controller_session_id'],project_generation=first['project_generation']))

    def test_old_ready_evidence_rejected_after_build_change(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.prepare_controller(directory)
            before = module._identity_snapshot()
            module.CONTROLLER_BUILD_ID = 'new-source-build'
            self.assertEqual(inspect_runtime_status(module.STATUS_FILE,'new-source-build').code,
                             'CONTROLLER_RUNTIME_BUILD_MISMATCH')
            with self.assertRaisesRegex(ValueError,'CONTEXT_MISMATCH'):
                module._validate_identity_build_request(dict(expected_controller_build_id=before['controller_build_id'],
                    controller_session_id=before['controller_session_id'],project_generation=before['project_generation']))

    def test_actual_producer_handler_to_actual_reader_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.prepare_controller(directory)
            script = module.SCRIPT_DIR/'device_DAWLoopController.py'
            script.write_text('CONTROLLER_BUILD_ID = "offline-source-build"\n',encoding='utf-8')
            sends = []
            class Port:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def send(self,message):
                    command = json.loads(module.COMMAND_FILE.read_text(encoding='utf-8'))
                    sends.append(command)
                    module._handle_diagnostic_request()
            midi = types.SimpleNamespace(get_output_names=lambda:['test-port'],
                open_output=lambda *args:Port(),Message=lambda *args,**kwargs:kwargs)
            reader = ControllerIdentityBackend('test-port',settings_dir=Path(directory))
            with patch.dict(sys.modules,{'mido':midi}):
                actual = reader._read()
            self.assertEqual(actual['controller_build_id'],module.CONTROLLER_BUILD_ID)
            self.assertEqual(actual['controller_session_id'],module._SESSION_ID)
            self.assertEqual(actual['project_generation'],module._PROJECT_GENERATION)
            self.assertEqual(sends[0]['params']['expected_controller_build_id'],actual['controller_build_id'])
            self.assertNotIn('controller_build_id',sends[0]['params'])
            self.assertFalse(module.COMMAND_FILE.exists())

    def test_disk_identity_does_not_certify_loaded_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory)/'controller.py'
            script.write_text('CONTROLLER_BUILD_ID = "disk-build"\n',encoding='utf-8')
            build,disk_hash = installed_controller_identity(script)
            self.assertEqual(build,'disk-build')
            self.assertNotEqual(build,disk_hash)
            with self.assertRaisesRegex(RuntimeError,'MISMATCH'):
                validate_controller_build_binding(dict(controller_build_id='loaded-build',
                    controller_session_id='session',controller_session='session',project_generation='project'),
                    dict(controller_build_id=build,controller_session_id='session',project_generation='project'))

    def test_controller_rejects_old_project_before_identity_read(self):
        with tempfile.TemporaryDirectory() as directory:
            module = self.prepare_controller(directory)
            old = module._controller_identity_binding()
            module._PROJECT_GENERATION = 'new-project-generation'
            module.COMMAND_FILE.write_text(json.dumps(dict(action='dawloop.getIdentitySnapshot',params=dict(
                request_id='old-request',expected_controller_build_id=old['controller_build_id'],
                controller_session_id=old['controller_session_id'],project_generation=old['project_generation']))),encoding='utf-8')
            with patch.object(module,'_identity_snapshot',side_effect=AssertionError('禁止读取旧代次目标')):
                module._handle_diagnostic_request()
            response = json.loads(module.RESPONSE_FILE.read_text(encoding='utf-8'))
            self.assertFalse(response['success'])
            self.assertEqual(response['error_code'],'CONTROLLER_BUILD_CONTEXT_MISMATCH')
            self.assertNotIn('target',response)
