"""
This provides the core functionality for the bot's task scheduler.

It defines the `TaskService` class, which is responsible for managing
and executing scheduled tasks. This includes creating and managing
`Task` instances, as well as handling their execution and dispatch.

The `TaskService` is designed to be used as a singleton and is
intended to be a central component of the bot's automation system.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from spacecat.core.models.actions import Action
from spacecat.core.models.tasks import Repeat, Task

if TYPE_CHECKING:
    from spacecat.core.interfaces import BaseDispatcher

FIVE_MINUTES_IN_SECONDS = 300


class TaskService:
    """
    Service for managing tasks and their actions.

    This class provides high-level operations for task management,
    including action execution and task lifecycle management.
    """

    def __init__(self, dispatcher: BaseDispatcher) -> None:
        """
        Initializes a new TaskService instance.

        Args:
            dispatcher: The dispatcher to use for dispatching actions.
        """
        self.dispatcher = dispatcher

    async def dispatch(self, task: Task) -> None:
        """
        The core execution flow for a triggered task.

        This method is called by the Scheduler. It handles the 'Business
        Rules' of firing actions and rescheduling the task if it is
        repeating.
        """
        try:
            # 1. Execute the payload
            await self.execute_actions(task)

            # 2. Update state for record keeping
            now = int(time.time())
            task.last_run_time = now

            # 3. Handle Recurrence (The Business Policy)
            if task.repeat_interval != Repeat.No and not task.is_paused:
                # Use the model's logic to find the next timestamp
                task.dispatch_time = task.get_next_run_timestamp()
            else:
                # If not repeating, we pause it so it doesn't fire again
                task.is_paused = True

            await task.save()

        except (OSError, ValueError, RuntimeError) as error:
            # In production, swap this for a proper logger
            print(f"Critical error during dispatch of Task {task.id}: {error}")

    async def execute_actions(self, task: Task) -> None:
        """Fetch and run all enabled actions for a task.

        Args:
            task: The task to execute actions for.
        """
        # Use select_related or similar if needed, but Tortoise filter is fine here
        actions = await task.actions.filter(is_enabled=True)

        for action in actions:
            try:
                # We pass the agnostic bot interface to the action
                await action.run(self.dispatcher)
            except (OSError, ValueError, RuntimeError) as error:
                print(f"Error executing action {action.id} ({action.action_type}): {error}")

    async def get_upcoming(self, time_limit: int = FIVE_MINUTES_IN_SECONDS) -> list[Task]:
        """
        Gets upcoming tasks within the time limit.

        Used by the Scheduler to populate its task queue.

        Args:
            time_limit: The maximum time in seconds to look ahead.

        Returns:
            A list of upcoming tasks.
        """
        current_time = int(time.time())
        return await Task.filter(
            dispatch_time__lte=current_time + time_limit, is_paused=False
        ).order_by("dispatch_time")

    async def add_action(self, task: Task, action_type: str, config: dict) -> Action:
        """Add a new action to a task.

        Args:
            task: The task to add the action to.
            action_type: The type of action to add.
            config: The configuration for the action.

        Returns:
            The created action.
        """
        return await Action.create(task=task, action_type=action_type, data=config)

    async def get_actions(self, task: Task) -> list[Action]:
        """Gets all actions for a task.

        Args:
            task: The task to get actions for.

        Returns:
            A list of actions associated with the task.
        """
        return await task.actions.all()

    async def update_task(self, task: Task, **kwargs: dict[str, Any]) -> None:
        """Updates task attributes and saves to DB.

        Args:
            task: The task to update.
            **kwargs: Keyword arguments for updating task attributes.
        """
        await task.update_from_dict(kwargs).save()

    async def remove_task(self, task: Task) -> None:
        """Remove a task and all its actions.

        Args:
            task: The task to remove.
        """
        await task.delete()
