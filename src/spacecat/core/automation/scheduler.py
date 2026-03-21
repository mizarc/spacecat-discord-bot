"""
This provides the core functionality for the bot's task scheduler.

It defines the `BaseScheduler` class, which is responsible for managing
and executing scheduled tasks. This includes creating and managing
`Schedulable` instances, as well as handling their execution and
dispatch.

The `BaseScheduler` is designed to be used as a singleton and is
intended to be a central component of the bot's automation system.
"""

import asyncio
import time
from typing import Any, Protocol


class Schedulable(Protocol):
    """Interface for items that can be scheduled."""

    id: Any
    dispatch_time: int


class BaseScheduler:
    """Base scheduler class for handling scheduled tasks."""

    def __init__(self, service: Any, check_interval: int = 60):
        """Initialize the scheduler."""
        self.service = service
        self.interval = check_interval
        self.tasks: dict = {}
        self._main_task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Starts the scheduler without blocking the main thread."""
        if not self._running:
            self._running = True
            self._main_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Gracefully stops the scheduler and cancels pending runs."""
        self._running = False
        if self._main_task:
            self._main_task.cancel()

        # Cancel all pending event/reminder runs
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()

    async def schedule(self, item: Schedulable) -> None:
        """
        Add a new scheduled item to the scheduler to run later.

        Args:
            item: The item to schedule.
        """
        # If a task for this ID is already running, cancel it first (prevents duplicates)
        if item.id in self.tasks:
            self.tasks[item.id].cancel()

        delay = max(0.0, item.dispatch_time - time.time())
        # Start the tracking task immediately
        self.tasks[item.id] = asyncio.create_task(self._run(item, delay))

    def unschedule(self, item_id: Any) -> bool:
        """
        Removes a scheduled item by its ID to stop it from running.

        Args:
            item_id: The ID of the item to remove.

        Returns:
            bool: True if the item was removed, False otherwise.
        """
        task = self.tasks.pop(item_id, None)
        if task:
            task.cancel()
            return True
        return False

    async def _scheduler_loop(self) -> None:
        """The background pulse of the scheduler."""
        while self._running:
            try:
                # Ask the service for items due soon
                items = await self.service.get_upcoming()

                # Schedule new tasks that haven't been assigned yet
                for item in items:
                    existing_task = self.tasks.get(item.id)
                    if existing_task is None or existing_task.done():
                        delay = max(0, item.dispatch_time - time.time())
                        self.tasks[item.id] = asyncio.create_task(self._run(item, delay))

                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log the error and wait before retrying
                print(f"Scheduler Loop Error: {e}")
                await asyncio.sleep(10)

    async def _run(self, item: Schedulable, delay: float) -> None:
        """Run a scheduled item."""
        try:
            await asyncio.sleep(delay)
            await self.service.dispatch(item)
        except asyncio.CancelledError:
            pass  # Task was cancelled (event deleted/paused)
        except Exception as e:
            print(f"Dispatch Error for {item.id}: {e}")
        finally:
            # Clean up the reference so it can be re-scheduled if repeating
            self.tasks.pop(item.id, None)
