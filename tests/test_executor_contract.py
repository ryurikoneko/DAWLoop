import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dawloop.adapters.gopher_native.response import decode_script_acceptance
from dawloop.runtime import ScriptApplicationStatus, ExecutionStatus, ResponseStatus

ROOT = Path(__file__).resolve().parents[1]


class ExecutorContractTests(unittest.TestCase):
    def test_ack_is_only_source_accepted(self):
        response={'ok':True,'payload':json.dumps({'jsonrpc':'2.0','id':'1','result':{'content':[
            {'type':'text','text':'Script executed without errors'}],'isError':False}})}
        result=decode_script_acceptance(response)
        self.assertEqual(result.script_application_status,ScriptApplicationStatus.SOURCE_ACCEPTED)
        self.assertIsNone(result.value)

    def test_unknown_or_tool_error_never_confirms_effect(self):
        for payload in ('done','SCRIPT_APPLIED',json.dumps({'content':[],'isError':True})):
            with self.subTest(payload=payload):
                result=decode_script_acceptance({'ok':True,'payload':payload})
                self.assertEqual(result.script_application_status,ScriptApplicationStatus.UNKNOWN)
                self.assertNotEqual(result.status,ExecutionStatus.SUCCESS)

    def test_dispatched_timeout_remains_unknown(self):
        result=decode_script_acceptance({'ok':False,'code':'EXECUTION_TIMEOUT','dispatched':True})
        self.assertEqual(result.status,ExecutionStatus.UNKNOWN)
        self.assertEqual(result.response_status,ResponseStatus.TIMEOUT)
        self.assertEqual(result.error_code,'EXECUTION_TIMEOUT')
        self.assertEqual(result.script_application_status,ScriptApplicationStatus.UNKNOWN)

    def test_gate_requires_standard_success_and_undo(self):
        spec=importlib.util.spec_from_file_location('executor_probe',ROOT/'scripts/runtime_v2_executor_probe_live.py')
        probe=importlib.util.module_from_spec(spec)
        with patch.object(sys,'path',[str(ROOT/'scripts'),*sys.path]):
            spec.loader.exec_module(probe)
        with tempfile.TemporaryDirectory() as directory,patch.object(probe,'OUTPUT',Path(directory)):
            root=Path(directory)
            (root/'canonical_probe.py').write_bytes((ROOT/'research/piano_roll_probe/executor_canonical_v1.pyscript').read_bytes())
            (root/'standard_runner.json').write_text(json.dumps(dict(source_hash=probe.SOURCE_HASH,canonical_script_valid=False)),encoding='utf-8')
            with self.assertRaises(ValueError):
                probe.check_gate()
            (root/'gopher_intent.json').touch()
            with self.assertRaises(ValueError):
                probe.check_gate()

    @unittest.skipUnless(shutil.which('node'),'需要脚本引擎验证实际桥接')
    def test_actual_bridge_byte_lock_and_single_invocation(self):
        result=subprocess.run([shutil.which('node'),str(ROOT/'tests/executor_probe_bridge_harness.cjs'),
            str(ROOT/'src/dawloop/adapters/gopher_native/bridge.js'),
            str(ROOT/'research/piano_roll_probe/executor_canonical_v1.pyscript')],capture_output=True,text=True,encoding='utf-8',timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
