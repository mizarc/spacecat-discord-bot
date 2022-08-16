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
        """Get list of all playlists"""
        results = self.db.cursor().execute('SELECT * FROM reminders').fetchall()
        playlists = []
        for result in results:
            playlists.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return playlists

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM reminders WHERE id=?', (id_,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5])

    def get_by_guild(self, guild):
        # Get list of all playlists in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=?', values)
        results = cursor.fetchall()

        playlists = []
        for result in results:
            playlists.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return playlists

    def get_by_guild_and_user(self, guild, name):
        # Get playlist by guild and playlist name
        cursor = self.db.cursor()
        values = (guild.id, name)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=? AND user_id=?', values)
        results = cursor.fetchall()

        playlists = []
        for result in results:
            playlists.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5]))
        return playlists

    def get_first_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM reminders WHERE timestamp < ? ORDER BY timestamp',
                                (timestamp,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5])

    def add(self, reminder):
        cursor = self.db.cursor()
        values = (str(reminder.id), reminder.name, reminder.guild_id, reminder.description)
        cursor.execute('INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.guild_id, reminder.name, reminder.description, reminder.id)
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
        self.bot = bot

    @app_commands.command()
    async def remindme(self, interaction, message: str, seconds: int = None, minutes: int = None, hours: int = None,
                       days: int = None, weeks: int = None, months: int = None, years: int = None):

        timestamp = await self.to_seconds(seconds, minutes, hours, days, weeks, months, years) + time.time()
        reminder = Reminder.create_new(interaction.user, interaction.channel, timestamp, message)

    @staticmethod
    async def to_seconds(seconds, minutes, hours, days, weeks, months, years) -> int:
        total = seconds
        total += minutes * 60
        total += hours * 3600
        total += days * 86400
        total += weeks * 604800
        total += months * 2629800
        total += years * 31557600
        return total


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
