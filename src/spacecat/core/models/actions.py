"""
Core actions module for platform-agnostic automation.

This module provides the fundamental action framework that can be
used across different platforms. It includes abstract base classes
for actions and their repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields, models

from spacecat.core.models.tasks import Task

if TYPE_CHECKING:
    from spacecat.core.interfaces import BaseDispatcher

# Required keys for each action type
REQUIRED_KEYS = {
    "message": ["channel_id", "content"],
    "embed": ["channel_id", "title", "description"],
    "voice_move": ["guild_id", "user_id", "target_vc"],
    "timeout": ["guild_id", "user_id", "duration"],
}


class Action(models.Model):
    """
    A representation of an Action.

    An action is a task executed when an event is dispatched. This can
    be any number of actions, such as sending a message, moving users
    between voice channels, or other platform-specific actions.
    """

    id = fields.UUIDField(pk=True)
    # The 'related_name' allows task.actions.all()
    task = fields.ForeignKeyField(Task, related_name="actions", on_delete=fields.CASCADE)
    action_type = fields.CharField(max_length=50, index=True)
    data = fields.JSONField()
    is_enabled = fields.BooleanField(default=True)

    class Meta:
        """Metadata for the Action model."""

        table = "actions"

    def get_formatted_output(self) -> str:
        """Returns a human-readable summary of the action."""
        # This can be expanded to return specific strings based on action_type
        return f"{self.action_type.title()} Action (ID: {str(self.id)[:4]})"

    async def run(self, dispatcher: BaseDispatcher) -> None:
        """Run the action using the associated dispatch function.

        Args:
            dispatcher: The dispatcher to use for running the action.
        """
        if not self.is_enabled:
            return

        # Dynamically find the method: e.g., "dispatch_send_message"
        method_name = f"dispatch_{self.action_type}"
        handler = getattr(dispatcher, method_name, None)

        if handler:
            try:
                # Spreads the database JSON 'data' as keyword arguments
                await handler(**self.data)
            except Exception as e:
                print(f"Execution Error [{self.action_type}]: {e}")
        else:
            print(f"Error: Dispatcher {type(dispatcher).__name__} has no method {method_name}")
