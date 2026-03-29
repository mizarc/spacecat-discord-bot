"""
Task Data Models and Scheduling Definitions.

This module defines the persistence layer for the automation system's
tasks. It includes the `Task` Tortoise-ORM model and the `Repeat`
enumeration, which together manage the state, timing, and recurrence
logic for scheduled tasks within the bot.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from tortoise import fields, models

if TYPE_CHECKING:
    from spacecat.core.models.actions import Action


class Repeat(StrEnum):
    """Supported intervals for task recurrence."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NONE = "no"


class Task(models.Model):
    """
    A representation of a Task.

    This class holds information required about a task, such as the
    name and guild/server for access, as well as dispatch time and
    intervals to determine when to execute the actions.
    """

    id = fields.UUIDField(pk=True)
    guild_id = fields.BigIntField(index=True)
    dispatch_time = fields.DatetimeField(null=True, index=True)
    last_run_time = fields.DatetimeField(null=True, index=True)
    repeat_interval = fields.TextField(default=Repeat.NONE)
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

    def get_next_run_time(self) -> datetime.datetime:
        """
        Calculates the next run time using calendar-aware math.

        Returns:
            datetime: The next calculated UTC dispatch time.
        """
        # We calculate based on when it SHOULD have run to prevent drift
        base_dt = self.dispatch_time or datetime.datetime.now(datetime.UTC)
        mult = self.repeat_multiplier or 1

        mapping = {
            Repeat.HOURLY: {"hours": mult},
            Repeat.DAILY: {"days": mult},
            Repeat.WEEKLY: {"weeks": mult},
            Repeat.MONTHLY: {"months": mult},
            Repeat.YEARLY: {"years": mult},
        }

        if self.repeat_interval not in mapping:
            return base_dt

        # relativedelta handles the varying lengths of months/years automatically
        delta = relativedelta(**mapping[self.repeat_interval])
        return base_dt + delta
