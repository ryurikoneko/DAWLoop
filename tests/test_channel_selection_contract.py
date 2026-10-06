"""模拟宿主和MIDI，执行实际控制器处理器与受限读端。"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from dawloop.adapters.fl_channel_selection import ControllerChannelSelector, ControllerPianoRollOpener
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend

sys.path.insert(0, str(Path(__file__).parent))
from test_controller_runtime import load_live_controller


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = load_live_controller(self.root)
        self.module.CONTROLLER_BUILD_ID = 'offline-build'
        self.selected = {0}
        self.calls = []
        self.commands = []
        self.global_reads = []
        self.names = ['808 Kick','808 Clap']
        def select(index, global_index):
            self.calls.append((index, global_index))
            self.selected = {index}
        def selected(*args):
            self.global_reads.append(('selected',args))
            return next(iter(self.selected))
        def is_selected(index, global_index):
            self.global_reads.append(('is_selected',(index,global_index)))
            return index in self.selected
        self.module.channels = types.SimpleNamespace(channelCount=lambda *args:2,
            getChannelIndex=lambda i:i,getChannelName=lambda i,*args:self.names[i],
            selectedChannel=selected,
            isChannelSelected=is_selected,selectOneChannel=select)
        self.module.general = types.SimpleNamespace(safeToEdit=lambda:1,
            getProjectTitle=lambda:'',getRecPPQ=lambda:96,getVersion=lambda:45)
        self.module.patterns = types.SimpleNamespace(patternNumber=lambda:1,getPatternName=lambda i:'样式 1')
        self.module.ui = types.SimpleNamespace(getVersion=lambda *args:'测试版本')
        self.module.plugins = None
        self.module.OnInit()
        (self.module.SCRIPT_DIR/'device_DAWLoopController.py').write_text('CONTROLLER_BUILD_ID = "offline-build"\n',encoding='utf-8')
        owner = self
        class Port:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def send(self,message):
                owner.commands.append(json.loads(owner.module.COMMAND_FILE.read_text(encoding='utf-8')))
                owner.module._handle_diagnostic_request()
        self.midi = types.SimpleNamespace(get_output_names=lambda:['offline-port'],
            open_output=lambda *args:Port(),Message=lambda *args,**kwargs:kwargs)

    def params(self, **changes):
        return dict(request_id='request',operation_id='operation',global_index=1,channel_name='808 Clap',
            expected_controller_build_id='offline-build',controller_session_id=self.module._SESSION_ID,
            project_generation=self.module._PROJECT_GENERATION,**changes)

    def test_actual_handler_and_reader_independent_readback(self):
        selector = ControllerChannelSelector('offline-port',settings_dir=self.root)
        with patch.dict(sys.modules,{'mido':self.midi}):
            value = asyncio.run(selector.select_once('operation',1,'808 Clap'))
            with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                asyncio.run(selector.select_once('operation',1,'808 Clap'))
        self.assertEqual(value['status'],'CHANNEL_SELECTION_CONFIRMED')
        self.assertEqual(self.calls,[(1,True)])
        self.assertEqual([x['action'] for x in self.commands],
            ['dawloop.getIdentitySnapshot','dawloop.selectOneChannelOnce','dawloop.getIdentitySnapshot'])
        self.assertEqual(len({x['params']['request_id'] for x in self.commands}),3)
        self.assertEqual(value['identity_after']['selected_channels'],[1])
        self.assertFalse(value['exact_target_binding'])
        self.assertTrue(all(args==(1,0,1) if name=='selected' else args[1] is True
                            for name,args in self.global_reads))

    def test_host_rejects_invalid_before_action(self):
        for field,value in [('global_index',True),('global_index',-1),('global_index',2),
            ('global_index','1'),('channel_name','wrong'),('project_generation','old'),
            ('controller_session_id','old'),('expected_controller_build_id','old'),('operation_id','')]:
            with self.subTest(field=field,value=value):
                params=self.params();params[field]=value
                with self.assertRaises(ValueError):self.module._select_one_channel_once(params)
                self.assertEqual(self.calls,[])
        for field in self.params():
            with self.subTest(missing=field):
                params=self.params();params.pop(field)
                with self.assertRaises(ValueError):self.module._select_one_channel_once(params)
        params=self.params();params['arbitrary_source']='forbidden'
        with self.assertRaises(ValueError):self.module._select_one_channel_once(params)

    def test_host_unknown_consumes_budget(self):
        with patch.object(self.module.channels,'selectOneChannel',side_effect=RuntimeError('unknown')):
            with self.assertRaises(RuntimeError):self.module._select_one_channel_once(self.params())
        with self.assertRaisesRegex(ValueError,'BUDGET_EXHAUSTED'):
            self.module._select_one_channel_once(self.params())
        self.assertEqual(self.calls,[])

    def test_open_uses_fixed_host_api_without_selection_or_retry(self):
        self.selected = {1}
        opened = []
        self.module.ui.openEventEditor = lambda event, mode: opened.append((event, mode))
        self.module.channels.getRecEventId = lambda index, global_index: 1000 if (index == 1 and global_index is True) else None
        opener = ControllerPianoRollOpener('offline-port',settings_dir=self.root)
        with patch.dict(sys.modules,{'mido':self.midi,'midi':types.SimpleNamespace(REC_Chan_PianoRoll=7,EE_PR=3)}):
            value = asyncio.run(opener.select_once('open-operation',1,'808 Clap'))
            with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                asyncio.run(opener.select_once('open-operation',1,'808 Clap'))
        self.assertEqual(opened,[(1007,3)])
        self.assertEqual(self.calls,[])
        self.assertEqual(value['status'],'PIANO_ROLL_OPEN_ACK_WITH_STABLE_IDENTITY')
        self.assertEqual(value['execution']['status'],'EXECUTED_UNVERIFIED')
        self.assertFalse(value['exact_target_binding'])
        self.assertEqual([x['action'] for x in self.commands],
            ['dawloop.getIdentitySnapshot','dawloop.openPianoRollOnce','dawloop.getIdentitySnapshot'])

    def test_open_rejects_wrong_target_and_unknown_consumes_budget(self):
        opened = []
        self.module.ui.openEventEditor = lambda event, mode: opened.append((event, mode))
        self.module.channels.getRecEventId = lambda index, global_index: 1000 if (index == 1 and global_index is True) else None
        with patch.dict(sys.modules,{'midi':types.SimpleNamespace(REC_Chan_PianoRoll=7,EE_PR=3)}):
            with self.assertRaisesRegex(ValueError,'NOT_UNIQUE'):
                self.module._open_piano_roll_once(self.params())
            self.assertEqual(opened,[])
            self.selected = {0,1}
            with self.assertRaisesRegex(ValueError,'NOT_UNIQUE'):
                self.module._open_piano_roll_once(self.params())
            self.selected = {1}
            with patch.object(self.module.ui,'openEventEditor',side_effect=RuntimeError('unknown')):
                with self.assertRaises(RuntimeError):self.module._open_piano_roll_once(self.params())
            with self.assertRaisesRegex(ValueError,'BUDGET_EXHAUSTED'):
                self.module._open_piano_roll_once(self.params())
        with self.assertRaises(ValueError):
            ControllerIdentityBackend('offline-port',settings_dir=self.root)._read('dawloop.openPianoRollOnce')

    def test_identity_reader_does_not_allow_selection(self):
        with self.assertRaises(ValueError):
            ControllerIdentityBackend('offline-port',settings_dir=self.root)._read('dawloop.selectOneChannelOnce')

    def test_readback_mismatch_stops_without_second_action(self):
        for kind in ('multi','wrong','pattern','project'):
            with self.subTest(kind=kind):
                selector=ControllerChannelSelector('offline-port',settings_dir=self.root)
                before=dict(channel_index=0,channel_name='808 Kick',selected_channels=[0],
                    channel_index_type='global',pattern_number=1,pattern_name='样式 1',ppq=96,
                    source='fl_studio_midi_scripting',controller_session='s',controller_session_id='s',
                    controller_build_id='b',project_generation='p',project_loading=False,
                    observed_at='2026-10-03T08:00:00+00:00',
                    visible_channels=[dict(global_index=1,name='808 Clap')])
                after=dict(before,channel_index=1,channel_name='808 Clap',selected_channels=[1])
                if kind=='multi':after['selected_channels']=[0,1]
                if kind=='wrong':after['channel_index']=0
                if kind=='pattern':after['pattern_number']=2
                if kind=='project':after['project_generation']='new'
                with patch.object(selector,'_read',side_effect=[before,{'status':'EXECUTED_UNVERIFIED'},after]) as read:
                    with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_FAILED'):
                        asyncio.run(selector.select_once('op',1,'808 Clap'))
                    self.assertEqual(read.call_count,3)
                    with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                        asyncio.run(selector.select_once('op',1,'808 Clap'))

    def test_timeout_and_invalid_ack_never_retry(self):
        for fault in ('timeout','wrong_operation','wrong_generation'):
            with self.subTest(fault=fault):
                selector=ControllerChannelSelector('offline-port',settings_dir=self.root,timeout=.02)
                original=self.midi.open_output
                owner=self
                class BadPort:
                    def __enter__(self):return self
                    def __exit__(self,*args):pass
                    def send(self,message):
                        command=json.loads(owner.module.COMMAND_FILE.read_text(encoding='utf-8'))
                        owner.commands.append(command)
                        owner.module._handle_diagnostic_request()
                        if command['action']=='dawloop.selectOneChannelOnce':
                            data=json.loads(owner.module.RESPONSE_FILE.read_text(encoding='utf-8'))
                            if fault=='timeout':data['request_id']='late-old-request'
                            elif fault=='wrong_operation':data['selection']['operation_id']='old'
                            else:data['selection']['project_generation']='old'
                            owner.module.RESPONSE_FILE.write_text(json.dumps(data),encoding='utf-8')
                self.midi.open_output=lambda *args:BadPort()
                start=len(self.calls)
                with patch.dict(sys.modules,{'mido':self.midi}):
                    with self.assertRaises((RuntimeError,TimeoutError)):
                        asyncio.run(selector.select_once('op-'+fault,1,'808 Clap'))
                    self.assertTrue(selector.poisoned)
                    with self.assertRaisesRegex(RuntimeError,'BUDGET_EXHAUSTED'):
                        asyncio.run(selector.select_once('op-'+fault,1,'808 Clap'))
                self.assertEqual(len(self.calls)-start,1)
                self.module.COMMAND_FILE.unlink(missing_ok=True)
                self.midi.open_output=original


if __name__=='__main__':unittest.main()
