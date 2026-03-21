"""
Reminder Data Models and Scheduling Definitions.

This module defines the persistence layer for the automation system's
reminders. It includes the `Reminder` Tortoise-ORM model, which
manages the state, timing, and recurrence logic for scheduled reminders
within the bot.
"""

import time
import uuid

from tortoise import fields, models


class Reminder(models.Model):
    """
    A representation of a Reminder.

    This class holds information required about a reminder, such as the
    user, guild/server, channel, message, and dispatch time.
    """

    # Primary Key
    id = fields.UUIDField(pk=True)

    # Use BigIntField for Discord IDs (Snowflakes)
    user_id = fields.BigIntField(index=True)
    guild_id = fields.BigIntField(index=True)
    channel_id = fields.BigIntField()
    message_id = fields.BigIntField()

    # Use BigIntField for Unix Timestamps
    creation_time = fields.BigIntField()
    dispatch_time = fields.BigIntField(index=True)

    message = fields.TextField()

    class Meta:
        """Metadata for the Reminder model."""

        table = "reminders"

    @classmethod
    async def create_new(
        cls,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        dispatch_time: int,
        message: str,
    ) -> "Reminder":
        """
        Create and persists a new reminder.

        Args:
            user_id: The id of the user creating the reminder.
            guild_id: The id of the guild where the reminder is being
                created.
            channel_id: The id of the channel the reminder is going to
                be sent in.
            message_id: The id of the original message that created the
                reminder.
            dispatch_time: The timestamp when the reminder should be
                dispatched.
            message: The message content of the reminder.

        Returns:
            Reminder: The created reminder.
        """
        return await cls.create(
            id=uuid.uuid4(),
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            creation_time=int(time.time()),
            dispatch_time=dispatch_time,
            message=message,
        )

    @classmethod
    async def get_upcoming(cls, time_limit: int = 300) -> list["Reminder"]:
        """
        Retrieves reminders due within the next X seconds.

        Args:
            time_limit: The time limit in seconds.

        Returns:
            A list of reminders that are due within the next X seconds.
        """
        now = int(time.time())
        return await cls.filter(
            dispatch_time__lte=now + time_limit,
            dispatch_time__gte=now - 60,  # Catch any slightly missed items
        ).order_by("dispatch_time")
