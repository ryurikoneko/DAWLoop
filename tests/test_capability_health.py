import asyncio
import copy
import unittest

from dawloop.adapters.gopher_native.backend import GopherNativeBackend
from dawloop.adapters.gopher_native.catalog import known_catalog
from dawloop.runtime import BackendRouter, OperationPlan, BackendState, certify_read
from test_gopher_native import FakeTransport


class CapabilityHealthTests(unittest.TestCase):
    def backend(self):
        transport = FakeTransport()
        transport.tools = [{'name':n,'description':v['description'],'inputSchema':v['input_schema']}
                           for n,v in known_catalog()['tools'].items()]
        return GopherNativeBackend(transport=transport, fl_version='test-version')

    def test_quarantined_tool_does_not_disable_other_reads(self):
        async def check():
            b=self.backend()
            r=BackendRouter([b])
            await r.discover()
            self.assertEqual(b.backend_state, BackendState.DEGRADED)
            result=await r.execute(OperationPlan('system.session_context', {'session':'doc-1'}))
            self.assertEqual(result.error_code,'CAPABILITY_QUARANTINED')
            tempo=await r.execute(OperationPlan('transport.tempo.read', {'session':'doc-1'}))
            self.assertEqual(tempo.data_status,'VALID')
            self.assertFalse(any(c[0]=='call' and c[1]=='get_session_context' for c in b.transport.calls))
        asyncio.run(check())

    def test_certification_is_per_contract_and_version(self):
        async def check():
            b=self.backend()
            r=BackendRouter([b],require_live_certified=True)
            await r.discover()
            plan=OperationPlan('transport.tempo.read', {'session':'doc-1'})
            self.assertEqual((await r.execute(plan)).error_code,'LIVE_CERTIFICATION_REQUIRED')
            cap=next(c for c in b.capabilities if c.name==plan.operation)
            row={'tool':'get_tempo','execution_status':'SUCCESS','data_status':'VALID','response_status':'SUCCESS','total_ms':3}
            h=certify_read(cap,[row],fl_version='test-version',evidence='test-live-record',scope={'project':'disposable'})
            b.apply_certification(cap.name,h)
            self.assertEqual((await r.execute(plan)).data_status,'VALID')
            h.fl_version='other-version'
            with self.assertRaises(ValueError):
                b.apply_certification(cap.name,h)
            with self.assertRaises(ValueError):
                certify_read(cap,[dict(row,data_status='INVALID')],fl_version='test-version',evidence='x',scope={'x':1})
            next(t for t in b.transport.tools if t['name']=='get_tempo')['description']='changed'
            await r.discover()
            self.assertNotIn(cap.name,b.capability_health)
        asyncio.run(check())

    def test_report_cannot_partially_install_mismatched_certificates(self):
        async def check():
            b=self.backend()
            await b.discover()
            certificates={}
            for cap in b.capabilities:
                if cap.name in {'transport.tempo.read','channel.list'}:
                    row={'tool':cap.raw_tool['name'],'execution_status':'SUCCESS','data_status':'VALID','response_status':'SUCCESS','total_ms':3}
                    certificates[cap.name]=certify_read(cap,[row],fl_version='test-version',evidence='test-live-record',scope={'test':True}).to_dict()
            report={'catalog_hash':b.catalog_digest,'capabilities':certificates}
            invalid=copy.deepcopy(report)
            invalid['capabilities']['transport.tempo.read']['schema_hash']='changed'
            before=copy.deepcopy(b.capability_health)
            with self.assertRaises(ValueError):
                b.apply_certification_report(invalid)
            self.assertEqual(b.capability_health,before)
            b.apply_certification_report(report)
            self.assertEqual(b.capability_health['channel.list'].state,'LIVE_CERTIFIED')
        asyncio.run(check())
