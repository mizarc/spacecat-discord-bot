"""
Action of "Message" type, used for sending messages to a text channel.

This incorporates an override for a Message action as well as an sqlite
repository to store the associated data.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Self, override

from spacecat.modules.automation.event_scheduler import Action, ActionRepository

if TYPE_CHECKING:
    import sqlite3


class MessageAction(Action):
    """Represents an action that sends a message to a text channel."""

    def __init__(self: MessageAction, id_: uuid.UUID, text_channel_id: int, message: str) -> None:
        """
        Initializes a new instance of the MessageAction class.

        Args:
            id_ (uuid.UUID): The unique identifier for the action.
            text_channel_id (int): The ID of the text channel where the
                message will be sent.
            message (str): The content of the message to be sent.
        """
        super().__init__(id_)
        self.text_channel_id = text_channel_id
        self.message = message

    @classmethod
    def create_new(cls: type[MessageAction], text_channel_id: int, message: str) -> MessageAction:
        """
        Create a new instance of a Message Action.

        Parameters:
            text_channel_id (int): The ID of the text channel.
            message (str): The message to be sent.

        Returns:
            Self: A new instance of the class,
        """
        return cls(uuid.uuid4(), text_channel_id, message)

    @override
    def get_formatted_output(self: Self) -> str:
        return (
            f"Sends a message starting with '{self.message[:20]}' "
            f"to channel <#{self.text_channel_id}>."
        )

    @override
    def get_name() -> str:
        return "message"


class MessageActionRepository(ActionRepository[MessageAction]):
    """
    Repository for managing MessageAction objects.

    This class provides methods for adding, removing, and retrieving
    MessageAction objects from a database.
    """

    def __init__(self: MessageActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a MessageActionRepository instance.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS action_message "
            "(id TEXT PRIMARY KEY, text_channel INTEGER, message TEXT)"
        )
        self.db.commit()

    @override
    def get_by_id(self: Self, id_: uuid.UUID) -> MessageAction | None:
        result = (
            self.db.cursor()
            .execute("SELECT * FROM action_message WHERE id=?", (str(id_),))
            .fetchone()
        )
        return self._result_to_action(result)

    @override
    def add(self: Self, action: MessageAction) -> None:
        values = (str(action.id), action.text_channel_id, action.message)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO action_message VALUES (?, ?, ?)", values)
        self.db.commit()

    @override
    def remove(self: Self, id_: uuid.UUID) -> None:
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM action_message WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_action(result: tuple) -> MessageAction | None:
        """
        Convert a database result tuple to a MessageAction object.

        Args:
            result (tuple): The database result tuple containing the
                message action data.

        Returns:
            MessageAction | None: The MessageAction object created from
                the result tuple, or None if the result is invalid.
        """
        return MessageAction(uuid.UUID(result[0]), result[1], result[2]) if result else None
