"""Shared automation and event command logic."""

import time
import uuid
from typing import Any

from spacecat.core.models.reminders import Reminder
from spacecat.core.registry import ServiceRegistry


async def remindme(
    user_id: str,
    message: str,
    delay_seconds: int,
    guild_id: int,
    channel_id: int,
    message_id: int,
) -> dict[str, Any]:
    """Creates a new reminder via ReminderService and returns display info.

    Args:
        user_id: The ID of the user to remind.
        message: The reminder message content.
        delay_seconds: Number of seconds until the reminder should
            dispatch.
        guild_id: The ID of the guild where the reminder was created.
        channel_id: The ID of the channel where the reminder was
            created.
        message_id: The ID of the message that triggered the reminder.

    Returns:
        A dictionary containing the created reminder and display
            message.
    """
    reminder_service = ServiceRegistry.reminders()
    scheduler = ServiceRegistry.reminder_scheduler()

    current_time = int(time.time())
    dispatch_time = current_time + delay_seconds

    reminder = await reminder_service.create_reminder(
        id=str(uuid.uuid4()),
        user_id=int(user_id),
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
        creation_time=current_time,
        dispatch_time=dispatch_time,
        message=message,
    )
    await scheduler.schedule(reminder)

    return {
        "reminder": reminder,
        "display": f"🔔 Reminder set for <t:{dispatch_time}:R>.",
    }


async def reminder_list(guild_id: int, author_id: int) -> dict[str, Any]:
    """Fetch reminders for a specific guild and author.

    Args:
        guild_id: The ID of the guild to filter reminders by.
        author_id: The ID of the author to filter reminders by.

    Returns:
        A dictionary containing the reminders list, title, and formatted display string.
    """
    reminders = await Reminder.filter(guild_id=guild_id, user_id=author_id).order_by(
        "dispatch_time"
    )

    if not reminders:
        return {
            "reminders": [],
            "title": "🔔 Your Reminders",
            "display": "You have no active reminders.",
        }

    lines = []
    for i, rem in enumerate(reminders, 1):
        lines.append(f"{i}. {rem.message[:20]}... | <t:{int(rem.dispatch_time)}:R>")

    return {"reminders": reminders, "title": "🔔 Your Reminders", "display": "\n".join(lines)}


def reminder_remove(reminders: list[Any], index: int) -> tuple[bool, str]:
    """Validates if a reminder can be removed by index."""
    if 0 < index <= len(reminders):
        return True, f"Reminder {index} has been removed."
    return False, "Invalid reminder index."


# --- Events: Lifecycle ---


def event_create(name: str, dispatch_time: int, repeat: Any) -> str:
    """Returns the success message for event creation."""
    return f"✅ Event `{name}` created for <t:{dispatch_time}:F>."


def event_destroy(name: str) -> str:
    """Returns the success message for event destruction."""
    return f"🗑️ Event `{name}` and all associated actions have been deleted."


def event_view(event: Any, actions: list[Any]) -> str:
    """Formats the full detail view of a single event."""
    status = "Paused" if event.is_paused else "Active"
    repeat_info = f"Repeats: {event.repeat_interval.name}"

    action_list = "\n".join([f"- {a.action_type}: {a.data}" for a in actions]) or "No actions set."

    return (
        f"**Event: {event.name}** ({status})\n"
        f"Next Run: <t:{event.dispatch_time}:R>\n"
        f"{repeat_info}\n\n"
        f"**Actions:**\n{action_list}"
    )


def event_list(events: list[Any]) -> str:
    """Formats a summary list of all guild events."""
    if not events:
        return "There are no scheduled events."

    return "\n".join(
        [
            f"• **{e.name}**: <t:{e.dispatch_time}:t> ({'Paused' if e.is_paused else 'Active'})"
            for e in events
        ]
    )


# --- Events: Modification ---


def event_pause(event_name: str) -> str:
    return f"⏸️ Event `{event_name}` has been paused. It will not trigger until resumed."


def event_resume(event_name: str) -> str:
    return f"▶️ Event `{event_name}` is now active."


def event_rename(old_name: str, new_name: str) -> str:
    return f"📝 Event `{old_name}` renamed to `{new_name}`."


def event_description(name: str, description: str) -> str:
    return f"📝 Description updated for `{name}`."


def event_reschedule(name: str, new_time: int) -> str:
    return f"📅 `{name}` rescheduled to <t:{new_time}:F>."


def event_interval(name: str, interval_name: str, multiplier: int) -> str:
    return f"🔄 `{name}` will now repeat every {multiplier} {interval_name}(s)."


# --- Events: Actions & Execution ---


def event_trigger(name: str) -> str:
    """Response for a manual 'Run Now' command."""
    return f"🚀 Manually triggering actions for `{name}`..."


def event_add_action(event_name: str, action_type: str, config: dict[str, Any]) -> str:
    """Generic response for adding any action (message, voice, etc)."""
    return f"➕ Added `{action_type}` action to event `{event_name}`."


def event_remove_action(event_name: str, action_index: int) -> str:
    return f"➖ Removed action {action_index} from `{event_name}`."


def event_reorder_actions(event_name: str) -> str:
    """Response for shifting action priority."""
    return f"🔢 Actions for `{event_name}` have been reordered."
