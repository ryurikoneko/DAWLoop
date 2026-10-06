"""只读进程级原生事件采集；不提供窗口输入或状态修改接口。"""

from collections import deque
import ctypes
from ctypes import wintypes
import importlib.util
import threading
import time

EVENTS = {0x8000: 'CREATE', 0x8002: 'SHOW', 0x8003: 'HIDE', 0x8004: 'REORDER',
    0x800A: 'STATECHANGE', 0x800B: 'LOCATIONCHANGE', 0x800C: 'NAMECHANGE'}
TITLE = 'DAWLoop Native Add'


def safe_name(value):
    return value if value in {TITLE, 'Experimental add-only preview.'} else '<已脱敏>' if value else ''


class EventBuffer:
    def __init__(self, limit=8192, clock=time.perf_counter_ns):
        self.clock = clock
        self.rows = deque()
        self.limit = limit
        self.sequence = 0
        self.depth = 0
        self.dropped = 0

    def capture(self, event, hwnd, obj, child, event_thread, event_time):
        enter = self.clock()
        self.depth += 1
        try:
            self.sequence += 1
            row = dict(sequence_id=self.sequence, event=EVENTS[event], event_id=event,
                hwnd=int(hwnd or 0), idObject=obj, idChild=child, eventThread=event_thread,
                dwmsEventTime=event_time, callback_enter=enter, reentrant=self.depth > 1,
                clock_domain='python_perf_counter', timestamp_unit='ns')
            if self.sequence <= self.limit:
                row['callback_exit'] = self.clock()
                self.rows.append(row)
            else:
                self.dropped += 1
        finally:
            self.depth -= 1


def uia_subscription_probe():
    if importlib.util.find_spec('comtypes') is None:
        # 已有动态自动化绑定只支持派发接口，不能伪称已订阅原生未知接口。
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                pythoncom.CoCreateInstance('{FF48DBA4-60EF-4201-AA87-54103EEF594E}',
                    None, pythoncom.CLSCTX_INPROC_SERVER, pythoncom.IID_IDispatch)
            finally:
                pythoncom.CoUninitialize()
        except Exception as error:
            return dict(status='CLIENT_BINDING_UNAVAILABLE', subscription_tested=False,
                interface_probe_error=type(error).__name__,
                hresult=getattr(error, 'hresult', None), auto_install=False)
        return dict(status='SUBSCRIPTION_BINDING_UNAVAILABLE', subscription_tested=False, auto_install=False)
    return dict(status='SUBSCRIPTION_NOT_IMPLEMENTED', subscription_tested=False, auto_install=False)


class NativeEventObserver:
    def __init__(self, pid, trace_id):
        if type(pid) is not int or pid <= 0:
            raise ValueError('EXPLICIT_HOST_PID_REQUIRED')
        self.pid = pid
        self.trace_id = trace_id
        self.buffer = EventBuffer()
        self.records = []
        self.ready = threading.Event()
        self.stop_worker = threading.Event()
        self.hooks = []
        self.error = None
        self.unhooked = None
        self.thread_id = None
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
            wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        self.user.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
            self.callback_type, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        self.user.SetWinEventHook.restype = wintypes.HANDLE
        self.user.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        self.user.UnhookWinEvent.restype = wintypes.BOOL
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.GetParent.argtypes = [wintypes.HWND]
        self.user.GetParent.restype = wintypes.HWND
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.user.GetMessageW.restype = ctypes.c_int
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.DispatchMessageW.restype = wintypes.LPARAM
        self.enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumWindows.argtypes = [self.enum_type, wintypes.LPARAM]
        self.user.EnumChildWindows.argtypes = [wintypes.HWND, self.enum_type, wintypes.LPARAM]

    def describe(self, hwnd):
        process = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(process))
        if process.value != self.pid:
            return dict(resolution='WINDOW_GONE_OR_NOT_HOST')
        text, klass, rect = ctypes.create_unicode_buffer(512), ctypes.create_unicode_buffer(256), wintypes.RECT()
        self.user.GetWindowTextW(hwnd, text, len(text))
        self.user.GetClassNameW(hwnd, klass, len(klass))
        has_rect = self.user.GetWindowRect(hwnd, ctypes.byref(rect))
        return dict(resolution='HOST_WINDOW', process_id=process.value, name=safe_name(text.value),
            fixed_probe_title_match=text.value == TITLE, class_name=klass.value,
            bounding_rectangle=[rect.left, rect.top, rect.right, rect.bottom] if has_rect else None,
            visible=bool(self.user.IsWindowVisible(hwnd)), enabled=bool(self.user.IsWindowEnabled(hwnd)),
            parent_hwnd=int(self.user.GetParent(hwnd) or 0),
            resolution_perf_counter_ns=time.perf_counter_ns(), state_at_callback_proven=False)

    def snapshot(self):
        rows = []
        seen = set()
        def collect(hwnd, unused):
            if int(hwnd) not in seen:
                seen.add(int(hwnd))
                item = self.describe(hwnd)
                if item.get('process_id') == self.pid:
                    rows.append(dict(hwnd=int(hwnd), **item))
                    self.user.EnumChildWindows(hwnd, child, 0)
            return True
        def collect_child(hwnd, unused):
            if int(hwnd) not in seen:
                seen.add(int(hwnd))
                item = self.describe(hwnd)
                if item.get('process_id') == self.pid:
                    rows.append(dict(hwnd=int(hwnd), **item))
            return True
        child = self.enum_type(collect_child)
        top = self.enum_type(collect)
        self.user.EnumWindows(top, 0)
        return dict(timestamp=time.perf_counter_ns(), clock_domain='python_perf_counter',
            process_id=self.pid, windows=rows,
            foreground_hwnd=int(self.user.GetForegroundWindow() or 0),
            coverage='HOST_NATIVE_WINDOWS_NOT_UIA_TREE')

    def start(self):
        def callback(hook, event, hwnd, obj, child, thread, event_time):
            try:
                self.buffer.capture(event, hwnd, obj, child, thread, event_time)
            except Exception:
                self.buffer.dropped += 1
        self.callback = self.callback_type(callback)
        def pump():
            self.thread_id = self.kernel.GetCurrentThreadId()
            try:
                for event in EVENTS:
                    hook = self.user.SetWinEventHook(event, event, None, self.callback, self.pid, 0, 0)
                    if not hook:
                        raise OSError('HOOK_INSTALLATION_FAILED')
                    self.hooks.append(hook)
                # 建立消息队列后才报告就绪，保证退出消息不会因队列未创建而丢失。
                message = wintypes.MSG()
                self.user.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
                self.ready.set()
                while self.user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                    self.user.TranslateMessage(ctypes.byref(message))
                    self.user.DispatchMessageW(ctypes.byref(message))
            except Exception as error:
                self.error = type(error).__name__
                self.ready.set()
            finally:
                self.unhooked = all([bool(self.user.UnhookWinEvent(hook)) for hook in self.hooks])
        def resolve():
            while not self.stop_worker.is_set() or self.buffer.rows:
                try:
                    row = self.buffer.rows.popleft()
                except IndexError:
                    self.stop_worker.wait(0.01)
                    continue
                row['trace_id'] = self.trace_id
                row['details'] = self.describe(row['hwnd'])
                self.records.append(row)
        self.pump_thread = threading.Thread(target=pump, daemon=True)
        self.worker_thread = threading.Thread(target=resolve, daemon=True)
        self.pump_thread.start()
        if not self.ready.wait(5) or self.error:
            self.stop()
            raise ValueError('OBSERVER_NOT_READY')
        self.worker_thread.start()

    def stop(self):
        if self.thread_id:
            self.user.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if hasattr(self, 'pump_thread'):
            self.pump_thread.join(5)
        self.stop_worker.set()
        if hasattr(self, 'worker_thread') and self.worker_thread.ident:
            self.worker_thread.join(5)
        if hasattr(self, 'pump_thread') and self.pump_thread.is_alive():
            raise ValueError('OBSERVER_UNINSTALL_UNCONFIRMED')

    def result(self):
        return dict(pid=self.pid, trace_id=self.trace_id, events=self.records,
            dropped=self.buffer.dropped, unhooked=self.unhooked, error=self.error,
            timestamp_semantics='ASYNCHRONOUS_CALLBACK_RECEIPT_NOT_PIXEL_ONSET')
