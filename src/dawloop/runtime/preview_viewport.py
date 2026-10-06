"""限定已校准单显示器布局的只读视口指纹。"""

import hashlib
import time


def window_visual_facts(hwnd):
    import ctypes
    from ctypes import wintypes
    import win32gui
    facts = dict(cloaked=None, region_type=None, layered=None, transparent_style=None, errors={})
    try:
        style = win32gui.GetWindowLong(hwnd, -20)
        facts.update(layered=bool(style & 0x80000), transparent_style=bool(style & 0x20))
    except Exception as error:
        facts['errors']['style'] = type(error).__name__
    try:
        get_attribute = ctypes.WinDLL('dwmapi').DwmGetWindowAttribute
        get_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        get_attribute.restype = ctypes.c_long
        value = wintypes.DWORD()
        result = get_attribute(hwnd, 14, ctypes.byref(value), ctypes.sizeof(value))
        if result == 0:
            facts['cloaked'] = bool(value.value)
        else:
            facts['errors']['cloaked'] = 'HRESULT_ERROR'
    except Exception as error:
        facts['errors']['cloaked'] = type(error).__name__
    try:
        gdi = ctypes.WinDLL('gdi32')
        create, delete = gdi.CreateRectRgn, gdi.DeleteObject
        create.argtypes, create.restype = [ctypes.c_int]*4, wintypes.HANDLE
        delete.argtypes, delete.restype = [wintypes.HANDLE], wintypes.BOOL
        get_region = ctypes.WinDLL('user32').GetWindowRgn
        get_region.argtypes, get_region.restype = [wintypes.HWND, wintypes.HANDLE], ctypes.c_int
        region = create(0, 0, 0, 0)
        if not region:
            raise ValueError('REGION_ALLOCATION_FAILED')
        try:
            result = get_region(hwnd, region)
            # 返回零兼有“没有自定义区域”和“失败”两种语义，不能当空区域。
            facts['region_type'] = {1:'EMPTY', 2:'SIMPLE', 3:'COMPLEX'}.get(result)
            if result == 0:
                facts['errors']['region'] = 'NO_REGION_OR_ERROR'
        finally:
            if not delete(region):
                facts['errors']['region_cleanup'] = 'DELETE_FAILED'
                facts['region_type'] = None
    except Exception as error:
        facts['errors']['region'] = type(error).__name__
    return facts


def assess_occlusion_survey(survey, hit_test=None):
    candidates, excluded = [], []
    for item in survey.get('preceding_overlaps', []):
        facts = item.get('visual_facts') or {}
        value = dict(hwnd=item.get('hwnd'), level_hwnd=item.get('level_hwnd'))
        if facts.get('cloaked') is True:
            excluded.append(dict(**value, basis='COMPOSITION_CLOAKED'))
        elif facts.get('region_type') == 'EMPTY':
            excluded.append(dict(**value, basis='EMPTY_WINDOW_REGION'))
        else:
            candidates.append(dict(**value, basis='PIXEL_COVERAGE_UNKNOWN'))
    chain = survey.get('piano_roll_chain') or {}
    disabled = [v.get('hwnd') for v in chain.get('windows', []) if v.get('enabled') is False]
    hit_test = hit_test or {}
    before, after = hit_test.get('main_enabled_before'), hit_test.get('main_enabled_after')
    transition = type(before) is bool and type(after) is bool and before != after
    gaps = ['PIXEL_COVERAGE_UNPROVEN']
    if survey.get('atomic_snapshot') is not True:
        gaps.append('NON_ATOMIC_SURVEY')
    if chain.get('complete') is not True or survey.get('preceding_scan_complete') is not True:
        gaps.append('SURVEY_INCOMPLETE')
    if candidates:
        gaps.append('COVERAGE_CANDIDATES_REMAIN')
    # 影子分类没有完整视觉覆盖证明，即使排除了全部已知候选也不能放行。
    return dict(scope='SHADOW_DIAGNOSTIC_ONLY', visual_coverage='UNKNOWN', allow_dispatch=False,
        guard_action='KEEP_ORIGINAL_GUARD', candidates=candidates, excluded=excluded,
        disabled_chain_hwnds=disabled, main_enabled_transition=transition,
        missing_evidence=gaps, exact_set_verified=False)


class ViewportInvalidated(ValueError):
    def __init__(self, code, reason, details):
        super().__init__(code)
        self.reason, self.details = reason, details


class NativePianoRollViewport:
    def __init__(self, pid):
        import win32gui
        import win32process
        import ctypes
        self.gui, self.process, self.user = win32gui, win32process, ctypes.windll.user32
        self.pid = pid
        self.hwnd = self._find()
        self.top = win32gui.GetAncestor(self.hwnd, 2)

    def _find(self):
        candidates = []
        def top(hwnd, unused):
            if self.process.GetWindowThreadProcessId(hwnd)[1] == self.pid:
                self.gui.EnumChildWindows(hwnd, child, None)
        def child(hwnd, unused):
            if self.gui.GetClassName(hwnd) != 'TEventEditForm' or not self.gui.IsWindowVisible(hwnd):
                return
            rect = self.gui.GetWindowRect(hwnd)
            bars = []
            self.gui.EnumChildWindows(hwnd, lambda h, _: bars.append(self.gui.GetWindowRect(h))
                if self.gui.GetClassName(h) == 'TNumBar' else None, None)
            if len(bars) == 2 and all(b[2] == rect[2] for b in bars):
                candidates.append(hwnd)
        self.gui.EnumWindows(top, None)
        if len(set(candidates)) != 1:
            raise ValueError('PIANO_ROLL_VIEWPORT_AMBIGUOUS')
        return candidates[0]

    def _occlusion_evidence(self, roi, hit):
        started = time.perf_counter_ns()
        def state(hwnd):
            return dict(hwnd=hwnd, enabled=bool(self.gui.IsWindowEnabled(hwnd)),
                visible=bool(self.gui.IsWindowVisible(hwnd)),
                same_process=self.process.GetWindowThreadProcessId(hwnd)[1] == self.pid,
                rectangle=list(self.gui.GetWindowRect(hwnd)))
        def chain(hwnd):
            values, seen = [], set()
            while hwnd and hwnd not in seen and len(values) < 16:
                seen.add(hwnd)
                values.append(state(hwnd))
                hwnd = self.gui.GetParent(hwnd)
            return dict(windows=values, complete=not hwnd)
        def intersects(rect):
            return rect[0] < roi[2] and rect[2] > roi[0] and rect[1] < roi[3] and rect[3] > roi[1]
        piano_chain, hit_chain = chain(self.hwnd), chain(hit)
        preceding, complete = [], True
        # 命中会跳过禁用窗口；另存各层前序窗口几何，避免用命中结果冒充覆盖证据。
        for item in piano_chain['windows']:
            hwnd, seen = self.gui.GetWindow(item['hwnd'], 3), set()
            while hwnd and hwnd not in seen and len(seen) < 64:
                seen.add(hwnd)
                value = state(hwnd)
                if value['visible'] and intersects(value['rectangle']):
                    value['visual_facts'] = window_visual_facts(hwnd)
                    preceding.append(dict(level_hwnd=item['hwnd'], **value))
                hwnd = self.gui.GetWindow(hwnd, 3)
            complete = complete and not hwnd
        dialogs = []
        def candidate(hwnd, unused):
            if (self.process.GetWindowThreadProcessId(hwnd)[1] == self.pid
                    and self.gui.GetClassName(hwnd) == 'TScriptDialog'
                    and self.gui.GetWindowText(hwnd) == 'DAWLoop Native Add'
                    and self.gui.IsWindowVisible(hwnd)):
                value = state(hwnd)
                dialogs.append(dict(**value, intersects_roi=intersects(value['rectangle'])))
        self.gui.EnumChildWindows(self.top, candidate, None)
        self.gui.EnumWindows(candidate, None)
        return dict(piano_roll_chain=piano_chain, hit_chain=hit_chain,
            preceding_overlaps=preceding, preceding_scan_complete=complete,
            fixed_preview_windows=list({v['hwnd']:v for v in dialogs}.values()),
            inspection_started_ns=started, inspection_completed_ns=time.perf_counter_ns(),
            atomic_snapshot=False, geometry_does_not_prove_pixel_occlusion=True)

    def fingerprint(self, *, require_input_hit=True):
        from .preview_pixels import RegionCapture
        self.last_inspection = {}
        def reject(code, reason):
            raise ViewportInvalidated(code, reason, dict(self.last_inspection))
        exists = bool(self.gui.IsWindow(self.hwnd))
        self.last_inspection['window_exists'] = exists
        if not exists:
            reject('VIEWPORT_INVALIDATED', 'WINDOW_GONE')
        visible = bool(self.gui.IsWindowVisible(self.hwnd))
        same_process = self.process.GetWindowThreadProcessId(self.hwnd)[1] == self.pid
        self.last_inspection.update(window_visible=visible, window_process_matches=same_process)
        if not visible:
            reject('VIEWPORT_INVALIDATED', 'WINDOW_HIDDEN')
        if not same_process:
            reject('VIEWPORT_INVALIDATED', 'WINDOW_PROCESS_CHANGED')
        self.last_inspection['window_enabled'] = bool(self.gui.IsWindowEnabled(self.hwnd))
        foreground = self.gui.GetForegroundWindow()
        own_preview = (self.process.GetWindowThreadProcessId(foreground)[1] == self.pid
            and self.gui.GetClassName(foreground) == 'TScriptDialog'
            and self.gui.GetWindowText(foreground) == 'DAWLoop Native Add'
            and self.gui.GetParent(foreground) == self.top)
        self.last_inspection.update(foreground_hwnd=foreground,
            foreground_is_main=foreground == self.top, foreground_is_fixed_preview=own_preview)
        if foreground != self.top and not own_preview:
            reject('VIEWPORT_INVALIDATED', 'FOREGROUND_NOT_ALLOWED')
        rect = self.gui.GetWindowRect(self.hwnd)
        client = self.gui.GetClientRect(self.hwnd)
        origin = self.gui.ClientToScreen(self.hwnd, (0, 0))
        self.last_inspection.update(window_rectangle=list(rect), client_rectangle=list(client),
            client_screen_origin=list(origin), window_dpi=self.user.GetDpiForWindow(self.hwnd))
        # 客户区内偏移来自四音符实验校准；不扩展为任意缩放布局。
        roi = tuple(rect[i%2] + v for i, v in enumerate((247, 213, 477, 363)))
        anchors = [(rect[0]+247, rect[1]+46, rect[0]+477, rect[1]+63),
            (rect[0]+1, rect[1]+213, rect[0]+68, rect[1]+363)]
        hashes = []
        scale = None
        for region in anchors:
            capture = RegionCapture(region)
            try:
                frame, _, _ = capture.grab()
                hashes.append(hashlib.sha256(frame[:, :, :3].tobytes()).hexdigest())
                scale = list(capture.scale)
            finally:
                capture.close()
        if client[2] != 1669 or client[3] != 1016 or scale != [1.25, 1.25]:
            self.last_inspection['scale'] = scale
            reject('VIEWPORT_LAYOUT_UNSUPPORTED', 'UNCALIBRATED_LAYOUT')
        self.last_inspection.update(scale=scale, roi=list(roi), viewport_ruler_hashes=hashes)
        if require_input_hit:
            for x, y in ((roi[0], roi[1]), (roi[2]-1, roi[3]-1)):
                state_started = time.perf_counter_ns()
                main_before = bool(self.gui.IsWindowEnabled(self.top))
                hit_started = time.perf_counter_ns()
                window = self.gui.WindowFromPoint((x, y))
                hit_completed = time.perf_counter_ns()
                main_after = bool(self.gui.IsWindowEnabled(self.top))
                state_completed = time.perf_counter_ns()
                hit_window = window
                while window and window != self.hwnd:
                    window = self.gui.GetParent(window)
                if window != self.hwnd:
                    self.last_inspection.update(occluded_point=[x, y], hit_hwnd=hit_window)
                    hit_test = dict(started_ns=hit_started, completed_ns=hit_completed,
                        state_inspection_started_ns=state_started, state_inspection_completed_ns=state_completed,
                        main_enabled_before=main_before, main_enabled_after=main_after,
                        atomic_snapshot=False)
                    self.last_inspection['hit_test'] = hit_test
                    try:
                        survey = self._occlusion_evidence(roi, hit_window)
                        self.last_inspection['occlusion_evidence'] = survey
                        self.last_inspection['shadow_assessment'] = assess_occlusion_survey(survey, hit_test)
                    except Exception as error:
                        self.last_inspection['occlusion_evidence_error'] = type(error).__name__
                    reject('VIEWPORT_INVALIDATED', 'ROI_OCCLUDED')
        return dict(piano_roll_hwnd=self.hwnd, main_hwnd=self.top,
            window_rectangle=list(rect), client_rectangle=list(client), client_screen_origin=list(origin),
            coordinate_space='WIN32_LOGICAL_IN_CURRENT_PROCESS_CONTEXT', scale=scale,
            window_dpi=self.user.GetDpiForWindow(self.hwnd), roi=list(roi),
            physical_roi=[round(v*scale[i%2]) for i,v in enumerate(roi)],
            viewport_ruler_hashes=hashes, numeric_zoom=None, scroll_position=None,
            title_hash=hashlib.sha256(self.gui.GetWindowText(self.hwnd).encode('utf-8')).hexdigest(),
            viewport_basis='CALIBRATED_TIME_AND_PITCH_RULER_PIXELS',
            display_scope='SINGLE_PRIMARY_DISPLAY_CALIBRATED_LAYOUT')

    def preview_snapshot(self):
        fingerprint = self.fingerprint(require_input_hit=False)
        roi = fingerprint['roi']
        dialogs = {}
        def candidate(hwnd, unused):
            if (self.process.GetWindowThreadProcessId(hwnd)[1] != self.pid
                    or self.gui.GetClassName(hwnd) != 'TScriptDialog'
                    or not self.gui.IsWindowVisible(hwnd)):
                return
            dialogs[hwnd] = dict(hwnd=hwnd, parent=self.gui.GetParent(hwnd),
                native_title=self.gui.GetWindowText(hwnd), window_class=self.gui.GetClassName(hwnd),
                fixed_title=self.gui.GetWindowText(hwnd) == 'DAWLoop Native Add',
                enabled=bool(self.gui.IsWindowEnabled(hwnd)), rectangle=list(self.gui.GetWindowRect(hwnd)))
        self.gui.EnumWindows(candidate, None)
        self.gui.EnumChildWindows(self.top, candidate, None)
        if len(dialogs) > 1:
            raise ViewportInvalidated('VIEWPORT_INVALIDATED', 'PREVIEW_DIALOG_AMBIGUOUS', {})
        preview = next(iter(dialogs.values()), None)
        if preview:
            if not preview['fixed_title'] or preview['parent'] != self.top or not preview['enabled']:
                raise ViewportInvalidated('VIEWPORT_INVALIDATED', 'PREVIEW_DIALOG_UNEXPECTED', {})
            left, top, right, bottom = preview['rectangle']
            if left < roi[2] and right > roi[0] and top < roi[3] and bottom > roi[1]:
                raise ViewportInvalidated('VIEWPORT_INVALIDATED', 'PREVIEW_DIALOG_COVERS_ROI', {})
        return dict(fingerprint=fingerprint, preview_confirmed=preview is not None, preview=preview)
