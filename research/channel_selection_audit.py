"""仅离线审计既有通道选择处理器，不连接宿主或发送控制消息。"""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

def audit():
    from dawloop.setup import default_settings_dir
    source = ROOT/'third_party/fl-studio-mcp/fl_controller/device_FLStudioMCP.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and
                 node.name in {'dispatch_command', 'handle_channels_select_one', 'handle_channels_select'}]
    class Channels:
        def __init__(self):
            self.selected = {0, 2}
            self.calls = []
        def selectOneChannel(self, index, global_index):
            self.calls.append(('selectOneChannel', index, global_index))
            self.selected = {index}
        def selectChannel(self, index, value, global_index):
            self.calls.append(('selectChannel', index, value, global_index))
            if value:
                self.selected.add(index)
            else:
                self.selected.discard(index)
        def getChannelName(self, index, global_index):
            self.calls.append(('getChannelName', index, global_index))
            return {0:'808 Kick', 1:'808 Clap'}.get(index, '未知')
    channels = Channels()
    scope = {'channels': channels}
    # 执行仓库里的实际处理器，避免另写一个模拟协议实现。
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), scope)
    result = scope['dispatch_command']('channels.selectOne', {'index':1, 'request_id':'offline-audit'})
    assert channels.selected == {1}
    assert channels.calls == [('selectOneChannel',1,True),('getChannelName',1,True)]
    assert result == {'channel_name':'808 Clap'} and 'request_id' not in result
    exclusive_calls = list(channels.calls)
    channels.selected = {0,2}; channels.calls.clear()
    scope['dispatch_command']('channels.select', {'index':1,'select':True})
    assert channels.selected == {0,1,2}
    channels.calls.clear()
    scope['dispatch_command']('channels.selectOne', {})
    assert channels.calls[0] == ('selectOneChannel',0,True)
    channels.calls.clear()
    scope['dispatch_command']('channels.selectOne', {'index':True})
    assert channels.calls[0][1] is True
    known=json.loads((ROOT/'src/dawloop/adapters/gopher_native/known_catalog.json').read_text(encoding='utf-8'))
    native=known['tools']['select_channels']
    assert native['dispatch_supported'] is False
    assert native['input_schema']['properties']['target_channels']['type']=='string'
    settings=default_settings_dir().resolve()
    assert hashlib.sha256(str(settings).encode()).hexdigest()=='850f9e7a5806244b3e7093f4f8748d9db0f980a44f60f5cf38923383ab580a82'
    installed=settings/'Hardware/DAWLoopMCP/upstream_backend.py'
    installed_tree=ast.parse(installed.read_text(encoding='utf-8'))
    installed_functions={node.name:ast.dump(node,include_attributes=False) for node in installed_tree.body
        if isinstance(node,ast.FunctionDef)}
    equal=all(installed_functions.get(node.name)==ast.dump(node,include_attributes=False) for node in functions)
    assert equal
    return dict(scope='OFFLINE_ONLY',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        installed_disk_handlers_equal=True,runtime_loaded_upstream_identity='NOT_VERIFIED',
        actual_input=dict(source='此前现场工具调用记录，原primitive文件没有坐标',
            api='sky.click',screenshot_id='screenshot-0',x=549,y=175,
            mouse_button='left_default',click_count=1,modifiers=[],
            semantic_intent='single_channel_selector',observed_effect='808 Clap采样器窗口打开'),
        gui_root_cause='名称按钮与选择器语义不同；命中名称按钮与观测一致，但缺实际输入落点日志，坐标变换原因未证明。',
        controller=dict(action='channels.selectOne',index_basis='GLOBAL_0_BASED',
            api='channels.selectOneChannel(index, True)',exclusive_calls=exclusive_calls,
            response_correlated=False,strict_parameter_validation=False,
            identity_reader_accepts_action=False,live_certified=False),
        native=dict(tool='select_channels',index_basis='VISUAL_1_BASED_OR_NAME',
            exclusive_selection_guarantee='NOT_PROVEN',dispatch_supported=False,live_certified=False),
        checks=dict(actual_dispatch_exclusive_selection=True,no_plugin_open_api=True,
            additive_select_preserves_other_selection=True,missing_index_defaults_zero=True,
            boolean_index_not_rejected=True,request_id_not_echoed=True,
            installed_disk_handler_ast_matches=True,native_dispatch_still_disabled=True),
        decision='优先既有Controller独占选择接口；先补受限参数与请求／代次绑定的导航调用入口，不放开身份读端或原生工具通用派发。',
        live_navigation_validation='FAILED_DURING_NAVIGATION',failure_stage='CHANNEL_SELECTION_PRIMITIVE',
        current_round=dict(host_started=False,navigation_transactions=0,navigation_primitives=0,
            note_dispatches=0,script_dispatches=0))

if __name__=='__main__':
    output=ROOT/'evidence/runtime_v2/target_preparation/channel_selection_audit'
    output.mkdir(exist_ok=True)
    with (output/'summary.json').open('x',encoding='utf-8') as stream:
        json.dump(audit(),stream,ensure_ascii=False,indent=2)
    print('OFFLINE_AUDIT_PASSED')
