"""只读核对恢复会话，不包含音符派发入口。"""

import asyncio
import json
from pathlib import Path
import sys
import time
import urllib.request
from urllib.parse import urlparse

from dawloop.adapters.gopher_native.transport import CDPTransport
from dawloop.adapters.gopher_native.response import decode_response
from dawloop.adapters.fl_controller_identity import ControllerIdentityBackend
from runtime_v2_latency_live import checked_catalog
from runtime_v2_throughput_live import baseline

OUTPUT=Path(__file__).resolve().parents[1]/'evidence/runtime_v2/native_host_recovery'


def write(name,value):
    with (OUTPUT/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def main():
    if (OUTPUT/'summary.json').exists():
        raise ValueError('RECOVERY_CLOSED')
    baseline()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    targets=json.loads(opener.open('http://127.0.0.1:9222/json/list',timeout=3).read().decode('utf-8'))
    write('targets.json',[dict(type=t.get('type'),title=t.get('title'),
        origin=urlparse(t.get('url','')).scheme+'://'+urlparse(t.get('url','')).netloc,
        path=urlparse(t.get('url','')).path) for t in targets])
    transport=CDPTransport(timeout=35)
    report=dict(scope='READ_ONLY_HOST_RECOVERY',write_dispatches=0)
    try:
        session=transport.connect()
        write('session.json',session)
        tools=checked_catalog(transport)
        from dawloop.adapters.gopher_native.catalog import catalog_hash
        write('catalog.json',dict(tools=tools,catalog_hash=catalog_hash(tools)))
        reads=[]
        for name in ('get_tempo','get_tempo','get_tempo','list_channel_names'):
            start=time.perf_counter_ns()
            raw=transport.invoke('call',name,{})
            end=time.perf_counter_ns()
            result=decode_response(name,raw,{})
            if result.error_code:
                raise ValueError(result.error_code)
            reads.append(dict(tool=name,total_ms=(end-start)/1e6,value=result.value,
                execution_status=result.status))
        write('reads.json',reads)
        identity=asyncio.run(ControllerIdentityBackend('FLSkill MCP IN 2').read_identity())
        write('identity.json',{key:identity.get(key) for key in ('fl_studio_version',
            'pattern_number','pattern_name','channel_index','channel_name','ppq')})
        report.update(status='CONNECTED',host_object_proven_by_catalog=True,
            catalog_count=len(tools),catalog_hash=catalog_hash(tools),
            frame_id=transport.frame_id,read_calls=len(reads),
            fl_version=identity.get('fl_studio_version'))
    except Exception as error:
        report.update(status='UNAVAILABLE',error_code=getattr(error,'code',type(error).__name__))
        raise
    finally:
        transport.close()
        report['callbacks_restored']=transport.callbacks_restored
        write('probe.json',report)
    print(json.dumps(report))


if __name__=='__main__':
    main()
