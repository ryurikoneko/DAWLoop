"""外部动作必须经过新鲜复核；交接超时不能重用预算。"""

import asyncio
import json

import pytest

from dawloop.runtime.accept_exchange import AcceptActionExchange


def test_exchange_requires_fresh_check_before_ack(tmp_path):
    async def experiment():
        exchange = AcceptActionExchange(tmp_path, main_origin=[0,0], sky_window_id=10)
        context, control = {'operation_id':'fixed'}, {'control_id':'accept'}
        async def revalidate(): return dict(control=control, pending=True)
        task = asyncio.create_task(exchange.action(context, control, revalidate))
        await asyncio.sleep(0.02)
        (tmp_path/'action_answer.json').write_text(json.dumps(dict(context=context,
            control_id='accept', acknowledged=True)), encoding='utf-8')
        with pytest.raises(ValueError, match='ANSWER_UNPROVEN'): await task
        with pytest.raises(ValueError, match='BUDGET_EXHAUSTED'):
            await exchange.action(context, control, revalidate)
    asyncio.run(experiment())


def test_exchange_fresh_generation_and_ack_keep_commit_separate(tmp_path):
    async def experiment():
        exchange = AcceptActionExchange(tmp_path, main_origin=[0,0], sky_window_id=10)
        context, control = {'operation_id':'fixed'}, {'control_id':'accept'}
        async def revalidate(): return dict(control=control, pending=True)
        task = asyncio.create_task(exchange.action(context, control, revalidate))
        await asyncio.sleep(0.02)
        (tmp_path/'fresh_check_request.json').write_text(json.dumps(dict(context=context,
            control=control, generation='new-generation')), encoding='utf-8')
        while not (tmp_path/'fresh_check_answer.json').exists(): await asyncio.sleep(0.01)
        fresh = json.loads((tmp_path/'fresh_check_answer.json').read_text(encoding='utf-8'))
        assert fresh['generation'] == 'new-generation'
        (tmp_path/'action_answer.json').write_text(json.dumps(dict(context=context,
            control_id='accept', acknowledged=True, commit_status='UNKNOWN')), encoding='utf-8')
        result = await task
        assert result['commit_status'] == 'UNKNOWN'
    asyncio.run(experiment())


def test_exchange_timeout_keeps_intent_and_rejects_reuse(tmp_path):
    async def experiment():
        exchange = AcceptActionExchange(tmp_path, main_origin=[0,0], sky_window_id=10, timeout=0.01)
        async def revalidate(): raise AssertionError('没有复核请求')
        with pytest.raises(TimeoutError): await exchange.action({}, {'control_id':'accept'}, revalidate)
        assert (tmp_path/'action_request.json').exists()
        with pytest.raises(ValueError): await exchange.action({}, {'control_id':'accept'}, revalidate)
    asyncio.run(experiment())


def test_exchange_cannot_publish_fresh_answer_after_timeout(tmp_path):
    async def experiment():
        exchange = AcceptActionExchange(tmp_path, main_origin=[0,0], sky_window_id=10, timeout=0.01)
        context, control = {}, {'control_id':'accept'}
        (tmp_path/'fresh_check_request.json').write_text(json.dumps(dict(context=context,
            control=control, generation='new')), encoding='utf-8')
        async def revalidate():
            await asyncio.sleep(0.02)
            return dict(control=control, pending=True)
        with pytest.raises(TimeoutError): await exchange.action(context, control, revalidate)
        assert not (tmp_path/'fresh_check_answer.json').exists()
    asyncio.run(experiment())
