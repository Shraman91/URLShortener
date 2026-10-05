import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict
from google.cloud import firestore as gcf

from firebase import db


class AsyncAnalyticsQueue:
    """
    High-throughput non-blocking click analytics queue.
    Buffers click events in-memory and flushes in micro-batches to the database,
    removing write latency and Firestore document contention from the redirect path.
    """
    def __init__(self, batch_size: int = 50, flush_interval: float = 2.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task = None
        self._running = False
        # Telemetry metrics
        self.total_enqueued: int = 0
        self.total_flushed: int = 0
        self.total_batches: int = 0
        self.last_flush_time: Optional[str] = None

    def start(self):
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._process_queue())
            print("[AnalyticsQueue] Async click processing worker started.")

    async def stop(self):
        self._running = False
        if self._worker_task:
            # Drain remaining items
            await self._flush_remaining()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            print("[AnalyticsQueue] Worker stopped and buffer flushed.")

    def enqueue(self, event: Dict[str, Any]):
        """Non-blocking instant enqueue for redirect requests."""
        try:
            self._queue.put_nowait(event)
            self.total_enqueued += 1
        except Exception as e:
            print(f"[AnalyticsQueue] Enqueue warning: {e}")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns real-time queue observability metrics."""
        return {
            "queue_size": self._queue.qsize(),
            "total_enqueued": self.total_enqueued,
            "total_flushed": self.total_flushed,
            "total_batches": self.total_batches,
            "last_flush_time": self.last_flush_time,
            "is_worker_running": self._running,
        }


    async def _process_queue(self):
        buffer: List[Dict[str, Any]] = []
        last_flush = time.time()

        while self._running:
            try:
                try:
                    # Wait for items with timeout
                    item = await asyncio.wait_for(self._queue.get(), timeout=self.flush_interval)
                    buffer.append(item)
                    self._queue.task_done()
                except asyncio.TimeoutError:
                    pass

                now = time.time()
                if buffer and (len(buffer) >= self.batch_size or (now - last_flush) >= self.flush_interval):
                    await self._flush_batch(buffer)
                    buffer = []
                    last_flush = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AnalyticsQueue] Error in worker loop: {e}")
                await asyncio.sleep(1)

    async def _flush_remaining(self):
        buffer = []
        while not self._queue.empty():
            try:
                buffer.append(self._queue.get_nowait())
                self._queue.task_done()
            except Exception:
                break
        if buffer:
            await self._flush_batch(buffer)

    async def _flush_batch(self, events: List[Dict[str, Any]]):
        """Flushes buffered events in atomic Firestore batches."""
        if not events:
            return

        try:
            # Run blocking Firestore batch operations in threadpool
            await asyncio.to_thread(self._sync_flush, events)
            self.total_flushed += len(events)
            self.total_batches += 1
            self.last_flush_time = datetime.utcnow().isoformat()
        except Exception as e:
            print(f"[AnalyticsQueue] Failed to flush click batch: {e}")


    def _sync_flush(self, events: List[Dict[str, Any]]):
        # Aggregate clicks per short_code for parent document update
        clicks_by_code = defaultdict(int)
        for ev in events:
            clicks_by_code[ev["code"]] += 1

        batch = db.batch()
        batch_count = 0

        # 1. Update parent link click counts
        for code, count in clicks_by_code.items():
            doc_ref = db.collection("urls").document(code)
            batch.update(doc_ref, {"clicks": gcf.Increment(count)})
            batch_count += 1

        # 2. Insert detailed click entries
        for ev in events:
            code = ev["code"]
            click_ref = db.collection("urls").document(code).collection("clicks").document()
            click_data = {
                "timestamp": ev.get("timestamp", datetime.utcnow().isoformat()),
                "referrer": ev.get("referrer", "Direct"),
                "browser": ev.get("browser", "Unknown"),
                "device": ev.get("device", "Unknown"),
                "os": ev.get("os", "Unknown"),
                "ip_hash": ev.get("ip_hash", "")
            }
            batch.set(click_ref, click_data)
            batch_count += 1

            if batch_count >= 400:  # Firestore limit is 500 ops per batch
                batch.commit()
                batch = db.batch()
                batch_count = 0

        if batch_count > 0:
            batch.commit()


analytics_queue = AsyncAnalyticsQueue()
