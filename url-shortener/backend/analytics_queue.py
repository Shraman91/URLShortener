import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict
from google.cloud import firestore as gcf
from google.api_core.exceptions import NotFound

from firebase import db


class AsyncAnalyticsQueue:
    def __init__(self, batch_size: int = 50, flush_interval: float = 2.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
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
            await self._flush_remaining()
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            print("[AnalyticsQueue] Worker stopped and buffer flushed.")

    def enqueue(self, event: Dict[str, Any]):
        try:
            self._queue.put_nowait(event)
            self.total_enqueued += 1
        except Exception as e:
            print(f"[AnalyticsQueue] Enqueue warning: {e}")

    def get_queue_stats(self) -> Dict[str, Any]:
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
                await asyncio.sleep(0.5)

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
        if not events:
            return

        try:
            await asyncio.to_thread(self._sync_flush, events)
            self.total_flushed += len(events)
            self.total_batches += 1
            self.last_flush_time = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            print(f"[AnalyticsQueue] Failed to flush click batch: {e}")

    def _sync_flush(self, events: List[Dict[str, Any]]):
        clicks_by_code = defaultdict(int)
        for ev in events:
            clicks_by_code[ev["code"]] += 1

        batch = db.batch()
        batch_count = 0

        for code, count in clicks_by_code.items():
            doc_ref = db.collection("urls").document(code)
            batch.set(doc_ref, {"clicks": gcf.Increment(count)}, merge=True)
            batch_count += 1

        now_str = datetime.now(timezone.utc).isoformat()
        for ev in events:
            code = ev["code"]
            click_ref = db.collection("urls").document(code).collection("clicks").document()
            click_data = {
                "timestamp": ev.get("timestamp", now_str),
                "referrer": ev.get("referrer", "Direct"),
                "browser": ev.get("browser", "Unknown"),
                "device": ev.get("device", "Unknown"),
                "os": ev.get("os", "Unknown"),
                "ip_hash": ev.get("ip_hash", "")
            }
            batch.set(click_ref, click_data)
            batch_count += 1

            if batch_count >= 400:
                try:
                    batch.commit()
                except Exception as ex:
                    print(f"[AnalyticsQueue] Batch commit error: {ex}")
                batch = db.batch()
                batch_count = 0

        if batch_count > 0:
            try:
                batch.commit()
            except Exception as ex:
                print(f"[AnalyticsQueue] Final batch commit error: {ex}")


analytics_queue = AsyncAnalyticsQueue()
