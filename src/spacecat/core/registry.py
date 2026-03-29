"""
This module provides a registry for the core services of the bot.

The `ServiceRegistry` class acts as a central point of access for the
bot's various services, such as the task scheduler, reminder scheduler,
and task service. It provides properties for accessing the various
services and ensures that the services are initialized in the correct
order.
"""

from spacecat.core.automation.reminder_service import ReminderService
from spacecat.core.automation.scheduler import BaseScheduler
from spacecat.core.automation.task_service import TaskService
from spacecat.core.interfaces import BaseDispatcher


class ServiceRegistry:
    """
    The central point of access for the bot's various services.

    It provides properties for accessing the various services and
    ensures that the services are initialized in the correct order.

    Attributes:
        _tasks (TaskService | None): The task service instance.
        _reminders (ReminderService | None): The reminder service
            instance.
        _task_scheduler (BaseScheduler | None): The task scheduler
            instance.
        _reminder_scheduler (BaseScheduler | None): The reminder
            scheduler instance.
    """

    # Services
    _tasks: TaskService | None = None
    _reminders: ReminderService | None = None

    # Schedulers
    _task_scheduler: BaseScheduler | None = None
    _reminder_scheduler: BaseScheduler | None = None

    @classmethod
    def initialize(cls, dispatcher: BaseDispatcher) -> None:
        """Initializes all singletons in the correct dependency order."""
        # 1. Initialize Services first
        cls._tasks = TaskService(dispatcher)
        cls._reminders = ReminderService(dispatcher)

        # 2. Initialize Schedulers using the Services
        cls._task_scheduler = BaseScheduler(cls._tasks, check_interval=60)
        cls._reminder_scheduler = BaseScheduler(cls._reminders, check_interval=60)

    @classmethod
    def start_all(cls) -> None:
        """Starts the background loops for all schedulers."""
        if cls._task_scheduler:
            cls._task_scheduler.start()
        if cls._reminder_scheduler:
            cls._reminder_scheduler.start()

    @classmethod
    async def stop_all(cls) -> None:
        """Gracefully shuts down all schedulers."""
        if cls._task_scheduler:
            await cls._task_scheduler.stop()
        if cls._reminder_scheduler:
            await cls._reminder_scheduler.stop()

    @classmethod
    def tasks(cls) -> TaskService:
        """Get the task service instance.

        Returns:
            TaskService: The task service instance.
        """
        if cls._tasks is None:
            raise RuntimeError("ServiceRegistry not initialized! Call initialize() first.")
        return cls._tasks

    @classmethod
    def reminders(cls) -> ReminderService:
        """Get the reminder service instance.

        Returns:
            ReminderService: The reminder service instance.
        """
        if cls._reminders is None:
            raise RuntimeError("ServiceRegistry not initialized! Call initialize() first.")
        return cls._reminders

    @classmethod
    def task_scheduler(cls) -> BaseScheduler:
        """Get the task scheduler instance.

        Returns:
            BaseScheduler: The task scheduler instance.
        """
        return cls._task_scheduler

    @classmethod
    def reminder_scheduler(cls) -> BaseScheduler:
        """Get the reminder scheduler instance.

        Returns:
            BaseScheduler: The reminder scheduler instance.
        """
        return cls._reminder_scheduler
