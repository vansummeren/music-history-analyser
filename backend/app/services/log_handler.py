"""Thread-safe logging handler that writes records to the app_logs DB table.

Design
------
* ``emit()`` is called from any thread/context and places the record in an
  in-memory ``queue.Queue`` without blocking.
* A daemon thread owns a dedicated asyncio event loop and flushes the queue
  to the database every ``_FLUSH_INTERVAL`` seconds.
* If the database is unavailable the handler silently drops the records for
  that flush cycle — it never raises, so it cannot disrupt the application.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import threading
import traceback
from datetime import UTC, datetime

_FLUSH_INTERVAL = 5.0   # seconds between DB flush cycles
_MAX_QUEUE_SIZE = 10_000  # maximum buffered records (drops on overflow)
_BATCH_SIZE = 200         # maximum records written per flush cycle

logger = logging.getLogger(__name__)


class DatabaseLogHandler(logging.Handler):
    """Async-safe logging handler that persists records to ``app_logs``."""

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[logging.LogRecord] = queue.Queue(
            maxsize=_MAX_QUEUE_SIZE
        )
        self._thread = threading.Thread(
            target=self._worker_thread,
            name="db-log-flusher",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # logging.Handler interface
    # ------------------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(record)

    # ------------------------------------------------------------------
    # Background flush thread
    # ------------------------------------------------------------------

    def _worker_thread(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_flush_loop())

    async def _async_flush_loop(self) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.config import settings
        from app.models.app_log import AppLog

        engine = create_async_engine(
            settings.database_url,
            echo=False,
            # Keep a minimal pool for the log writer thread
            pool_size=1,
            max_overflow=1,
        )
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        while True:
            await asyncio.sleep(_FLUSH_INTERVAL)

            # Drain up to _BATCH_SIZE records from the queue
            records: list[logging.LogRecord] = []
            try:
                while len(records) < _BATCH_SIZE:
                    records.append(self._queue.get_nowait())
            except queue.Empty:
                pass

            if not records:
                continue

            try:
                async with SessionLocal() as db:
                    for record in records:
                        message = record.getMessage()
                        if record.exc_info:
                            message += "\n" + "".join(
                                traceback.format_exception(*record.exc_info)
                            )
                        db.add(
                            AppLog(
                                created_at=datetime.fromtimestamp(
                                    record.created, tz=UTC
                                ),
                                level=record.levelname,
                                service=settings.service_name,
                                logger_name=record.name,
                                message=message,
                            )
                        )
                    await db.commit()
            except Exception:  # noqa: BLE001
                # Never let log-writing failures surface to the application.
                pass
