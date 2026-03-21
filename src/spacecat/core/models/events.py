"""
Event Data Models and Scheduling Definitions.

This module defines the persistence layer for the automation system's
events. It includes the `Event` Tortoise-ORM model and the `Repeat`
enumeration, which together manage the state, timing, and recurrence
logic for scheduled tasks within the bot.
"""

from enum import IntEnum

from tortoise import fields, models


class Repeat(IntEnum):
    """
    Represents the time at which an event should be repeated.

    Attributes:
        No (int): No repeats will be set.
        Hourly (int): The event will be set to repeat every hour.
        Daily (int): The event will be set to repeat every day.
        Weekly (int): The event will be set to repeat every week.
    """

    No = 0
    Hourly = 3600
    Daily = 86400
    Weekly = 604800


class Event(models.Model):
    """
    A representation of an Event.

    This class holds information required about an event, such as the
    name and guild/server for access, as well as dispatch time and
    intervals to determine when to execute the actions.
    """

    id = fields.UUIDField(pk=True)
    guild_id = fields.BigIntField(index=True)
    dispatch_time = fields.IntField()
    last_run_time = fields.IntField(null=True)
    repeat_interval = fields.IntEnumField(Repeat, default=Repeat.No)
    repeat_multiplier = fields.IntField(default=1)
    name = fields.CharField(max_length=255)
    description = fields.TextField(default="")
    is_paused = fields.BooleanField(default=False)

    class Meta:
        """Metadata for the Event model."""

        table = "events"

    @classmethod
    async def create_new(
        cls,
        guild_id: int,
        dispatch_time: int,
        repeat_interval: Repeat,
        repeat_multiplier: int,
        name: str,
        description: str = "",
    ) -> "Event":
        """Create a new instance of an Event.

        Args:
            guild_id: The ID of the guild.
            dispatch_time: The time to dispatch the event.
            repeat_interval: The interval in which the event should
                repeat its dispatch.
            repeat_multiplier: A multiplier value to affect the
                interval. (i.e. 2 on a Daily interval would double the
                interval to 2 days.)
            name: The name of the event.
            description: The description of the event.
                Defaults to "".

        Returns:
            Event: The created event.
        """
        return await cls.create(
            guild_id=guild_id,
            dispatch_time=dispatch_time,
            repeat_interval=repeat_interval,
            repeat_multiplier=repeat_multiplier,
            name=name,
            description=description,
        )

    def get_next_run_timestamp(self) -> int:
        """Calculates the next run time.

        Returns:
            The next run time as a timestamp.
        """
        if self.repeat_interval == Repeat.No:
            return self.dispatch_time

        base_time = self.last_run_time or self.dispatch_time
        interval_seconds = self.repeat_interval.value * self.repeat_multiplier
        return base_time + interval_seconds
