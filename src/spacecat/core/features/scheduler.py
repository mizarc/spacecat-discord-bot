"""Shared automation and event command logic."""

import time
import uuid
from typing import Any

import dateparser

from spacecat.core.models.reminders import Reminder
from spacecat.core.models.tasks import Repeat, Task
from spacecat.core.registry import ServiceRegistry


async def remindme(
    user_id: str,
    message: str,
    dispatch_time_text: str,
    guild_id: int,
    channel_id: int,
    message_id: int,
) -> dict[str, Any]:
    """Creates a new reminder via ReminderService and returns display info.

    Args:
        user_id: The ID of the user to remind.
        message: The reminder message content.
        dispatch_time_text: The time to dispatch the reminder in a
            human-readable format.
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
    target_time = dateparser.parse(dispatch_time_text)
    if not target_time:
        return {
            "display": "Could not parse time input.",
        }

    target_timestamp = target_time.timestamp()
    if target_timestamp <= current_time:
        return {
            "display": "Time must be in the future.",
        }

    delay_seconds = int(target_timestamp - current_time)
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
    # Get reminders for the user and guild
    reminders = await Reminder.filter(guild_id=guild_id, user_id=author_id).order_by(
        "dispatch_time"
    )

    # Inform user that they have no reminders
    if not reminders:
        return {
            "reminders": [],
            "title": "🔔 Your Reminders",
            "display": "You have no active reminders.",
        }

    # Build the display strings for the list of reminders
    lines = []
    for i, rem in enumerate(reminders, 1):
        lines.append(f"{i}. {rem.message[:20]}... | <t:{int(rem.dispatch_time)}:R>")

    return {"reminders": reminders, "title": "🔔 Your Reminders", "display": "\n".join(lines)}


async def reminder_remove(guild_id: int, user_id: int, index: int) -> dict[str, Any]:
    """Remove a reminder by index for a specific user and guild.

    Args:
        guild_id: The ID of the guild.
        user_id: The ID of the user.
        index: The 1-based index of the reminder to remove.

    Returns:
        A dictionary containing the result message.
    """
    # Get reminders for the user and guild
    reminders = await Reminder.filter(guild_id=guild_id, user_id=user_id).order_by("dispatch_time")

    # Alert user that they have no reminders to remove
    if not reminders:
        return {"display": "You have no reminders to delete!"}

    # Alert the user if the index does not contain a reminder.
    if index < 1 or index > len(reminders):
        return {"display": f"Invalid reminder! You have {len(reminders)} reminder(s)."}

    # Get the reminder to remove
    reminder_to_remove = reminders[index - 1]

    # Get the scheduler service to unschedule the reminder
    scheduler = ServiceRegistry.reminder_scheduler()
    scheduler.unschedule(reminder_to_remove)

    # Delete the reminder from database
    await reminder_to_remove.delete()

    return {"display": f"✅ Reminder '{reminder_to_remove.message}' has been deleted!"}


async def task_list(guild_id: int) -> str:
    """Formats a summary list of all guild tasks from the ORM."""
    tasks = await Task.filter(guild_id=guild_id).order_by("dispatch_time")

    if not tasks:
        return "There are no available tasks."

    return "\n".join(
        [
            f"- **{task.name}**: <t:{task.dispatch_time}:t>"
            " ({'Paused' if task.is_paused else 'Active'})"
            for task in tasks
        ]
    )


async def task_create(
    guild_id: int,
    name: str,
    description: str,
    dispatch_time: int | None = None,
    repeat_interval: Repeat = Repeat.No,
    repeat_multiplier: int = 1,
) -> dict[str, Any]:
    """Creates a new task in the ORM with unique name validation.

    Args:
        guild_id: The ID of the guild where the task will be created
        name: The unique name for the task within the guild
        description: Optional description for the task
        dispatch_time: When the task should run (timestamp). If None, creates a manual-only task
        repeat_interval: How often the task should repeat (ignored for manual-only tasks)
        repeat_multiplier: Multiplier for the repeat interval (ignored for manual-only tasks)

    Returns:
        Dictionary with success status and message
    """
    # Check if the task name already exists for this guild
    existing_task = await Task.filter(guild_id=guild_id, name=name).first()
    if existing_task:
        return {
            "success": False,
            "message": f"A task with name `{name}` already exists in this guild.",
        }

    # Use None for manual-only tasks (no automatic dispatch)
    task_dispatch_time = None if dispatch_time is None else dispatch_time

    # For manual-only tasks, set repeat to No
    if dispatch_time is None:
        repeat_interval = Repeat.No
        repeat_multiplier = 1

    # Create the new task
    task = await Task.create_new(
        guild_id=guild_id,
        dispatch_time=task_dispatch_time,
        repeat_interval=repeat_interval,
        repeat_multiplier=repeat_multiplier,
        name=name,
        description=description,
    )

    if dispatch_time is None:
        return {
            "success": True,
            "task": task,
            "message": f"✅ Task `{name}` created.",
        }
    return {
        "success": True,
        "task": task,
        "message": f"✅ Task `{name}` created for <t:{dispatch_time}:F>.",
    }


def task_info(event: Any, actions: list[Any]) -> str:
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


def task_destroy(name: str) -> str:
    """Returns the success message for event destruction."""
    return f"🗑️ Event `{name}` and all associated actions have been deleted."


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
