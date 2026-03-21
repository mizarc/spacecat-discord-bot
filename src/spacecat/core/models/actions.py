"""
Core actions module for platform-agnostic automation.

This module provides the fundamental action framework that can be
used across different platforms. It includes abstract base classes
for actions and their repositories.
"""

from __future__ import annotations

from tortoise import fields, models


class Action(models.Model):
    """
    A representation of an Action.

    An action is a task executed when an event is dispatched. This can
    be any number of actions, such as sending a message, moving users
    between voice channels, or other platform-specific actions.
    """

    id = fields.UUIDField(pk=True)
    # The 'related_name' allows event.actions.all()
    event = fields.ForeignKeyField(
        "models.Event", related_name="actions", on_delete=fields.CASCADE
    )
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
