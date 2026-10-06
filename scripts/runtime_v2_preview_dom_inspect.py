"""单次只读网页快照；不安装桥接、不派发宿主工具、不导出页面全文。"""

import json
import urllib.request
import websocket
from pathlib import Path
from urllib.parse import urlparse
from dawloop.adapters.gopher_native.transport import find_target

OUTPUT = Path(__file__).resolve().parents[1] / 'evidence/runtime_v2/preview_onset/dom_at_visible_preview.json'


def main():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:9222/json/list', timeout=3) as response:
        target = find_target(json.load(response))
    address = target['webSocketDebuggerUrl']
    parsed = urlparse(address)
    if (parsed.scheme != 'ws' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
            or parsed.username or parsed.password):
        raise ValueError('UNSAFE_DEBUGGER_URL')
    socket = websocket.create_connection(address, timeout=5,
        suppress_origin=True, http_no_proxy=['localhost', '127.0.0.1', '::1'])
    counter = 0
    contexts = []
    def rpc(method, params=None):
        nonlocal counter
        counter += 1
        socket.send(json.dumps(dict(id=counter, method=method, params=params or {})))
        while True:
            value = json.loads(socket.recv())
            if value.get('method') == 'Runtime.executionContextCreated':
                contexts.append(value['params']['context'])
            if value.get('id') == counter:
                if 'error' in value:
                    raise ValueError('READ_ONLY_CDP_INSPECTION_FAILED')
                return value['result']
    try:
        frame = rpc('Page.getFrameTree')['frameTree']['frame']['id']
        rpc('Runtime.enable')
        selected = [c for c in contexts if c.get('auxData', {}).get('isDefault') and
            c.get('auxData', {}).get('frameId') == frame]
        if len(selected) != 1:
            raise ValueError('PAGE_CONTEXT_AMBIGUOUS')
        current = selected[0]
        evaluated = rpc('Runtime.evaluate', dict(contextId=current['id'], returnByValue=True,
            expression='({sample_ms:performance.now(),observer:window.__dawloopPreviewOnsetObservation?.snapshot()})'))
        if 'exceptionDetails' in evaluated:
            raise ValueError('OBSERVER_INSPECTION_FAILED')
        snapshot = rpc('DOMSnapshot.captureSnapshot', dict(computedStyles=[]))
        strings = snapshot['strings']
        report = dict(host_generation=current.get('uniqueId'), target_id=target['id'],
            clock_domain='webview_performance', sample=evaluated['result'].get('value'),
            cdp_document_count=len(snapshot['documents']),
            cdp_node_count=sum(len(d['nodes']['nodeName']) for d in snapshot['documents']),
            fixed_title_present=any('DAWLoop Native Add' in s for s in strings),
            fixed_description_present=any('Experimental add-only preview.' in s for s in strings),
            private_page_content_exported=False,
            coverage='CDP_DOM_SNAPSHOT_DOCUMENTS', native_window_covered=False)
        with OUTPUT.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(json.dumps({k: report[k] for k in ('cdp_document_count', 'cdp_node_count',
            'fixed_title_present', 'fixed_description_present')}))
    finally:
        socket.close()


if __name__ == '__main__':
    main()
