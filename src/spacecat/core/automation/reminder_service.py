"""
This provides the core functionality for the bot's reminder scheduler.

It defines the `ReminderService` class, which is responsible for
managing and executing triggered reminders. This includes creating and
managing `Reminder` instances, as well as handling their execution and
dispatch.

The `ReminderService` is designed to be used as a singleton and is
intended to be a central component of the bot's automation system.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from spacecat.core.models.reminders import Reminder

if TYPE_CHECKING:
    from spacecat.core.interfaces import BaseDispatcher

logger = logging.getLogger(__name__)

FIVE_MINUTES_IN_SECONDS = 300


class ReminderService:
    """
    Service for managing reminders.

    This class handles the lifecycle of one-off notifications, ensuring
    they are dispatched and then cleaned up from the database.
    """

    def __init__(self, dispatcher: BaseDispatcher) -> None:
        """
        Initializes a new ReminderService instance.

        Args:
            dispatcher: The dispatcher instance.
        """
        self.dispatcher = dispatcher

    async def get_upcoming(self, time_limit: int = FIVE_MINUTES_IN_SECONDS) -> list[Reminder]:
        """Gets upcoming reminders within the time limit.

        Args:
            time_limit: The time limit in seconds.

        Returns:
            A list of upcoming reminders.
        """
        current_time = int(time.time())
        return await Reminder.filter(dispatch_time=current_time + time_limit).order_by(
            "dispatch_time"
        )

    async def dispatch(self, reminder: Reminder) -> None:
        """
        The core execution flow for a triggered reminder.

        Unlike Events, Reminders are 'fire and forget'. We dispatch
        the message and immediately delete the record.

        Args:
            reminder: The reminder to dispatch.
        """
        try:
            # Delegate the actual sending to the bot interface
            await self.dispatcher.dispatch_reminder(
                reminder.channel_id, reminder.message_id, reminder.message
            )
        except (ConnectionError, TimeoutError, OSError):
            logger.exception("Error dispatching reminder %s", reminder.id)
        finally:
            # Reminders are one-off, so we remove them regardless of success
            await self.remove_reminder(reminder)

    async def remove_reminder(self, reminder: Reminder) -> None:
        """
        Removes a reminder from the database.

        Args:
            reminder: The reminder to remove.
        """
        await reminder.delete()

    async def create_reminder(
        self,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        dispatch_time: int,
        message: str,
    ) -> Reminder:
        """Create a new reminder.

        Args:
            user_id: The ID of the user creating the reminder.
            guild_id: The ID of the guild where the reminder was created.
            channel_id: The ID of the channel where the reminder was created.
            message_id: The ID of the message that triggered the reminder.
            dispatch_time: Unix timestamp when the reminder should be dispatched.
            message: The reminder message content.

        Returns:
            The newly created Reminder instance.
        """
        return await Reminder.create_new(
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            dispatch_time=dispatch_time,
            message=message,
        )
