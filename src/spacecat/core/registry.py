"""
This module provides a registry for the core services of the bot.

The `ServiceRegistry` class acts as a central point of access for the
bot's various services, such as the event scheduler, reminder scheduler,
and event service. It provides properties for accessing the various
services and ensures that the services are initialized in the correct
order.
"""

from spacecat.core.automation.event_service import EventService
from spacecat.core.automation.reminder_service import ReminderService
from spacecat.core.automation.scheduler import BaseScheduler
from spacecat.core.interfaces import BaseDispatcher


class ServiceRegistry:
    """
    The central point of access for the bot's various services.

    It provides properties for accessing the various services and
    ensures that the services are initialized in the correct order.

    Attributes:
        _events (EventService | None): The event service instance.
        _reminders (ReminderService | None): The reminder service
            instance.
        _event_scheduler (BaseScheduler | None): The event scheduler
            instance.
        _reminder_scheduler (BaseScheduler | None): The reminder
            scheduler instance.
    """

    # Services
    _events: EventService | None = None
    _reminders: ReminderService | None = None

    # Schedulers
    _event_scheduler: BaseScheduler | None = None
    _reminder_scheduler: BaseScheduler | None = None

    @classmethod
    def initialize(cls, dispatcher: BaseDispatcher) -> None:
        """Initializes all singletons in the correct dependency order."""
        # 1. Initialize Services first
        cls._events = EventService(dispatcher)
        cls._reminders = ReminderService(dispatcher)

        # 2. Initialize Schedulers using the Services
        cls._event_scheduler = BaseScheduler(cls._events, check_interval=60)
        cls._reminder_scheduler = BaseScheduler(cls._reminders, check_interval=60)

    @classmethod
    def start_all(cls) -> None:
        """Starts the background loops for all schedulers."""
        if cls._event_scheduler:
            cls._event_scheduler.start()
        if cls._reminder_scheduler:
            cls._reminder_scheduler.start()

    @classmethod
    async def stop_all(cls) -> None:
        """Gracefully shuts down all schedulers."""
        if cls._event_scheduler:
            await cls._event_scheduler.stop()
        if cls._reminder_scheduler:
            await cls._reminder_scheduler.stop()

    @classmethod
    def events(cls) -> EventService:
        """Get the event service instance.

        Returns:
            EventService: The event service instance.
        """
        if cls._events is None:
            raise RuntimeError("ServiceRegistry not initialized! Call initialize() first.")
        return cls._events

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
    def event_scheduler(cls) -> BaseScheduler:
        """Get the event scheduler instance.

        Returns:
            BaseScheduler: The event scheduler instance.
        """
        return cls._event_scheduler

    @classmethod
    def reminder_scheduler(cls) -> BaseScheduler:
        """Get the reminder scheduler instance.

        Returns:
            BaseScheduler: The reminder scheduler instance.
        """
        return cls._reminder_scheduler
