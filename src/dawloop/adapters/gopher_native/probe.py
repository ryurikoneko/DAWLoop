from __future__ import annotations

from dawloop.runtime import BackendError, BackendRouter, DataStatus, ExecutionStatus, OperationPlan, ToolSafetyClassification
from dawloop.runtime.benchmark import PerformanceTrace

from .backend import GopherNativeBackend


async def native_probe(endpoint, timeout=35.0, repeats=3, plugin_target=None, slot_number=-1, param_identifier=None):
    if not 1 <= repeats <= 100:
        raise ValueError("重复次数必须为1到100")
    trace = PerformanceTrace("LIVE_READ_ONLY")
    backend = GopherNativeBackend(endpoint, timeout, trace=trace)
    report = {"status": "NOT_RUN", "fl_version": None, "project_identity": None, "reads": []}
    try:
        with trace.phase("backend_connect"):
            session = await backend.connect()
        router = BackendRouter([backend])
        with trace.phase("discovery"):
            await router.discover()
            if backend.name in router.discovery_errors:
                raise BackendError(router.discovery_errors[backend.name])
        report.update(tool_count=len(backend.capabilities), catalog_hash=backend.catalog_digest,
                      allowed_operations=[item.name for item in backend.capabilities
                                          if item.safety == ToolSafetyClassification.READ_ONLY and item.dispatch_supported])
        names = ["transport.tempo.read", "channel.list", "system.session_context"]
        if plugin_target is not None:
            names.append("plugin.parameter.read" if param_identifier else "plugin.parameter.list")
        for _ in range(repeats):
            for name in names:
                target = {"session": session["session"]}
                args = {}
                if name.startswith("plugin."):
                    args = {"target": plugin_target, "slot_number": slot_number}
                    target.update(plugin_target=plugin_target, slot_number=slot_number)
                    if param_identifier:
                        args["param_identifier"] = param_identifier
                plan = OperationPlan(name, target, args)
                result = await router.execute(plan)
                # 宿主输出可能包含工程名及本地路径，诊断只保存状态和类型。
                report["reads"].append({"operation": name, "execution_status": result.execution_status,
                                        "data_status": result.data_status, "response_status": result.response_status,
                                        "error_code": result.error_code, "value_type": type(result.value).__name__})
                if name == "system.session_context" and isinstance(result.value, dict):
                    version = result.value.get("fl_studio_version") or result.value.get("fl_version")
                    if isinstance(version, (str, int)):
                        report["fl_version"] = version
                if result.execution_status in {ExecutionStatus.UNKNOWN, ExecutionStatus.FAILED}:
                    report["status"] = "STOPPED"
                    return report
        report["status"] = "READ_ONLY_TESTED" if report["reads"] and all(
            item["execution_status"] == ExecutionStatus.SUCCESS and item['data_status'] == DataStatus.VALID
            for item in report["reads"]
        ) else "PARTIAL"
        report["interference"] = backend.observations
        report["correlation"] = "UNCONFIRMED"
        report['backend_state'] = backend.backend_state
        report['capability_health'] = {name:health.to_dict() for name,health in backend.capability_health.items()}
        return report
    except BackendError as error:
        report.update(status="UNAVAILABLE", error_code=error.code)
        return report
    except (ValueError, TypeError):
        report.update(status="STOPPED", error_code="INVALID_NATIVE_DATA")
        return report
    finally:
        await backend.close()
        report["callbacks_restored"] = backend.transport.callbacks_restored
        report["performance"] = trace.report(report["status"], catalog_digest=backend.catalog_digest,
                                              host_version=report["fl_version"])
