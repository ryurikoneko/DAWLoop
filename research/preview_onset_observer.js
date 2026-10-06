(() => {
  'use strict';
  const key = '__dawloopPreviewOnsetObservation';
  if (window[key]) return {installed: false, reason: 'OBSERVER_ALREADY_INSTALLED'};
  const events = [];
  let mutationBatches = 0;
  let stopped = false;
  let firstCandidate = null;
  const stamp = (event, metadata = {}) => {
    if (events.length < 256) events.push({event, clock_domain: 'webview_performance',
      timestamp: performance.now(), timestamp_unit: 'ms', metadata});
  };
  const inventory = () => {
    const nodes = Array.from(document.querySelectorAll('*'));
    const candidates = nodes.filter(node => {
      // 两段固定探针标识只用于候选检测，不能把聊天中的引用认证为预览。
      const text = node.textContent || '';
      return node !== document.body && node !== document.documentElement &&
        node.children.length < 50 && text.includes('DAWLoop Native Add') &&
        text.includes('Experimental add-only preview.');
    });
    const visible = candidates.filter(node => {
      const style = getComputedStyle(node);
      return node.getClientRects().length > 0 && style.display !== 'none' &&
        style.visibility !== 'hidden' && style.visibility !== 'collapse' &&
        Number(style.opacity) !== 0;
    });
    return {node_count: nodes.length, candidate_count: candidates.length,
      layout_visible_candidates: visible.length,
      dialog_count: document.querySelectorAll('dialog,[role="dialog"]').length,
      iframe_count: document.querySelectorAll('iframe,frame').length,
      open_shadow_root_count: nodes.filter(node => node.shadowRoot).length,
      document_visibility: document.visibilityState,
      preview_identity_certified: false,
      coverage: 'TOP_DOCUMENT_ONLY',
      blind_spots: ['NATIVE_WINDOWS', 'FRAME_DOCUMENTS', 'SHADOW_ROOTS',
        'CSS_ONLY_TRANSITIONS', 'SCREEN_OCCLUSION', 'PAINT_TIME']};
  };
  const initial = inventory();
  if (initial.layout_visible_candidates) firstCandidate = 'EXISTED_AT_INSTALL';
  stamp('observer_installed', initial);
  const observer = new MutationObserver(() => {
    if (stopped) return;
    const begin = performance.now();
    mutationBatches++;
    const current = inventory();
    if (!firstCandidate && current.layout_visible_candidates) {
      firstCandidate = 'OBSERVED_IN_MUTATION_CALLBACK';
      stamp('preview_candidate_first_detected', {...current,
        onset_semantics: 'MUTATION_CALLBACK_DETECTION_NOT_PAINT'});
    }
    stamp('mutation_batch_observed', {mutation_batches: mutationBatches,
      candidate_count: current.candidate_count,
      layout_visible_candidates: current.layout_visible_candidates,
      callback_processing_ms: performance.now() - begin});
  });
  observer.observe(document.documentElement, {subtree: true, childList: true,
    attributes: true, characterData: true});
  const visibility = () => stamp('document_visibility_changed',
    {document_visibility: document.visibilityState});
  document.addEventListener('visibilitychange', visibility);
  window[key] = {
    snapshot: () => ({events: events.slice(), inventory: inventory(),
      mutation_batches: mutationBatches, first_candidate: firstCandidate,
      certified_preview_onset_ms: null, stopped}),
    dispose: () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', visibility);
      stopped = true;
      stamp('observer_disposed');
      return {ok: true};
    }
  };
  return {installed: true, inventory: initial};
})()
