"""
Action of "ChannelPrivate" type, used for setting a channel to private.

This incorporates an override for a ChannelPrivate action as well as an
sqlite repository to store the associated data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self, override

from spacecat.modules.automation.event_scheduler import Action, ActionRepository

if TYPE_CHECKING:
    import sqlite3


class ChannelPrivateAction(Action):
    """Represents an action that sets a channel to private."""

    def __init__(self: ChannelPrivateAction, id_: uuid.UUID, channel_id: int) -> None:
        """
        Initialise a ChannelPrivate action instance.

        Use the create_new classmethod to generate a new instance with
        an autogenerated id.

        Args:
            id_ (uuid.UUID): The unique identifier for the action.
            channel_id: The ID of the channel to set to private.
        """
        super().__init__(id_)
        self.channel_id = channel_id

    @classmethod
    def create_new(cls: type[ChannelPrivateAction], channel_id: int) -> ChannelPrivateAction:
        """
        Create a new ChannelPrivateAction instance.

        Parameters:
            channel_id: The ID of the channel to set to private.

        Returns:
            ChannelPrivateAction: A new instance of the class,
        """
        return cls(uuid.uuid4(), channel_id)

    @override
    def get_formatted_output(self: Self) -> str:
        return f"Sets channel <#{self.channel_id}> to private visibility."

    @override
    def get_name() -> str:
        return "channel_private"


class ChannelPrivateActionRepository(ActionRepository[ChannelPrivateAction]):
    """
    Repository for managing ChannelPrivateAction objects.

    This class provides methods for adding, removing, and retrieving
    ChannelPrivateAction objects from a database.
    """

    def __init__(self: ChannelPrivateActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a ChannelPrivateActionRepository instance.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS action_channel_private "
            "(id TEXT PRIMARY KEY, channel_id INTEGER)"
        )
        self.db.commit()

    @override
    def get_by_id(self: Self, id_: uuid.UUID) -> ChannelPrivateAction | None:
        result = (
            self.db.cursor()
            .execute("SELECT * FROM action_channel_private WHERE id=?", (str(id_),))
            .fetchone()
        )
        self.db.commit()
        return self._result_to_args(result)

    @override
    def add(self: Self, action: ChannelPrivateAction) -> None:
        values = (str(action.id), action.channel_id)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO action_channel_private VALUES (?, ?)", values)
        self.db.commit()

    @override
    def remove(self: Self, id_: uuid.UUID) -> None:
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM action_channel_private WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result: tuple | None) -> ChannelPrivateAction | None:
        return ChannelPrivateAction(uuid.UUID(result[0]), result[1]) if result else None
