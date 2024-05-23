"""
Action of "VoiceKick" type, used for kicking users from a voice channel.

This incorporates an override for a VoiceKick action as well as an
sqlite repository to store the associated data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self, override

from spacecat.modules.automation.event_scheduler import Action, ActionRepository

if TYPE_CHECKING:
    import sqlite3


class VoiceKickAction(Action):
    """Represents an action that kicks a user from a voice channel."""

    def __init__(self: VoiceKickAction, id_: uuid.UUID, voice_channel_id: int) -> None:
        """
        Initializes a new instance of the VoiceKickAction class.

        Args:
            id_ (uuid.UUID): The unique identifier of the action.
            voice_channel_id (int): The ID of the voice channel.
        """
        super().__init__(id_)
        self.voice_channel_id = voice_channel_id

    @classmethod
    def create_new(cls: type[VoiceKickAction], voice_channel_id: int) -> VoiceKickAction:
        """
        Create a new instance of the VoiceKickAction class.

        Args:
            voice_channel_id (int): The ID of the voice channel.

        Returns:
            VoiceKickAction: A new instance of the VoiceKickAction class.
        """
        return cls(uuid.uuid4(), voice_channel_id)

    @override
    def get_formatted_output(self: Self) -> str:
        return f"Kicks all users out of voice channel <#{self.voice_channel_id}>."

    @override
    def get_name() -> str:
        return "voice_kick"


class VoiceKickActionRepository(ActionRepository[VoiceKickAction]):
    """
    Repository for managing VoiceKickAction objects.

    This class provides methods for adding, removing, and retrieving
    VoiceKickAction objects from a database.
    """

    def __init__(self: VoiceKickActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a VoiceKickActionRepository instance.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS action_voice_kick "
            "(id TEXT PRIMARY KEY, voice_channel_id TEXT)"
        )
        self.db.commit()

    @override
    def get_by_id(self: Self, id_: uuid.UUID) -> VoiceKickAction | None:
        result = (
            self.db.cursor()
            .execute("SELECT * FROM action_voice_kick WHERE id=?", (str(id_),))
            .fetchone()
        )
        self.db.commit()
        return self._result_to_args(result)

    @override
    def add(self: Self, action: VoiceKickAction) -> None:
        values = (str(action.id), action.voice_channel_id)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO action_voice_kick VALUES (?, ?)", values)
        self.db.commit()

    @override
    def remove(self: Self, id_: uuid.UUID) -> None:
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM action_voice_kick WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result: tuple | None) -> VoiceKickAction | None:
        return VoiceKickAction(uuid.UUID(result[0]), result[1]) if result else None
