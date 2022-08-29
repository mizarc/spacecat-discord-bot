import asyncio
import sqlite3
from enum import Enum
from itertools import islice

import discord
from discord import app_commands
from discord.ext import commands

import datetime
import pytz
import time
import uuid

from spacecat.helpers import constants
from spacecat.modules.administration import ServerSettingsRepository
from spacecat.spacecat import SpaceCat


class Repeat(Enum):
    No = 0,
    Hourly = 1,
    Daily = 2,
    Weekly = 3,
    Monthly = 4,
    Yearly = 5


class Day(Enum):
    Monday = 0,
    Tuesday = 2,
    Wednesday = 3,
    Thursday = 4,
    Friday = 5,
    Saturday = 6,
    Sunday = 7


class Reminder:
    def __init__(self, id_, user_id, guild_id, channel_id, message_id, creation_time, dispatch_time, message):
        self.id = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.creation_time = creation_time
        self.dispatch_time = dispatch_time
        self.message = message

    @classmethod
    def create_new(cls, user, guild, channel, confirmation_message, creation_time, dispatch_time, message):
        return cls(uuid.uuid4(), user.id, guild.id, channel.id, confirmation_message.id, creation_time, dispatch_time,
                   message)


class ReminderRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'channel_id INTEGER, message_id INTEGER, creation_time INTEGER, dispatch_time INTEGER, '
                       'message TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM reminders').fetchall()
        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM reminders WHERE id=?', (id_,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7])

    def get_by_guild(self, guild):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_by_guild_and_user(self, guild, name):
        # Get reminder by guild and reminder name
        cursor = self.db.cursor()
        values = (guild.id, name)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=? AND user_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_first_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM reminders WHERE dispatch_time < ? ORDER BY dispatch_time',
                                (timestamp,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7])

    def add(self, reminder):
        cursor = self.db.cursor()
        values = (str(reminder.id), reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                  reminder.creation_time, reminder.dispatch_time, reminder.message)
        cursor.execute('INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                  reminder.creation_time, reminder.dispatch_time, reminder.message, str(reminder.id))
        cursor.execute('UPDATE reminders SET user_id=?, guild_id=?, channel_id=?, message_id=?'
                       'creation_time=?, dispatch_time=?, message=? WHERE id=?', values)
        self.db.commit()

    def remove(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.id,)
        cursor.execute('DELETE FROM reminders WHERE id=?', values)
        self.db.commit()


class Event:
    def __init__(self, id_, user_id, guild_id, dispatch_time, last_run_time, repeat_interval,
                 repeat_multiplier, name, function_name, arguments):
        self.id = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.dispatch_time = dispatch_time
        self.last_run_time = last_run_time
        self.repeat_interval = repeat_interval
        self.repeat_multiplier = repeat_multiplier
        self.name = name
        self.function_name = function_name
        self.arguments = arguments

    @classmethod
    def create_new(cls, user_id, guild_id, dispatch_time, repeat_interval,
                   repeat_multiplier, name, function_name, arguments):
        return cls(uuid.uuid4(), user_id, guild_id, dispatch_time, None, repeat_interval,
                   repeat_multiplier, name, function_name, arguments)


class EventRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'dispatch_time INTEGER, last_run_time INTEGER, repeat_interval TEXT, repeat_multiplier INTEGER, '
                       'name TEXT, function_name TEXT, arguments TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM events').fetchall()
        reminders = []
        for result in results:
            reminders.append(Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6],
                                   result[7], result[8], result[9]))
        return reminders

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM events WHERE id=?', (id_,)).fetchone()
        return Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6], result[7],
                     result[8], result[9])

    def get_by_guild(self, guild):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM events WHERE guild_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6],
                                   result[7], result[8], result[9]))
        return reminders

    def get_repeating(self):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM events WHERE NOT repeat_interval=?', ('No',))
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6],
                                   result[7], result[8], result[9]))
        return reminders

    def get_first_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM events '
                                'WHERE dispatch_time < ? AND repeat_interval="No" ORDER BY dispatch_time',
                                (timestamp,)).fetchone()
        return Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6], result[7],
                     result[8], result[9])

    def add(self, event):
        cursor = self.db.cursor()
        values = (str(event.id), event.user_id, event.guild_id, event.dispatch_time, event.last_run_time,
                  event.repeat_interval.name, event.repeat_multiplier, event.name, event.function_name, event.arguments)
        cursor.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, event):
        cursor = self.db.cursor()
        values = (event.user_id, event.guild_id, event.dispatch_time, event.last_run_time, event.repeat_interval.name,
                  event.repeat_multiplier, event.name, event.function_name, event.arguments, str(event.id))
        cursor.execute('UPDATE events SET user_id=?, guild_id=?, dispatch_time=?, last_run_time=?, repeat_interval=?, '
                       'repeat_multiplier=?, name=?, function_name=?, arguments=? WHERE id=?', values)
        self.db.commit()

    def remove(self, event):
        cursor = self.db.cursor()
        values = (event.id,)
        cursor.execute('DELETE FROM events WHERE id=?', values)
        self.db.commit()


class RepeatJob:
    def __init__(self, bot: commands.Bot, event: Event, timezone: pytz.tzinfo):
        self.bot = bot
        self.event = event
        self.timezone = timezone
        self.interval = self.calculate_interval()
        self.next_run_time = self.calculate_next_run()
        self.job_task = asyncio.create_task(self.job_loop())

    def calculate_next_run(self):
        next_run_time = self.event.dispatch_time
        if self.event.last_run_time:
            next_run_time = self.event.last_run_time
        while next_run_time <= datetime.datetime.now(tz=self.timezone).timestamp() + 1:
            next_run_time += self.interval
        return next_run_time

    def calculate_interval(self):
        interval = 0
        if self.event.repeat_interval == Repeat.Hourly:
            interval = 3600
        elif self.event.repeat_interval == Repeat.Daily:
            interval = 86400
        elif self.event.repeat_interval == Repeat.Weekly:
            interval = 604800
        return interval * self.event.repeat_multiplier

    async def job_loop(self):
        while True:
            if self.next_run_time >= time.time():
                await asyncio.sleep(self.next_run_time - time.time())
            await self.dispatch_event()

    async def dispatch_event(self):
        self.bot.dispatch(f"{self.event.function_name}_event", self.event)
        self.event.last_run_time = self.next_run_time
        self.next_run_time = self.calculate_next_run()
        self.job_task.cancel()
        self.job_task = asyncio.create_task(self.job_loop())


class Automation(commands.Cog):
    """Schedule events to run at a later date"""
    def __init__(self, bot):
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = ReminderRepository(self.database)
        self.events = EventRepository(self.database)
        self.reminder_task = bot.loop.create_task(self.reminder_loop())
        self.event_task = bot.loop.create_task(self.event_loop())
        self.repeating_events = {}

    async def cog_load(self):
        await self.init_repeating_events()

    schedule_group = app_commands.Group(
        name="schedule", description="Allows you to run an function at a scheduled time.")
    schedule_add_group = app_commands.Group(
        parent=schedule_group, name="add", description="Add a new scheudled event.")

    async def init_repeating_events(self):
        events = self.events.get_repeating()
        for event in events:
            if event.id in self.repeating_events:
                continue
            self.repeating_events[event.id] = RepeatJob(self.bot, event, await self.get_guild_timezone(event.guild_id))

    async def reminder_loop(self):
        try:
            while not self.bot.is_closed():
                reminder = self.reminders.get_first_before_timestamp(time.time() + 86400)  # Get timers within 24 hours
                if reminder.dispatch_time >= time.time():
                    sleep_duration = (reminder.dispatch_time - time.time())
                    await asyncio.sleep(sleep_duration)

                await self.dispatch_reminder(reminder)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.reminder_task.cancel()
            self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

    async def dispatch_reminder(self, reminder: Reminder):
        self.reminders.remove(reminder)
        self.bot.dispatch("reminder", reminder)

    async def event_loop(self):
        try:
            while not self.bot.is_closed():
                event = self.events.get_first_before_timestamp(time.time() + 86400)  # Get timers within 24 hours
                if event.dispatch_time >= time.time():
                    sleep_duration = (event.dispatch_time - time.time())
                    await asyncio.sleep(sleep_duration)

                await self.dispatch_event(event)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.event_task.cancel()
            self.event_task = self.bot.loop.create_task(self.event_loop())

    async def dispatch_event(self, event: Event):
        self.events.remove(event)
        self.bot.dispatch(f"{event.function_name}_event", event)

    @commands.Cog.listener()
    async def on_reminder(self, reminder):
        channel = self.bot.get_channel(reminder.channel_id)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} Reminder!",
            description=f"<@{reminder.user_id}>**, <t:{int(reminder.creation_time)}:R> "
                        f"you asked me to remind you:** \n {reminder.message}")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Go to original message',
                                        url=f'https://discord.com/channels/{reminder.guild_id}/'
                                            f'{reminder.channel_id}/{reminder.message_id}'))
        await channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message_event(self, event):
        self.events.update(event)
        channel = self.bot.get_channel(int(event.arguments.split(' ')[0]))
        await channel.send(embed=discord.Embed(
            colour=constants.EmbedStatus.SPECIAL.value,
            title=f"{event.name}",
            description=f"{event.arguments.split(' ', 1)[1]}"
        ))

    @commands.Cog.listener()
    async def on_voicekick_event(self, event):
        self.events.update(event)
        voice_channel = self.bot.get_channel(int(event.arguments.split(' ')[0]))
        for member in voice_channel.members:
            await member.move_to(None)

    @commands.Cog.listener()
    async def on_voicemove_event(self, event):
        current_channel = self.bot.get_channel(int(event.arguments.split(' ')[0]))
        new_channel = self.bot.get_channel(int(event.arguments.split(' ')[1]))
        for member in current_channel.members:
            await member.move_to(new_channel)

    @app_commands.command()
    async def remindme(self, interaction, message: str, seconds: int = 0, minutes: int = 0, hours: int = 0,
                       days: int = 0, weeks: int = 0, months: int = 0, years: int = 0):

        timestamp = await self.to_seconds(seconds, minutes, hours, days, weeks, months, years)
        dispatch_time = timestamp + time.time()

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Reminder has been set for "
                        f"{await self.format_datetime(datetime.timedelta(seconds=timestamp))}")
        await interaction.response.send_message(embed=embed)

        reminder = Reminder.create_new(interaction.user, interaction.guild, interaction.channel,
                                       await interaction.original_response(), time.time(), dispatch_time, message)
        self.reminders.add(reminder)
        self.reminder_task.cancel()
        self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

    @schedule_add_group.command(name="message")
    async def schedule_message(self, interaction, title: str, message: str, channel: discord.TextChannel,
                               time_string: str, date_string: str, repeat: Repeat = Repeat.No,
                               repeat_multiplier: int = 0):
        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "message", f"{channel.id} {message}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A message event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="voicekick")
    async def schedule_voicekick(self, interaction, title: str, voice_channel: discord.VoiceChannel, time_string: str,
                                 date_string: str, repeat: Repeat = Repeat.No, repeat_multiplier: int = 0):
        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "voicekick", f"{voice_channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A voicekick event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="voicemove")
    async def schedule_voicemove(self, interaction, title: str, current_channel: discord.VoiceChannel,
                                 new_channel: discord.VoiceChannel, time_string: str, date_string: str,
                                 repeat: Repeat = Repeat.No, repeat_multiplier: int = 0):
        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "voicemove",
                                 f"{current_channel.id} {new_channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A voicemove event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_group.command()
    async def schedule_list(self, interaction):
        events = self.events.get_by_guild(interaction.guild)
        if not events:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no scheduled events")
            await interaction.response.send_message(embed=embed)
            return

        # Format playlist songs into pretty listings
        event_listings = []
        for index, event in enumerate(islice(events, 0, 10)):
            listing = f"{index + 1}. {event.name}"
            if event.repeat_interval != Repeat.No:
                listing += f" | `Repeating {event.repeat_interval.name}`"
            event_listings.append(listing)

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Events")
        playlist_output = '\n'.join(event_listings)
        embed.add_field(
            name=f"{len(events)} available",
            value=playlist_output, inline=False)
        await interaction.response.send_message(embed=embed)

    async def load_event(self, event):
        if event.repeat_interval == Repeat.No:
            self.event_task.cancel()
            self.event_task = self.bot.loop.create_task(self.event_loop())
            return
        self.repeating_events[event.id] = RepeatJob(
            self.bot, event, await self.get_guild_timezone(event.guild_id))

    async def fetch_future_datetime(self, guild: discord.Guild, time_string: str, date_string: str = None):
        time_ = await self.parse_time(time_string)
        timezone = await self.get_guild_timezone(guild.id)
        if date_string is None:
            date = datetime.date.today()
        else:
            date = await self.parse_date(date_string)

        combined = timezone.localize(datetime.datetime.combine(date, time_))
        timestamp = combined.timestamp()
        if timestamp < time.time():
            combined.replace(day=combined.day + 1)
        return combined

    async def get_guild_timezone(self, guild_id):
        administration = self.bot.get_cog("Administration")
        servers_settings: ServerSettingsRepository = administration.server_settings
        server_settings = servers_settings.get_by_guild(guild_id)
        if server_settings.timezone is not None:
            return pytz.timezone(server_settings.timezone)
        return pytz.utc

    @staticmethod
    async def parse_time(time_string):
        split = time_string.split(':')
        return datetime.time(hour=int(split[0]), minute=int(split[1]))

    @staticmethod
    async def parse_date(date_string):
        split = date_string.split('/')
        if not split:
            split = date_string.split(':')
        if not split:
            raise
        return datetime.date(day=int(split[0]), month=int(split[1]), year=int(split[2]))

    @staticmethod
    async def to_seconds(seconds=0, minutes=0, hours=0, days=0, weeks=0, months=0, years=0) -> int:
        total = seconds
        total += minutes * 60
        total += hours * 3600
        total += days * 86400
        total += weeks * 604800
        total += months * 2592000
        total += years * 31536000
        return total

    @staticmethod
    async def format_datetime(timedelta: datetime.timedelta) -> str:
        years = timedelta.days // 365
        months = (timedelta.days - years * 365) // 30
        weeks = (timedelta.days - years * 365 - months * 30) // 7
        days = (timedelta.days - years * 365 - months * 30 - weeks * 7)

        hours = timedelta.seconds // 3600
        minutes = (timedelta.seconds - hours * 3600) // 60
        seconds = (timedelta.seconds - hours * 3600 - minutes * 60)

        output = ""
        if years:
            if years > 1:
                output += f"{years} years, "
            else:
                output += f"{years} year, "
        if months:
            if months > 1:
                output += f"{months} months, "
            else:
                output += f"{months} month, "
        if weeks:
            if weeks > 1:
                output += f"{weeks} weeks, "
            else:
                output += f"{weeks} week, "
        if days:
            if days > 1:
                output += f"{days} days, "
            else:
                output += f"{days} day, "
        if hours:
            if hours > 1:
                output += f"{hours} hours, "
            else:
                output += f"{hours} hour, "
        if minutes:
            if minutes > 1:
                output += f"{minutes} minutes, "
            else:
                output += f"{minutes} minute, "
        if seconds:
            if seconds > 1:
                output += f"{seconds} seconds, "
            else:
                output += f"{seconds} second, "
        return output[:-2]

    @staticmethod
    async def format_repeat_message(interval: Repeat, multiplier: int):
        if interval == Repeat.Hourly:
            interval_string = "hour"
        elif interval == Repeat.Daily:
            interval_string = "day"
        elif interval == Repeat.Weekly:
            interval_string = "week"
        elif interval == Repeat.Monthly:
            interval_string = "month"
        elif interval == Repeat.Yearly:
            interval_string = "year"
        else:
            return "."

        if multiplier:
            return f", repeating every {interval_string}."
        return f", repeating every {multiplier} {interval_string}s."


async def setup(bot):
    await bot.add_cog(Automation(bot))
