import { createHash, randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { writeFile } from 'node:fs/promises';

export function digest(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

export function describeReturn(value, depth = 0) {
  if (value === null) return { runtime_type: 'null' };
  if (Buffer.isBuffer(value) || value instanceof Uint8Array)
    return { runtime_type: 'binary', length: value.byteLength, hash: digest(value) };
  if (typeof value === 'string') {
    const mime = /^data:([a-z0-9.+-]+\/[a-z0-9.+-]+)[;,]/i.exec(value)?.[1];
    return { runtime_type: 'string', length: value.length, ...(mime ? { declared_mime: mime } : {}) };
  }
  if (Array.isArray(value)) return { runtime_type: 'array', length: value.length,
    items: depth < 5 ? value.map(item => describeReturn(item, depth + 1)) : undefined };
  if (typeof value === 'object') return { runtime_type: 'object', fields: Object.keys(value),
    declared_mime: [value.mime,value.type].find(item => typeof item === 'string' &&
      /^[a-z0-9.+-]+\/[a-z0-9.+-]+$/i.test(item)),
    structure: depth < 5 ? Object.fromEntries(Object.entries(value).map(([key,item]) =>
      [key,describeReturn(item,depth+1)])) : undefined };
  return { runtime_type: typeof value };
}

function imageDimensions(bytes, mime) {
  let dimensions;
  if (mime === 'image/png' && bytes.length >= 24 &&
      bytes.subarray(0,8).toString('hex') === '89504e470d0a1a0a' &&
      bytes.subarray(12,16).toString('ascii') === 'IHDR') {
    dimensions = { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
  } else if (mime === 'image/jpeg' && bytes.length >= 4 && bytes.readUInt16BE(0) === 0xffd8) {
    let offset = 2;
    while (offset + 4 <= bytes.length) {
      if (bytes[offset++] !== 0xff) break;
      while (bytes[offset] === 0xff) offset++;
      const marker = bytes[offset++];
      if (marker === 0xd9 || marker === 0xda) break;
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
      if (offset + 2 > bytes.length) break;
      const length = bytes.readUInt16BE(offset);
      if (length < 2 || offset + length > bytes.length) break;
      if ([0xc0,0xc1,0xc2].includes(marker) && length >= 8) {
        dimensions = { height: bytes.readUInt16BE(offset+3), width: bytes.readUInt16BE(offset+5) };
        break;
      }
      offset += length;
    }
  }
  if (!dimensions || dimensions.width < 1 || dimensions.height < 1)
    throw Error('CAPTURE_FORMAT_UNSUPPORTED');
  return dimensions;
}

export function extractImage(frame) {
  if (!frame || typeof frame.url !== 'string') throw Error('CAPTURE_IMAGE_PAYLOAD_MISSING');
  const match = /^data:(image\/png|image\/jpeg);base64,([A-Za-z0-9+/]*={0,2})$/.exec(frame.url);
  if (!match) throw Error('CAPTURE_FORMAT_UNSUPPORTED');
  if (!match[2]) throw Error('CAPTURE_IMAGE_PAYLOAD_EMPTY');
  const bytes = Buffer.from(match[2], 'base64');
  if (!bytes.length || bytes.toString('base64') !== match[2]) throw Error('CAPTURE_FORMAT_UNSUPPORTED');
  return { bytes, mime: match[1], dimensions: imageDimensions(bytes,match[1]) };
}

export class CaptureIntervalObserver {
  constructor(sky) {
    this.sky = sky;
    this.generation = randomUUID();
    this.clockDomain = `node-observer-${this.generation}`;
    this.records = new Map();
    this.tasks = new Map();
    this.quarantine = [];
  }

  stamp() {
    return { clock_domain: this.clockDomain, monotonic_ms: performance.now(), wall_unix_ms: Date.now() };
  }

  request(operationId, binding) {
    return Object.freeze({ operation_id: operationId, request_id: randomUUID(),
      observer_generation: this.generation, binding: structuredClone(binding), created_at: this.stamp() });
  }

  async capture(request, window, { beforeDelivery, onRawResponse } = {}) {
    if (request.observer_generation !== this.generation || this.records.has(request.request_id))
      throw Error('GENERATION_MISMATCH');
    const record = { request: structuredClone(request), cancelled: false, exited: false, accepted: false };
    this.records.set(request.request_id, record);
    const job = (async () => {
      try {
        const received = this.stamp();
        const started = this.stamp();
        const state = await this.sky.get_window_state({ window, include_screenshot: true, include_text: false });
        const completed = this.stamp();
        // 原始返回的序列化副本仅留在本地内存；公开证据先保存结构、摘要和调用区间。
        record.rawSerialization = JSON.stringify(state);
        record.rawResponseHash = digest(Buffer.from(record.rawSerialization));
        record.rawEvidence = { request_id: request.request_id, operation_id: request.operation_id,
          observer_generation: this.generation, capture_started_at: started, capture_completed_at: completed,
          raw_response_hash: record.rawResponseHash, raw_response_type: describeReturn(state) };
        if (onRawResponse) await onRawResponse(structuredClone(record.rawEvidence));
        if (!state || !Array.isArray(state.screenshots) || !state.window)
          throw Error('CAPTURE_FORMAT_UNSUPPORTED');
        const frames = [...state.screenshots].sort((a,b)=>(b.width*b.height)-(a.width*a.height));
        if (state.window.id !== window.id || !frames.length ||
            (frames.length > 1 && frames.some(frame => !Number.isFinite(frame.width*frame.height) || frame.width*frame.height <= 0)) ||
            (frames.length > 1 && frames[0].width*frames[0].height === frames[1].width*frames[1].height))
          throw Error('IMAGE_TIMESTAMP_BINDING_FAILED');
        const frame = frames[0];
        const image = extractImage(frame);
        const bytes = image.bytes;
        const result = { request_id: request.request_id, operation_id: request.operation_id,
          observer_generation: this.generation, binding: structuredClone(request.binding),
          observer_received_at: received, capture_started_at: started, capture_completed_at: completed,
          captured_at: { kind: 'API_CALL_INTERVAL', start: started, end: completed },
          raw_response_hash: record.rawResponseHash, raw_response_type: record.rawEvidence.raw_response_type,
          image_hash: digest(bytes), image_dimensions: image.dimensions, image_mime: image.mime,
          image_encoding: 'base64_data_url', screenshot_id: frame.id,
          window_id: state.window.id, capture_source: 'sky.get_window_state' };
        // 封装对应本次调用返回的字节；摘要生成与文件保存时刻均不冒充采样时间。
        record.captureSeal = digest(Buffer.from(JSON.stringify(result)));
        record.capture = structuredClone(result);
        if (beforeDelivery) await beforeDelivery();
        result.published_at = this.stamp();
        record.resultSeal = digest(Buffer.from(JSON.stringify(result)));
        if (record.cancelled) {
          this.quarantine.push({ event: 'LATE_CANCELLED_RESULT', request_id: request.request_id,
            image_hash: result.image_hash, capture_interval: result.captured_at });
          return { cancelled: true, result, bytes };
        }
        return { result, bytes };
      } finally {
        record.exited = true;
        this.tasks.delete(request.request_id);
      }
    })();
    this.tasks.set(request.request_id, job);
    return job;
  }

  cancel(request) {
    const record = this.records.get(request.request_id);
    if (!record || JSON.stringify(record.request) !== JSON.stringify(request)) throw Error('GENERATION_MISMATCH');
    record.cancelled = true;
    record.cancelledAt = this.stamp();
  }

  accept(request, packet) {
    const received = this.stamp();
    const record = this.records.get(request.request_id);
    if (!record || request.observer_generation !== this.generation ||
        JSON.stringify(record.request) !== JSON.stringify(request)) throw Error('GENERATION_MISMATCH');
    if (record.cancelled) {
      this.quarantine.push({ event: 'LATE_RESULT', request_id: request.request_id });
      return { accepted: false, received_at: received };
    }
    if (record.accepted || !packet?.result || !packet?.bytes) throw Error('IMAGE_TIMESTAMP_BINDING_FAILED');
    const result = packet.result;
    if (result.request_id !== request.request_id || result.operation_id !== request.operation_id ||
        result.observer_generation !== request.observer_generation ||
        JSON.stringify(result.binding) !== JSON.stringify(request.binding)) throw Error('GENERATION_MISMATCH');
    if (digest(packet.bytes) !== result.image_hash ||
        digest(Buffer.from(JSON.stringify(result))) !== record.resultSeal ||
        result.raw_response_hash !== record.rawResponseHash ||
        digest(Buffer.from(record.rawSerialization)) !== record.rawResponseHash ||
        JSON.stringify(imageDimensions(packet.bytes,result.image_mime)) !== JSON.stringify(result.image_dimensions))
      throw Error('IMAGE_TIMESTAMP_BINDING_FAILED');
    const start = result.capture_started_at, end = result.capture_completed_at;
    if (!start || !end || start.clock_domain !== this.clockDomain || end.clock_domain !== this.clockDomain ||
        start.monotonic_ms > end.monotonic_ms) throw Error('CAPTURE_TIMESTAMP_UNAVAILABLE');
    if (received.monotonic_ms - request.created_at.monotonic_ms > 55000) throw Error('DELIVERY_TOO_LATE');
    record.accepted = true;
    return { accepted: true, result: structuredClone(result), received_at: received,
      capture_duration_ms: end.monotonic_ms - start.monotonic_ms,
      delivery_age_interval_ms: [received.monotonic_ms - end.monotonic_ms, received.monotonic_ms - start.monotonic_ms] };
  }

  async persist(packet, filename) {
    await writeFile(filename, packet.bytes, { flag: 'wx' });
  }

  async submitApplication(request, observation, review, { evidencePath, receiptPath, timingPath }) {
    const reviewCompleted = this.stamp();
    const record = this.records.get(request.request_id);
    if (!record || record.cancelled || !record.accepted || record.submitted ||
        JSON.stringify(record.request) !== JSON.stringify(request) ||
        observation?.accepted !== true ||
        digest(Buffer.from(JSON.stringify(observation.result))) !== record.resultSeal ||
        review.image_hash !== observation.result.image_hash)
      throw Error('IMAGE_REVIEW_BINDING_FAILED');
    if (['observed', 'preview_closed', 'phrase_visible'].some(k => typeof review[k] !== 'boolean') ||
        !Number.isInteger(review.visible_pattern) || review.visible_pattern < 1 ||
        typeof review.channel_name !== 'string' || !review.channel_name)
      throw Error('APPLICATION_REVIEW_REQUIRED');
    const receipt = { operation_id: request.operation_id, observer: 'agent_visual_review',
      evidence_ref: 'application_observation.json', observed: review.observed,
      preview_closed: review.preview_closed, phrase_visible: review.phrase_visible,
      visible_pattern: review.visible_pattern, channel_name: review.channel_name,
      observed_unix: observation.result.capture_completed_at.wall_unix_ms / 1000 };
    const timing = { capture_completed_at: observation.result.capture_completed_at,
      review_completed_at: reviewCompleted,
      review_timestamp_basis: 'OBSERVER_REVIEW_COMPLETION_ACKNOWLEDGED',
      submit_started_at: this.stamp(), receipt_persisted_at: null };
    // 审阅回执立即落盘；本地观察器接收不冒充协调器领取。
    record.submitted = true;
    await writeFile(evidencePath, JSON.stringify({ ...receipt, ...request.binding,
      frame: observation, verification_level: 'UNVERIFIED' }, null, 2), { flag: 'wx' });
    await writeFile(receiptPath, JSON.stringify(receipt), { flag: 'wx' });
    timing.receipt_persisted_at = this.stamp();
    await writeFile(timingPath, JSON.stringify(timing, null, 2), { flag: 'wx' });
    return { receipt, timing };
  }

  async teardown(request, timeoutMs = 1000) {
    const record = this.records.get(request.request_id);
    const task = this.tasks.get(request.request_id);
    let timer;
    if (task) {
      await Promise.race([task.catch(() => {}), new Promise(resolve => { timer = setTimeout(resolve, timeoutMs); })]);
      clearTimeout(timer);
    }
    return { cancellation_signaled: record?.cancelled === true, observer_exited: record?.exited === true,
      outstanding_tasks: this.tasks.size, dedicated_worker_processes_created: 0,
      status: record?.exited && this.tasks.size === 0 ? 'PASS' : 'CANCELLATION_FAILED' };
  }
}
