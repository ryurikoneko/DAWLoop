(function () {
  'use strict';
  var key = '__dawloopReadonlyBridgeV1';
  var prior = window[key];
  if (prior && prior.unacknowledged) prior.poisoned = true;
  if (prior && prior.attached) return {epoch: prior.epoch, poisoned: prior.poisoned};
  var state = prior || {epoch: crypto.randomUUID(), poisoned: false, interference: 0, unacknowledged: false};
  var attachedEpoch = state.epoch;
  var existed = !!window.flHelper;
  var helper = window.flHelper || (window.flHelper = {});
  var oldRun = helper.onRunJson;
  var oldCatalog = helper.onMCPTools;
  var active = null;
  state.attached = true;

  state.configureDiagnostics = function (traceId, operationId, generation) {
    if (active) return false;
    state.diagnostics = {trace_id: traceId, operation_id: operationId,
      host_generation: generation, events: []};
    return true;
  };
  function diagnostic(event, metadata) {
    // 仅追加内存事件，失败不得改变原调用及回调处理。
    try {
      var d = state.diagnostics;
      if (d && d.events.length < 1000) d.events.push({trace_id: d.trace_id,
        operation_id: d.operation_id, host_generation: d.host_generation,
        layer: 'bridge', event: event, clock_domain: 'webview_performance',
        timestamp: performance.now(), timestamp_unit: 'ms', metadata: metadata || {}});
    } catch (_) {}
  }

  function host() {
    if (typeof script_handler === 'object' && script_handler) return script_handler;
    if (window.chrome && window.chrome.webview && window.chrome.webview.hostObjects)
      return window.chrome.webview.hostObjects.script_handler;
    throw new Error('HOST_UNAVAILABLE');
  }
  function forward(fn, value) {
    if (typeof fn === 'function') {
      try { fn.call(helper, value); } catch (_) { state.interference += 1; }
    }
  }
  function finish(kind, payload) {
    diagnostic('host_callback_received', {kind: kind});
    // 本地代次只能隔离已知旧处理器，不能替代宿主响应关联编号。
    if (window[key] !== state || state.epoch !== attachedEpoch) { state.interference += 1; return; }
    if (!active || active.kind !== kind) { state.interference += 1; return; }
    var pending = active;
    active = null;
    clearTimeout(pending.timer);
    pending.resolve({ok: true, payload: payload, interference: state.interference});
    diagnostic('bridge_promise_resolved');
  }
  function onRun(payload) { finish('call', payload); forward(oldRun, payload); }
  function onCatalog(payload) { finish('catalog', payload); forward(oldCatalog, payload); }
  helper.onRunJson = onRun;
  helper.onMCPTools = onCatalog;
  state.invoke = function (kind, tool, args, timeout) {
    var allowed = ['get_tempo', 'list_channel_names', 'get_session_context',
      'get_plugin_parameter_list', 'get_plugin_parameter_value'];
    if (kind !== 'catalog' && (kind !== 'call' || allowed.indexOf(tool) === -1))
      return Promise.resolve({ok: false, code: 'READ_ONLY_BACKEND'});
    return startCall(kind, tool, args, timeout);
  };
  state.invokeFixedCountProbe = function (probeId, hash, source, timeout) {
    var fixed = "import flpianoroll as flp\n\n\ndef apply(form):\n    return {'ppq': flp.score.PPQ, 'note_count': flp.score.noteCount}\n";
    if (probeId !== 'piano_roll_count_return_v1' ||
        hash !== '7a549a8b2ebb2bb309b7065986e987c5a4dd734f303c3a7750d15af150798fba' || source !== fixed)
      return Promise.resolve({ok: false, code: 'FIXED_PROBE_MISMATCH'});
    // 仅开放字节锁定的研究探针，普通工具入口继续拒绝任意脚本。
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: 'INVALID_PROBE_TIMEOUT'});
    return startCall('call', 'run_piano_roll_script', {source: fixed}, timeout);
  };
  state.invokeFixedScalarProbe = function (probeId, hash, source, timeout) {
    var fixed = "import flpianoroll as flp\n\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Scalar Return Probe\", \"Read-only return contract research.\")\n\n\ndef apply(form):\n    count = flp.score.noteCount\n    return \"DAWLOOP_RETURN_V1|\" + str(count)\n";
    if (probeId !== 'SCALAR_RETURN_PROBE_V1' ||
        hash !== '48ecc28054787affb34d377daa85e2c804b4a60c4c950f98a73329ac0eaa09c2' || source !== fixed)
      return Promise.resolve({ok: false, code: 'FIXED_PROBE_MISMATCH'});
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: 'INVALID_PROBE_TIMEOUT'});
    if (state.executorProbeAttempted)
      return Promise.resolve({ok: false, code: 'PROBE_BUDGET_EXHAUSTED'});
    if (state.poisoned || active || state.unacknowledged)
      return Promise.resolve({ok: false, code: 'PROBE_SESSION_NOT_READY'});
    // 接受、取消或未知结果均已消耗同一会话的实验预算。
    state.executorProbeAttempted = true;
    return startCall('call', 'run_piano_roll_script', {source: fixed}, timeout);
  };
  state.invokeFixedErrorProbe = function (probeId, hash, source, timeout) {
    var fixed = "import flpianoroll as flp\n\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Error Return Probe\", \"Exception propagation diagnostic.\")\n\n\ndef apply(form):\n    count = flp.score.noteCount\n    raise Exception(\"DAWLOOP_ERROR_V1|COUNT=\" + str(count))\n";
    if (probeId !== 'ERROR_RETURN_PROBE_V1' ||
        hash !== 'e03610c0c9551d31086e8f7b5a07d0b57821563d4851e9d9ac9fefb1ae2d1a1e' || source !== fixed)
      return Promise.resolve({ok: false, code: 'FIXED_PROBE_MISMATCH'});
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: 'INVALID_PROBE_TIMEOUT'});
    if (state.executorProbeAttempted)
      return Promise.resolve({ok: false, code: 'PROBE_BUDGET_EXHAUSTED'});
    if (state.poisoned || active || state.unacknowledged)
      return Promise.resolve({ok: false, code: 'PROBE_SESSION_NOT_READY'});
    // 异常结果也消耗实验预算，不因未返回诊断数据而重新派发。
    state.executorProbeAttempted = true;
    return startCall('call', 'run_piano_roll_script', {source: fixed}, timeout);
  };
  state.invokeFixedTargetProbe = function (probeId, hash, source, ordinal, timeout) {
    var fixed = "import flpianoroll as flp\n\ndef apply(form):\n    note = flp.Note()\n    note.number = 120\n    note.time = 0\n    note.length = flp.score.PPQ\n    note.velocity = 0.5\n    flp.score.addNote(note)\n";
    if (probeId !== 'target_semantics_v1' ||
        hash !== 'cb2b35af5004a20f78da6d12fb67890edf45cabc8516372953c12cbefc6bce4b' || source !== fixed)
      return Promise.resolve({ok: false, code: 'FIXED_PROBE_MISMATCH'});
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: 'INVALID_PROBE_TIMEOUT'});
    // 页面内预算保留于重连；跨页面及进程预算由研究客户端持久意图约束。
    var used = state.targetProbeAttempts || 0;
    if (ordinal !== used + 1 || ordinal > 2)
      return Promise.resolve({ok: false, code: 'PROBE_BUDGET_EXHAUSTED'});
    if (state.poisoned || active || state.unacknowledged)
      return Promise.resolve({ok: false, code: 'PROBE_SESSION_NOT_READY'});
    state.targetProbeAttempts = ordinal;
    return startCall('call', 'run_piano_roll_script', {source: fixed}, timeout);
  };
  state.invokeFixedExecutorProbe = function (probeId, hash, source, timeout) {
    var fixed = "import flpianoroll as flp\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\n        \"DAWLoop Target Probe\",\n        \"Adds one disposable marker note.\"\n    )\n\ndef apply(form: flp.ScriptDialog) -> None:\n    note = flp.Note()\n    note.number = 120\n    note.time = 0\n    note.length = flp.score.PPQ\n    note.velocity = 0.5\n    flp.score.addNote(note)\n";
    if (probeId !== 'executor_canonical_v1' || hash !== 'bbf82b82bc172858d09ac9a3fd95818e3069d30a10ce152c1db1591ba6753570' || source !== fixed)
      return Promise.resolve({ok: false, code: 'FIXED_PROBE_MISMATCH'});
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: 'INVALID_PROBE_TIMEOUT'});
    if (state.executorProbeAttempted)
      return Promise.resolve({ok: false, code: 'PROBE_BUDGET_EXHAUSTED'});
    if (state.poisoned || active || state.unacknowledged)
      return Promise.resolve({ok: false, code: 'PROBE_SESSION_NOT_READY'});
    state.executorProbeAttempted = true;
    return startCall('call', 'run_piano_roll_script', {source: fixed}, timeout);
  };
  state.invokeFixedThroughputProbe = function (count, hash, source, timeout) {
    var fixed = {"1": {"hash": "334379a79bd53af0751e5e0474ecbf4bb069b9fdc5e1f2ef9e4149af202e8857", "source": "import flpianoroll as flp\n\nNOTE_COUNT = 1\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Throughput Probe\", \"Adds a fixed disposable grid.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    ppq = flp.score.PPQ\n    for index in range(NOTE_COUNT):\n        note = flp.Note()\n        note.number = 84 + index // 16\n        note.time = 32 * ppq + (index % 16) * (ppq // 2)\n        note.length = ppq // 4\n        note.velocity = 0.5\n        flp.score.addNote(note)\n"}, "4": {"hash": "cb5c5bacbd0af66353c7317acc5f435264bd8267317ca66a7449b1327fa7f6ab", "source": "import flpianoroll as flp\n\nNOTE_COUNT = 4\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Throughput Probe\", \"Adds a fixed disposable grid.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    ppq = flp.score.PPQ\n    for index in range(NOTE_COUNT):\n        note = flp.Note()\n        note.number = 84 + index // 16\n        note.time = 32 * ppq + (index % 16) * (ppq // 2)\n        note.length = ppq // 4\n        note.velocity = 0.5\n        flp.score.addNote(note)\n"}, "32": {"hash": "2ae1da0104fb61ac5863e08ed05d3692f133b02c239cc9be3eda51b29d00beec", "source": "import flpianoroll as flp\n\nNOTE_COUNT = 32\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Throughput Probe\", \"Adds a fixed disposable grid.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    ppq = flp.score.PPQ\n    for index in range(NOTE_COUNT):\n        note = flp.Note()\n        note.number = 84 + index // 16\n        note.time = 32 * ppq + (index % 16) * (ppq // 2)\n        note.length = ppq // 4\n        note.velocity = 0.5\n        flp.score.addNote(note)\n"}, "64": {"hash": "c5fbd46c80b817e581ab0a793a1fa38d29b245d86beb863f866410eedc9028e4", "source": "import flpianoroll as flp\n\nNOTE_COUNT = 64\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Throughput Probe\", \"Adds a fixed disposable grid.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    ppq = flp.score.PPQ\n    for index in range(NOTE_COUNT):\n        note = flp.Note()\n        note.number = 84 + index // 16\n        note.time = 32 * ppq + (index % 16) * (ppq // 2)\n        note.length = ppq // 4\n        note.velocity = 0.5\n        flp.score.addNote(note)\n"}, "128": {"hash": "36eaddd15a584ae346d34ed8cb78a9a493dd526612236fb6facfd7d15721fe38", "source": "import flpianoroll as flp\n\nNOTE_COUNT = 128\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Throughput Probe\", \"Adds a fixed disposable grid.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    ppq = flp.score.PPQ\n    for index in range(NOTE_COUNT):\n        note = flp.Note()\n        note.number = 84 + index // 16\n        note.time = 32 * ppq + (index % 16) * (ppq // 2)\n        note.length = ppq // 4\n        note.velocity = 0.5\n        flp.score.addNote(note)\n"}};
    var item = fixed[count];
    if (!Number.isInteger(count) || !item || hash !== item.hash || source !== item.source)
      return Promise.resolve({ok: false, code: "FIXED_PROBE_MISMATCH"});
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return Promise.resolve({ok: false, code: "INVALID_PROBE_TIMEOUT"});
    if (state.executorProbeAttempted)
      return Promise.resolve({ok: false, code: "PROBE_BUDGET_EXHAUSTED"});
    if (state.poisoned || active || state.unacknowledged)
      return Promise.resolve({ok: false, code: "PROBE_SESSION_NOT_READY"});
    state.executorProbeAttempted = true;
    return startCall("call", "run_piano_roll_script", {source: item.source}, timeout);
  };
  state.invokeBatchAdd = async function (operationId, rows, hash, source, epoch, timeout) {
    if (epoch !== state.epoch || typeof operationId !== 'string' ||
        !/^[A-Za-z0-9_-]{1,64}$/.test(operationId))
      return {ok: false, code: 'INVALID_BATCH_OPERATION'};
    if (!Array.isArray(rows) || rows.length < 1 || rows.length > 128)
      return {ok: false, code: 'CAPABILITY_LIMIT_EXCEEDED'};
    for (var row of rows) {
      if (!Array.isArray(row) || row.length !== 4 ||
          !row.every(Number.isInteger) || row[0] < 0 || row[0] > 127 ||
          row[1] < 0 || row[2] < 1 || row[1] + row[2] > 2147483647 ||
          row[3] < 0 || row[3] > 1000000)
        return {ok: false, code: 'INVALID_BATCH_NOTE'};
    }
    var canonical = "import flpianoroll as flp\n\nNOTES = " + JSON.stringify(rows) + "\n\ndef createDialog() -> flp.ScriptDialog:\n    return flp.ScriptDialog(\"DAWLoop Native Add\", \"Experimental add-only preview.\")\n\ndef apply(form: flp.ScriptDialog) -> None:\n    for number, tick, length, velocity in NOTES:\n        note = flp.Note()\n        note.number = number\n        note.time = tick\n        note.length = length\n        note.velocity = velocity / 1000000\n        flp.score.addNote(note)\n";
    if (source !== canonical || !/^[0-9a-f]{64}$/.test(hash))
      return {ok: false, code: 'SOURCE_TEMPLATE_MISMATCH'};
    if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 60000)
      return {ok: false, code: 'INVALID_PROBE_TIMEOUT'};
    var digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical));
    var actual = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
    if (actual !== hash) return {ok: false, code: 'SOURCE_HASH_MISMATCH'};
    // 摘要计算会让出执行权，必须再次检查页面、队列及共享预算。
    if (window[key] !== state || !state.attached || epoch !== state.epoch ||
        state.poisoned || active || state.unacknowledged)
      return {ok: false, code: 'PROBE_SESSION_NOT_READY'};
    if (state.executorProbeAttempted)
      return {ok: false, code: 'PROBE_BUDGET_EXHAUSTED'};
    state.executorProbeAttempted = true;
    return startCall('call', 'run_piano_roll_script', {source: canonical}, timeout);
  };
  function startCall(kind, tool, args, timeout) {
    diagnostic('bridge_request_enter', {kind: kind, tool: tool || null});
    if (state.poisoned) return Promise.resolve({ok: false, code: 'SESSION_POISONED'});
    if (active) return Promise.resolve({ok: false, code: 'CALL_IN_FLIGHT'});
    if (state.unacknowledged) return Promise.resolve({ok: false, code: 'RESULT_NOT_ACKNOWLEDGED'});
    return new Promise(function (resolve) {
      var sh;
      try { sh = host(); } catch (_) { resolve({ok: false, code: 'HOST_UNAVAILABLE'}); return; }
      state.unacknowledged = true;
      active = {kind: kind, resolve: resolve, timer: null};
      active.timer = setTimeout(function () {
        diagnostic('bridge_timeout');
        // 宿主没有响应编号，迟到结果无法安全归属于下一项。
        state.poisoned = true;
        active = null;
        resolve({ok: false, code: 'EXECUTION_TIMEOUT', dispatched: true});
      }, timeout);
      try {
        diagnostic('script_handler_assignment_begin');
        if (kind === 'catalog') sh.MCPTools = '1';
        else sh.runJson = JSON.stringify({jsonrpc: '2.0', id: 1, method: 'tools/call',
          params: {name: tool, arguments: args}});
        diagnostic('script_handler_assignment_return');
      } catch (_) {
        state.poisoned = true;
        if (active) clearTimeout(active.timer);
        active = null;
        resolve({ok: false, code: 'DISPATCH_UNKNOWN', dispatched: true});
      }
    });
  }
  state.acknowledge = function (epoch) {
    if (epoch !== state.epoch || active || state.poisoned) return false;
    state.unacknowledged = false;
    return true;
  };
  state.dispose = function () {
    if (active) return {ok: false, code: 'CALL_IN_FLIGHT'};
    if (helper.onRunJson === onRun) {
      if (oldRun === undefined) delete helper.onRunJson; else helper.onRunJson = oldRun;
    } else state.interference += 1;
    if (helper.onMCPTools === onCatalog) {
      if (oldCatalog === undefined) delete helper.onMCPTools; else helper.onMCPTools = oldCatalog;
    } else state.interference += 1;
    if (!existed && Object.keys(helper).length === 0) delete window.flHelper;
    state.attached = false;
    return {ok: true, interference: state.interference};
  };
  window[key] = state;
  return {epoch: state.epoch, poisoned: state.poisoned};
})();
