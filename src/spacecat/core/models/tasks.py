"""
Task Data Models and Scheduling Definitions.

This module defines the persistence layer for the automation system's
tasks. It includes the `Task` Tortoise-ORM model and the `Repeat`
enumeration, which together manage the state, timing, and recurrence
logic for scheduled tasks within the bot.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from spacecat.core.models.actions import Action


class Repeat(IntEnum):
    """
    Represents the time at which a task should be repeated.

    Attributes:
        No (int): No repeats will be set.
        Hourly (int): The task will be set to repeat every hour.
        Daily (int): The task will be set to repeat every day.
        Weekly (int): The task will be set to repeat every week.
    """

    No = 0
    Hourly = 3600
    Daily = 86400
    Weekly = 604800


class Task(models.Model):
    """
    A representation of a Task.

    This class holds information required about a task, such as the
    name and guild/server for access, as well as dispatch time and
    intervals to determine when to execute the actions.
    """

    id = fields.UUIDField(pk=True)
    guild_id = fields.BigIntField(index=True)
    dispatch_time = fields.BigIntField(null=True)
    last_run_time = fields.BigIntField(null=True)
    repeat_interval = fields.BigIntField(default=Repeat.No.value)
    repeat_multiplier = fields.IntField(default=1)
    name = fields.CharField(max_length=255)
    description = fields.TextField(default="")
    is_paused = fields.BooleanField(default=False)

    # Reverse relation from Action model's ForeignKey with related_name="actions"
    actions: fields.ReverseRelation[Action]

    class Meta:
        """Metadata for the Task model."""

        table = "tasks"

    @classmethod
    async def create_new(
        cls,
        guild_id: int,
        dispatch_time: int | None,
        repeat_interval: Repeat,
        repeat_multiplier: int,
        name: str,
        description: str = "",
    ) -> Task:
        """Create a new instance of a Task.

        Args:
            guild_id: The ID of the guild.
            dispatch_time: The time to dispatch the task, or None for manual-only tasks.
            repeat_interval: The interval in which the task should
                repeat its dispatch.
            repeat_multiplier: A multiplier value to affect the
                interval. (i.e. 2 on a Daily interval would double the
                interval to 2 days.)
            name: The name of the task.
            description: The description of the task.
                Defaults to "".

        Returns:
            Task: The created task.
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
