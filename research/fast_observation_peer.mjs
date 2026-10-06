import { access, mkdir, readFile, readdir, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { CaptureIntervalObserver, digest } from './capture_interval_observer.mjs';

export class AgentVisualReview {
  constructor() {
    this.attached = false;
    this.pending = null;
  }

  attach() {
    if (this.attached || this.pending) throw Error('VISUAL_REVIEW_ALREADY_ATTACHED');
    this.attached = true;
    const callback = (request, packet, { signal }) => new Promise((resolve, reject) => {
      if (!this.attached || this.pending || signal.aborted) return reject(Error('VISUAL_REVIEW_NOT_READY'));
      const abort = () => this.finish(null, Error('REQUEST_CANCELLED'));
      this.pending = { request: structuredClone(request), packet: {
        result: structuredClone(packet.result), bytes: Buffer.from(packet.bytes) }, resolve, reject, signal, abort };
      signal.addEventListener('abort', abort, { once: true });
    });
    callback.ready = () => this.attached;
    return callback;
  }

  current() {
    if (!this.pending) return null;
    return { request: structuredClone(this.pending.request),
      result: structuredClone(this.pending.packet.result), bytes: Buffer.from(this.pending.packet.bytes) };
  }

  confirm(review) {
    const pending = this.pending;
    if (!pending || !review || pending.signal.aborted || review.observer !== 'agent_visual_review' ||
        review.request_id !== pending.request.request_id ||
        review.observer_generation !== pending.request.observer_generation ||
        review.image_hash !== pending.packet.result.image_hash ||
        typeof review.visible !== 'boolean' || typeof review.confirmed !== 'boolean' ||
        !Number.isInteger(review.pattern_number) || typeof review.channel_name !== 'string' ||
        !Number.isInteger(review.window_pid) || !Number.isInteger(review.window_hwnd))
      throw Error('IMAGE_REVIEW_BINDING_FAILED');
    // 返回实际观察字段，不从预期目标填充标题、可见音符或空区域结论。
    this.finish(structuredClone(review));
  }

  finish(review, error) {
    const pending = this.pending;
    if (!pending) return;
    pending.signal.removeEventListener('abort', pending.abort);
    this.pending = null;
    if (error) pending.reject(error); else pending.resolve(review);
  }

  detach() {
    this.attached = false;
    this.finish(null, Error('VISUAL_REVIEW_DETACHED'));
  }
}

export class FastObservationPeer {
  constructor(sky, window, { directory, artifactDirectory, review, runtimePid }) {
    if (!Number.isInteger(runtimePid) || runtimePid <= 0) throw Error('OBSERVER_RUNTIME_PID_REQUIRED');
    this.runtimePid = runtimePid;
    this.observer = new CaptureIntervalObserver(sky);
    this.window = window;
    this.directory = directory;
    this.artifactDirectory = artifactDirectory;
    this.review = review;
    this.completed = new Set();
    this.stopped = false;
    this.active = null;
    this.loop = null;
    this.lastHeartbeat = 0;
    this.failure = null;
    this.manifestQueue = Promise.resolve();
    this.reviewTasks = new Set();
    this.reviewAbort = null;
    this.captureReady = false;
  }

  async manifest(ready) {
    const job = this.manifestQueue.then(async () => {
      const body = { source: 'CaptureIntervalObserver', pid: this.runtimePid,
        observer_generation: this.observer.generation,
        ready: ready && !this.stopped && this.captureReady && this.reviewReady(),
        capture_ready: this.captureReady,
        review_ready: this.reviewReady(), observed_at: Date.now() / 1000 };
      await writeFile(join(this.directory, 'observer.tmp'), JSON.stringify(body), { encoding: 'utf8' });
      await rename(join(this.directory, 'observer.tmp'), join(this.directory, 'observer.json'));
      this.lastHeartbeat = Date.now();
    });
    this.manifestQueue = job.catch(() => {});
    await job;
  }

  async start() {
    if (this.loop || this.stopped) throw Error('OBSERVER_ALREADY_STARTED');
    await mkdir(join(this.directory, 'mailbox'), { recursive: true });
    await mkdir(this.artifactDirectory, { recursive: true });
    if (this.reviewReady() && typeof this.observer.sky?.get_window_state === 'function') {
      try {
        const state = await this.observer.sky.get_window_state({ window: this.window,
          include_screenshot: false, include_text: true });
        this.captureReady = state?.window?.id === this.window.id;
      } catch (_) {
        this.captureReady = false;
      }
    }
    await this.manifest(this.reviewReady());
    this.loop = this.pump().catch(async error => {
      this.failure = error.message;
      this.stopped = true;
      await this.manifest(false);
    });
    return { observer_generation: this.observer.generation, review_ready: this.reviewReady() };
  }

  reviewReady() {
    return typeof this.review === 'function' &&
      (typeof this.review.ready !== 'function' || this.review.ready() === true);
  }

  async pump() {
    while (!this.stopped) {
      if (Date.now() - this.lastHeartbeat > 1000) await this.manifest(this.reviewReady());
      const mailbox = join(this.directory, 'mailbox');
      const names = (await readdir(mailbox)).filter(name => name.endsWith('.request.json') && !this.completed.has(name));
      if (names.length > 1) throw Error('PENDING_OBSERVATION_NOT_UNIQUE');
      if (names.length && this.captureReady && this.reviewReady()) {
        const name = names[0];
        const { request } = JSON.parse(await readFile(join(mailbox, name), 'utf8'));
        const cancel = join(mailbox, request.request_id + '.cancel.json');
        if (await access(cancel).then(() => true, () => false)) {
          this.completed.add(name);
        } else {
          await this.handle(request);
          this.completed.add(name);
        }
      }
      await delay(50);
    }
  }

  async handle(request) {
    if (!request || request.observer_generation !== this.observer.generation ||
        !['TARGET', 'APPLICATION'].includes(request.stage) ||
        !/^[a-f0-9]{32}$/.test(request.request_id) || !/^[a-f0-9]{32}$/.test(request.run_id) ||
        !/^[a-f0-9]{32}$/.test(request.session_id)) throw Error('OBSERVATION_GENERATION_MISMATCH');
    const wrapped = Object.freeze({ operation_id: request.operation_id, request_id: request.request_id,
      observer_generation: this.observer.generation, binding: structuredClone(request),
      created_at: this.observer.stamp() });
    this.active = wrapped;
    const prefix = join(this.directory, 'mailbox', request.request_id);
    const expired = async () => this.stopped ||
      this.observer.stamp().monotonic_ms - wrapped.created_at.monotonic_ms > 55000 ||
      await access(prefix + '.cancel.json').then(() => true, () => false);
    try {
      const packet = await this.observer.capture(wrapped, this.window);
      if (await expired()) throw Error('REQUEST_CANCELLED');
      const receipt = this.observer.accept(wrapped, packet);
      if (!receipt.accepted) throw Error('CAPTURE_NOT_ACCEPTED');
      const artifact = join(this.artifactDirectory, request.request_id +
        (packet.result.image_mime === 'image/jpeg' ? '.jpg' : '.png'));
      await this.observer.persist(packet, artifact);
      // 审阅者接收本次帧的独立字节；没有审阅函数时根本不发布confirmed。
      this.reviewAbort = new AbortController();
      const reviewJob = Promise.resolve().then(() => this.review(structuredClone(request), {
        result: structuredClone(receipt.result), bytes: Buffer.from(packet.bytes) },
        { signal: this.reviewAbort.signal }));
      this.reviewTasks.add(reviewJob);
      reviewJob.finally(() => this.reviewTasks.delete(reviewJob)).catch(() => {});
      let reviewDone = false;
      let review;
      try {
        review = await Promise.race([reviewJob, (async () => {
          while (!reviewDone && !await expired()) await delay(50);
          if (!reviewDone) throw Error('REQUEST_CANCELLED');
        })()]);
      } finally {
        reviewDone = true;
      }
      if (await expired()) throw Error('REQUEST_CANCELLED');
      if (review?.image_hash !== packet.result.image_hash ||
          review.request_id !== request.request_id ||
          review.observer_generation !== this.observer.generation ||
          digest(await readFile(artifact)) !== packet.result.image_hash)
        throw Error('IMAGE_REVIEW_BINDING_FAILED');
      const reply = { request, capture: receipt.result, review, artifact };
      await writeFile(prefix + '.result.tmp', JSON.stringify(reply), { flag: 'wx', encoding: 'utf8' });
      if (await expired()) throw Error('REQUEST_CANCELLED');
      await rename(prefix + '.result.tmp', prefix + '.result.json');
    } catch (error) {
      this.observer.cancel(wrapped);
      this.reviewAbort?.abort();
      await writeFile(prefix + '.diagnostic.json', JSON.stringify({
        request_id: request.request_id, stage: request.stage, error_code: error.message,
        result_accepted: false }), { flag: 'wx', encoding: 'utf8' });
      throw error;
    } finally {
      const teardown = await this.observer.teardown(wrapped, 1000);
      this.active = null;
      this.reviewAbort = null;
      if (teardown.status !== 'PASS') throw Error('OBSERVER_TEARDOWN_FAILED');
    }
  }

  async stop() {
    this.stopped = true;
    this.reviewAbort?.abort();
    if (this.active && this.observer.records.has(this.active.request_id)) this.observer.cancel(this.active);
    await this.manifest(false);
    let timer;
    const waiting = Promise.all([this.loop, ...this.reviewTasks].map(task => Promise.resolve(task).catch(() => {})));
    const exited = await Promise.race([waiting.then(() => true),
      new Promise(resolve => { timer = setTimeout(() => resolve(false), 1000); })]);
    clearTimeout(timer);
    return { status: exited && !this.active && this.observer.tasks.size === 0 && this.reviewTasks.size === 0
      ? 'PASS' : 'OBSERVER_TEARDOWN_FAILED',
      observer_generation: this.observer.generation, tasks_remaining: this.observer.tasks.size,
      review_tasks_remaining: this.reviewTasks.size,
      failure: this.failure };
  }
}
