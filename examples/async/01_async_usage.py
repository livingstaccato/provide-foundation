#!/usr/bin/env python3
# examples/foundation_telemetry/09_async_usage.py
"""Demonstrates using Foundation Telemetry in asynchronous applications."""

import asyncio
from pathlib import Path
import sys

# Add src to path for examples
example_file = Path(__file__).resolve()
project_root = example_file.parent.parent.parent  # Go up from examples to project root
# Line removed - project_root already set above
src_path = project_root / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from provide.foundation import (  # noqa: E402
    logger,
    setup_telemetry,
    shutdown_foundation_telemetry,
)
from provide.foundation.console.output import pout  # noqa: E402


async def example_9_async_usage() -> None:
    """
    Example 9: Demonstrates usage in asynchronous (`asyncio`) contexts.

    Covers logging from async functions and using the `shutdown_foundation_telemetry`
    async function.
    """
    pout("\n" + "=" * 60)
    pout("⚡ Example 9: Async Usage")
    pout(" Demonstrates: Logging from asyncio tasks and async shutdown.")
    pout("=" * 60)

    setup_telemetry()  # Default configuration

    async def async_task(task_id: int) -> None:
        task_logger = logger.get_logger(f"async_task.{task_id}")
        task_logger.info("Async task started", task_id=task_id)
        await asyncio.sleep(0.01)  # Simulate async work
        task_logger.debug("Async task processing step 1", progress=50)
        await asyncio.sleep(0.01)
        task_logger.info("Async task completed", task_id=task_id, duration_ms=20)

    # Run multiple async tasks concurrently
    await asyncio.gather(
        async_task(1),
        async_task(2),
    )

    # Demonstrate async shutdown (currently logs a message)
    logger.info("Initiating telemetry shutdown...")
    await shutdown_foundation_telemetry(timeout_millis=100)
    logger.info(
        "Message after shutdown call (may use fallback if shutdown was destructive)"
    )


if __name__ == "__main__":
    asyncio.run(example_9_async_usage())
    pout("\n✅ Example 9 completed.")
