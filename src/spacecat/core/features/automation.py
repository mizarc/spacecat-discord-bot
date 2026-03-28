"""Shared automation and task command logic."""

import time
from typing import Any

import dateparser
from tortoise import expressions
from tortoise.exceptions import DoesNotExist, IntegrityError, ValidationError

from spacecat.core.models.actions import REQUIRED_KEYS, Action
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
        user_id=int(user_id),
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=message_id,
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


async def task_action_add(
    guild_id: int, task_name: str, action_type: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Adds an action to a task.

    Args:
        guild_id: The ID of the guild where the task exists.
        task_name: The name of the task to add the action to.
        action_type: The type of action to add.
        config: The configuration for the action.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=task_name).first()

    if not task:
        return {"success": False, "message": f"Task `{task_name}` not found."}

    if action_type in REQUIRED_KEYS:
        missing_keys = [key for key in REQUIRED_KEYS[action_type] if key not in config]
        if missing_keys:
            return {
                "success": False,
                "message": (
                    f"Missing required keys for `{action_type}` action: {', '.join(missing_keys)}"
                ),
            }

    # Calculate the next order value based on existing actions
    last_action = await task.actions.all().order_by("-position").first()
    next_position = (last_action.position + 1) if last_action else 1

    try:
        await Action.create(
            task=task, action_type=action_type, data=config, position=next_position
        )
    except (IntegrityError, ValidationError, DoesNotExist) as error:
        return {"success": False, "message": f"Error adding action: {error!s}"}
    else:
        return {
            "success": True,
            "message": f"➕ Added `{action_type}` action to task `{task_name}`.",  # noqa: RUF001
        }


async def task_action_remove(guild_id: int, task_name: str, action_index: int) -> dict[str, Any]:
    """Removes an action from a task by index.

    Args:
        guild_id: The ID of the guild where the task exists.
        task_name: The name of the task to remove the action from.
        action_index: The 1-based index of the action to remove.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=task_name).first()

    if not task:
        return {"success": False, "message": f"Task `{task_name}` not found."}

    # Get all actions for the task
    actions = await task.actions.all().order_by("position")

    if not actions:
        return {"success": False, "message": f"Task `{task_name}` has no actions to remove."}

    if action_index < 1 or action_index > len(actions):
        return {
            "success": False,
            "message": f"Invalid action index {action_index}. Task has {len(actions)} action(s).",
        }

    action_to_remove = actions[action_index - 1]
    action_type = action_to_remove.action_type

    try:
        deleted_position = action_to_remove.position
        await action_to_remove.delete()
        await task.actions.filter(position__gt=deleted_position).update(
            position=expressions.F("position") - 1
        )
    except (IntegrityError, ValidationError, DoesNotExist) as error:
        return {"success": False, "message": f"Error removing action: {error!s}"}
    else:
        return {
            "success": True,
            "message": f"➖ Removed {action_type} from `{task_name}`.",  # noqa: RUF001
        }


async def task_action_reorder(guild_id: int, task_name: str) -> dict[str, Any]:
    """Placeholder for reordering task actions.

    Note: This would require adding an 'order' field to the Action model
    for proper ordering functionality.

    Args:
        guild_id: The ID of the guild where the task exists.
        task_name: The name of the task to reorder actions for.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=task_name).first()

    if not task:
        return {"success": False, "message": f"Task `{task_name}` not found."}

    # Get all actions for the task
    actions = await task.actions.all().order_by("position")

    if not actions:
        return {"success": False, "message": f"Task `{task_name}` has no actions to reorder."}

    # Example logic to normalize the order to 1, 2, 3...
    for i, action in enumerate(actions, 1):
        action.position = i
        await action.save()

    return {
        "success": True,
        "message": f"✅ Actions for `{task_name}` have been normalized.",
    }


async def task_create(
    guild_id: int,
    name: str,
    description: str | None = None,
    dispatch_time: int | None = None,
    repeat_interval: Repeat = Repeat.No,
    repeat_multiplier: int = 1,
) -> dict[str, Any]:
    """Creates a new task in the ORM with unique name validation.

    Args:
        guild_id: The ID of the guild where the task will be created
        name: The unique name for the task within the guild
        description: Optional description for the task
        dispatch_time: When the task should run (timestamp). If None,
            creates a manual-only task
        repeat_interval: How often the task should repeat (ignored for
            manual-only tasks)
        repeat_multiplier: Multiplier for the repeat interval (ignored
            for manual-only tasks)

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


async def task_delete(guild_id: int, name: str) -> dict[str, Any]:
    """Deletes a task by name and guild_id using the ORM.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to delete.

    Returns:
        Dictionary with success status and message
    """
    # Find the task by guild_id and name
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    # Delete the task from the database
    await task.delete()

    return {
        "success": True,
        "message": f"🗑️ Task `{name}` has been deleted.",
    }


async def task_description(guild_id: int, name: str, description: str) -> dict[str, Any]:
    """Updates a task's description by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to update.
        description: The new description for the task.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    task.description = description
    await task.save()

    return {"success": True, "message": f"📝 Description updated for `{name}`."}


async def task_list(guild_id: int, page: int = 1, page_size: int = 10) -> dict[str, Any]:
    """Formats a summary list of all guild tasks."""
    total_count = await Task.filter(guild_id=guild_id).count()
    tasks = (
        await Task.filter(guild_id=guild_id)
        .order_by("dispatch_time")
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    if not tasks:
        return {
            "title": "📋 Available Tasks",
            "body": "There are no available tasks.",
        }

    total_pages = (total_count + page_size - 1) // page_size

    lines = []
    for task in tasks:
        if task.dispatch_time:
            status = "Paused" if task.is_paused else "Active"
            lines.append(f"- **{task.name}:** <t:{task.dispatch_time}:t> ({status})")
        else:
            lines.append(f"- **{task.name}:** No Schedule")

    body = "\n".join(lines)

    return {
        "title": "📋 Available Tasks",
        "body": body,
        "footer": f"Page {page} of {total_pages} ({total_count} total tasks)",
    }


async def task_info(guild_id: int, name: str) -> dict[str, Any]:
    """Formats the full detail view of a single task.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to display.

    Returns:
        Dictionary with success status and formatted display message.
    """
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    actions = await task.actions.all().order_by("position")

    status = "Paused" if task.is_paused else "Active"
    repeat_info = f"Repeats: {Repeat(task.repeat_interval).name}"

    action_lines = []
    for i, a in enumerate(actions, 1):
        content = ""
        if a.action_type == "message" and "content" in a.data:
            msg = a.data.get("content", "")
            channel = f" <#{a.data['channel_id']}>" if "channel_id" in a.data else ""
            max_msg_length = 30
            truncated_msg = f"{msg[:30]}..." if len(msg) > max_msg_length else msg
            content = f"Send '{truncated_msg}' to channel{channel}"
        action_lines.append(f"**{i}. {a.action_type}:** {content}")

    action_list = "\n".join(action_lines) or "No actions set."

    embed_data = {
        "title": f"Task: {task.name}",
        "description": task.description or "No description provided.",
        "status": status,
        "next_run": f"<t:{task.dispatch_time}:R>" if task.dispatch_time else "Manual Only",
        "repeat": repeat_info,
        "actions": action_list,
    }

    return {"success": True, "task": task, "embed": embed_data}


async def task_pause(guild_id: int, task_name: str) -> dict[str, Any]:
    """Pauses a task by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        task_name: The name of the task to pause.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=task_name).first()

    if not task:
        return {"success": False, "message": f"Task `{task_name}` not found."}

    if task.is_paused:
        return {"success": False, "message": f"Task `{task_name}` is already paused."}

    task.is_paused = True
    await task.save()

    return {
        "success": True,
        "message": (
            f"⏸️ Task `{task_name}` has been paused."
            " It will not automatically trigger until resumed."
        ),
    }


async def task_rename(guild_id: int, old_name: str, new_name: str) -> dict[str, Any]:
    """Renames a task by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        old_name: The current name of the task.
        new_name: The new name for the task.

    Returns:
        Dictionary with success status and message.
    """
    # Check if the new name already exists
    existing_task = await Task.filter(guild_id=guild_id, name=new_name).first()
    if existing_task:
        return {"success": False, "message": f"A task with name `{new_name}` already exists."}

    task = await Task.filter(guild_id=guild_id, name=old_name).first()

    if not task:
        return {"success": False, "message": f"Task `{old_name}` not found."}

    task.name = new_name
    await task.save()

    return {"success": True, "message": f"📝 Task `{old_name}` renamed to `{new_name}`."}


async def task_resume(guild_id: int, task_name: str) -> dict[str, Any]:
    """Resumes a task by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        task_name: The name of the task to resume.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=task_name).first()

    if not task:
        return {"success": False, "message": f"Task `{task_name}` not found."}

    if not task.is_paused:
        return {"success": False, "message": f"Task `{task_name}` is already active."}

    task.is_paused = False
    await task.save()

    return {"success": True, "message": f"▶️ Task `{task_name}` is now active."}


async def task_reschedule(guild_id: int, name: str, new_time: int) -> dict[str, Any]:
    """Reschedules a task by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to reschedule.
        new_time: The new dispatch time as a timestamp.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    task.dispatch_time = new_time
    await task.save()

    return {"success": True, "message": f"📅 `{name}` rescheduled to <t:{new_time}:F>."}


async def task_interval(
    guild_id: int, name: str, interval_name: str, multiplier: int
) -> dict[str, Any]:
    """Updates a task's repeat interval by name and guild_id.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to update.
        interval_name: The name of the repeat interval (Hourly, Daily,
            Weekly).
        multiplier: The multiplier for the interval.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    # Convert interval name to Repeat enum
    interval_map = {
        "hourly": Repeat.Hourly,
        "daily": Repeat.Daily,
        "weekly": Repeat.Weekly,
        "no": Repeat.No,
    }

    interval_lower = interval_name.lower()
    if interval_lower not in interval_map:
        return {
            "success": False,
            "message": f"Invalid interval `{interval_name}`. Use: hourly, daily, weekly, or no.",
        }

    task.repeat_interval = interval_map[interval_lower]
    task.repeat_multiplier = multiplier
    await task.save()

    return {
        "success": True,
        "message": f"🔄 `{name}` will now repeat every {multiplier} {interval_name}(s).",
    }


async def task_trigger(guild_id: int, name: str) -> dict[str, Any]:
    """Manually triggers a task's actions.

    Args:
        guild_id: The ID of the guild where the task exists.
        name: The name of the task to trigger.

    Returns:
        Dictionary with success status and message.
    """
    task = await Task.filter(guild_id=guild_id, name=name).first()

    if not task:
        return {"success": False, "message": f"Task `{name}` not found."}

    event_service = ServiceRegistry.events()

    try:
        await event_service.execute_actions(task)

        now = int(time.time())
        task.last_run_time = now
        await task.save()
    except (OSError, ValueError, RuntimeError) as error:
        return {"success": False, "message": f"Error triggering task `{name}`: {error}"}
    else:
        return {"success": True, "message": f"🚀 Successfully triggered actions for `{name}`."}
