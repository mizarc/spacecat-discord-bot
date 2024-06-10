"""
Action of "VoiceMove" type, used for moving users to a voice channel.

This incorporates an override for a VoiceMove action as well as an
sqlite repository to store the associated data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self, override

from spacecat.modules.automation.event_scheduler import Action, ActionRepository

if TYPE_CHECKING:
    import sqlite3


class VoiceMoveAction(Action):
    """Represents an action that moves users to a voice channel."""

    def __init__(
        self: VoiceMoveAction,
        id_: uuid.UUID,
        current_voice_channel_id: int,
        new_voice_channel_id: int,
    ) -> None:
        """
        Initializes a new instance of the VoiceMoveAction class.

        Args:
            id_ (uuid.UUID): The unique identifier for the action.
            current_voice_channel_id (int): The ID of the current voice channel.
            new_voice_channel_id (int): The ID of the new voice channel.
        """
        super().__init__(id_)
        self.current_voice_channel_id = current_voice_channel_id
        self.new_voice_channel_id = new_voice_channel_id

    @classmethod
    def create_new(
        cls: type[VoiceMoveAction], current_voice_channel_id: int, new_voice_channel_id: int
    ) -> VoiceMoveAction:
        """
        Create a new instance of the VoiceMoveAction class.

        Parameters:
            current_voice_channel_id (int): The ID of the voice channel
                to move users from.
            new_voice_channel_id (int): The ID of the new voice channel
                to move users to.

        Returns:
            VoiceMoveAction: A new instance of the VoiceMoveAction
                class.
        """
        return cls(uuid.uuid4(), current_voice_channel_id, new_voice_channel_id)

    @override
    def get_formatted_output(self: Self) -> str:
        return (
            f"Moves all users from voice channel "
            f"<#{self.current_voice_channel_id}> to <#{self.new_voice_channel_id}>."
        )

    @override
    def get_name() -> str:
        return "voice_move"


class VoiceMoveActionRepository(ActionRepository[VoiceMoveAction]):
    """
    Repository for managing VoiceMoveAction objects.

    This class provides methods for adding, removing, and retrieving
    VoiceMoveAction objects from a database.
    """

    def __init__(self: VoiceMoveActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a VoiceMoveActionRepository instance.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS action_voice_move "
            "(id TEXT PRIMARY KEY, current_voice_channel_id INTEGER, new_voice_channel_id INTEGER)"
        )
        self.db.commit()

    def get_by_id(self: Self, id_: uuid.UUID) -> VoiceMoveAction | None:
        """
        Retrieves a VoiceMoveAction by ID.

        Args:
            id_ (uuid.UUID): The unique identifier of the VoiceMoveAction object.

        Returns:
            VoiceMoveAction | None: The VoiceMoveAction object with the specified identifier,
            or None if the object is not found.
        """
        result = (
            self.db.cursor()
            .execute("SELECT * FROM action_voice_move WHERE id=?", (str(id_),))
            .fetchone()
        )
        self.db.commit()
        return self._result_to_args(result)

    def add(self: Self, action: VoiceMoveAction) -> None:
        """
        Adds a VoiceMoveAction to the database.

        Args:
            action (VoiceMoveAction): The VoiceMoveAction object to be added.
        """
        values = (str(action.id), action.current_voice_channel_id, action.new_voice_channel_id)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO action_voice_move VALUES (?, ?, ?)", values)
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove a record by a given ID.

        Parameters:
            id_ (uuid.UUID): The ID of the record to be removed.
        """
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM action_voice_move WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result: tuple | None) -> VoiceMoveAction | None:
        return VoiceMoveAction(uuid.UUID(result[0]), result[1], result[2]) if result else None
