"""
This provides the core functionality for the bot's event scheduler.

It defines the `EventService` class, which is responsible for managing
and executing scheduled events. This includes creating and managing
`Event` instances, as well as handling their execution and dispatch.

The `EventService` is designed to be used as a singleton and is
intended to be a central component of the bot's automation system.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from spacecat.core.models.actions import Action
from spacecat.core.models.events import Event, Repeat

if TYPE_CHECKING:
    from spacecat.core.interfaces import BotInterface

FIVE_MINUTES_IN_SECONDS = 300


class EventService:
    """
    Service for managing events and their actions.

    This class provides high-level operations for event management,
    including action execution and event lifecycle management.
    """

    def __init__(self, bot: BotInterface) -> None:
        """
        Initializes a new EventService instance.

        Args:
            bot: The bot instance implementing BotInterface.
        """
        self.bot = bot

    async def dispatch(self, event: Event) -> None:
        """
        The core execution flow for a triggered event.

        This method is called by the Scheduler. It handles the 'Business
        Rules' of firing actions and rescheduling the event if it is
        repeating.
        """
        try:
            # 1. Execute the payload
            await self.execute_actions(event)

            # 2. Update state for record keeping
            now = int(time.time())
            event.last_run_time = now

            # 3. Handle Recurrence (The Business Policy)
            if event.repeat_interval != Repeat.No and not event.is_paused:
                # Use the model's logic to find the next timestamp
                event.dispatch_time = event.get_next_run_timestamp()
            else:
                # If not repeating, we pause it so it doesn't fire again
                event.is_paused = True

            await event.save()

        except Exception as e:
            # In production, swap this for a proper logger
            print(f"Critical error during dispatch of Event {event.id}: {e}")

    async def execute_actions(self, event: Event) -> None:
        """Fetch and run all enabled actions for an event.

        Args:
            event: The event to execute actions for.
        """
        # Use select_related or similar if needed, but Tortoise filter is fine here
        actions = await event.actions.filter(is_enabled=True)

        for action in actions:
            try:
                # We pass the agnostic bot interface to the action
                await action.run(self.bot)
            except Exception as e:
                print(f"Error executing action {action.id} ({action.action_type}): {e}")

    async def get_upcoming_events(self, time_limit: int = FIVE_MINUTES_IN_SECONDS) -> list[Event]:
        """
        Gets upcoming events within the time limit.

        Used by the Scheduler to populate its task queue.

        Args:
            time_limit: The maximum time in seconds to look ahead.

        Returns:
            A list of upcoming events.
        """
        current_time = int(time.time())
        return await Event.filter(
            dispatch_time__lte=current_time + time_limit, is_paused=False
        ).order_by("dispatch_time")

    async def add_action(self, event: Event, action_type: str, config: dict) -> Action:
        """Add a new action to an event.

        Args:
            event: The event to add the action to.
            action_type: The type of action to add.
            config: The configuration for the action.

        Returns:
            The created action.
        """
        return await Action.create(event=event, action_type=action_type, data=config)

    async def get_actions(self, event: Event) -> list[Action]:
        """Gets all actions for an event.

        Args:
            event: The event to get actions for.

        Returns:
            A list of actions associated with the event.
        """
        return await event.actions.all()

    async def update_event(self, event: Event, **kwargs: dict[str, Any]) -> None:
        """Updates event attributes and saves to DB.

        Args:
            event: The event to update.
            **kwargs: Keyword arguments for updating event attributes.
        """
        await event.update_from_dict(kwargs).save()

    async def remove_event(self, event: Event) -> None:
        """Remove an event and all its actions.

        Args:
            event: The event to remove.
        """
        await event.delete()
