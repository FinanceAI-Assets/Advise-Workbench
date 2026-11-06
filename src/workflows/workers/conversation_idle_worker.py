"""Background worker for conversation idle detection and summary generation.

Runs periodically (every 2 minutes) to:
1. Detect idle engagement sessions
2. Generate summaries
3. Persist summaries to database
"""

import asyncio
import logging
import threading
from typing import Optional

from src.core.db.session import SessionLocal
from src.workflows.conversation_summary_worker import check_idle_engagements_and_summarize

logger = logging.getLogger(__name__)

_idle_detection_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _idle_detection_loop() -> None:
    """Main loop for idle detection background task.

    Runs every 2 minutes to detect idle engagements and generate summaries.
    Uses per-tick event loop pattern (asyncio.new_event_loop) for thread-safe async execution.
    """
    logger.info("Starting conversation idle detection worker")

    while not _stop_event.is_set():
        try:
            # Wait 2 minutes or until stopped
            if _stop_event.wait(120):
                break

            # Run idle detection task with fresh event loop (per-tick pattern)
            db = SessionLocal()
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(check_idle_engagements_and_summarize(db))
                    if result.get("summaries_generated", 0) > 0:
                        logger.info(f"Idle detection: {result['summaries_generated']} summaries generated")
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Error in idle detection task: {e}", exc_info=True)
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Unexpected error in idle detection loop: {e}", exc_info=True)
            # Continue running even if there's an error
            if not _stop_event.is_set():
                _stop_event.wait(60)  # Wait 1 min before retrying


def start_idle_detection_worker() -> None:
    """Start the idle detection background worker thread."""
    global _idle_detection_thread

    if _idle_detection_thread is not None and _idle_detection_thread.is_alive():
        logger.warning("Idle detection worker already running")
        return

    _stop_event.clear()
    _idle_detection_thread = threading.Thread(
        target=_idle_detection_loop,
        daemon=True,
        name="conversation-idle-detection"
    )
    _idle_detection_thread.start()
    logger.info("Conversation idle detection worker started")


def stop_idle_detection_worker(timeout_sec: int = 10) -> None:
    """Stop the idle detection background worker thread.

    Args:
        timeout_sec: Timeout to wait for thread to finish
    """
    global _idle_detection_thread

    if _idle_detection_thread is None or not _idle_detection_thread.is_alive():
        logger.debug("Idle detection worker not running")
        return

    logger.info("Stopping conversation idle detection worker")
    _stop_event.set()
    _idle_detection_thread.join(timeout=timeout_sec)

    if _idle_detection_thread.is_alive():
        logger.warning(f"Idle detection worker did not stop within {timeout_sec}s")
    else:
        logger.info("Conversation idle detection worker stopped")
