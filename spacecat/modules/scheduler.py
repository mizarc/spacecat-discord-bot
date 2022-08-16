import discord
from discord import app_commands
from discord.ext import commands

import time
import uuid


class Reminder:
    def __init__(self, id_, user_id, guild_id, channel_id, timestamp, message):
        self.id = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.timestamp = timestamp
        self.message = message

    @classmethod
    def create_new(cls, user, channel, timestamp, message):
        return cls(uuid.uuid4(), user.id, channel.id, timestamp, message)


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
