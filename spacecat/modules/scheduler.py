import discord
from discord import app_commands
from discord.ext import commands

import time
import uuid


class Reminder:
    def __init__(self, id_, user_id, channel_id, timestamp, message):
        self.id = id_
        self.user_id = user_id
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


async def setup(bot):
    await bot.add_cog(Scheduler(bot))
