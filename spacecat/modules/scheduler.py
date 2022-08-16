import asyncio
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands, tasks

import datetime
import time
import uuid

from spacecat.helpers import constants
from spacecat.spacecat import SpaceCat


class Reminder:
    def __init__(self, id_, user_id, guild_id, channel_id, timestamp, message):
        self.id = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.timestamp = timestamp
        self.message = message

    @classmethod
    def create_new(cls, user, guild, channel, timestamp, message):
        return cls(uuid.uuid4(), user.id, guild.id, channel.id, timestamp, message)


class ReminderRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'channel_id INTEGER, timestamp INTEGER, message TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM reminders').fetchall()
        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return reminders

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM reminders WHERE id=?', (id_,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5])

    def get_by_guild(self, guild):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return reminders

    def get_by_guild_and_user(self, guild, name):
        # Get reminder by guild and reminder name
        cursor = self.db.cursor()
        values = (guild.id, name)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=? AND user_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return reminders

    def get_first_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM reminders WHERE timestamp < ? ORDER BY timestamp',
                                (timestamp,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5])

    def add(self, reminder):
        cursor = self.db.cursor()
        values = (str(reminder.id), reminder.user_id, reminder.guild_id, reminder.channel_id,
                  reminder.timestamp, reminder.message)
        cursor.execute('INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.user_id, reminder.guild_id, reminder.channel_id,
                  reminder.timestamp, reminder.message, str(reminder.id))
        cursor.execute('UPDATE reminders SET user_id=?, guild_id=?, channel_id=?, '
                       'timestamp=?, message=? WHERE id=?', values)
        self.db.commit()

    def remove(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.id,)
        cursor.execute('DELETE FROM reminders WHERE id=?', values)
        self.db.commit()


class Scheduler(commands.Cog):
    """Schedule events to run at a later date"""
    def __init__(self, bot):
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = ReminderRepository(self.database)
        self.reminder_task = bot.loop.create_task(self.reminder_loop())

    async def reminder_loop(self):
        try:
            while not self.bot.is_closed():
                reminder = self.reminders.get_first_before_timestamp(time.time() + 86400)  # Get timers within 24 hours
                if reminder.timestamp >= time.time():
                    sleep_duration = (reminder.timestamp - time.time())
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

    @commands.Cog.listener()
    async def on_reminder(self, reminder):
        channel = self.bot.get_channel(reminder.channel_id)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} Reminder!",
            description=f"{self.bot.get_user(reminder.user_id).mention}, "
                        f"you asked me to remind you: \n\n {reminder.message}")
        await channel.send(embed=embed)

    @app_commands.command()
    async def remindme(self, interaction, message: str, seconds: int = 0, minutes: int = 0, hours: int = 0,
                       days: int = 0, weeks: int = 0, months: int = 0, years: int = 0):

        timestamp = await self.to_seconds(seconds, minutes, hours, days, weeks, months, years)
        dispatch_time = timestamp + time.time()
        reminder = Reminder.create_new(interaction.user, interaction.guild, interaction.channel, dispatch_time, message)
        self.reminders.add(reminder)
        self.reminder_task.cancel()
        self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Reminder has been set for "
                        f"{await self.format_datetime(datetime.timedelta(seconds=timestamp))}")
        await interaction.response.send_message(embed=embed)

    @staticmethod
    async def to_seconds(seconds=0, minutes=0, hours=0, days=0, weeks=0, months=0, years=0) -> int:
        total = seconds
        total += minutes * 60
        total += hours * 3600
        total += days * 86400
        total += weeks * 604800
        total += months * 2629800
        total += years * 31557600
        return total

    @staticmethod
    async def format_datetime(timedelta: datetime.timedelta) -> str:
        years = timedelta.days // 365
        months = (timedelta.days - years * 365) // 30
        days = (timedelta.days - years * 365 - months * 30)

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


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
