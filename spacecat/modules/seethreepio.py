import time

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import perms


class Throwing:
    def __init__(self, thrower: discord.Member, target: discord.Member):
        self.thrower = thrower
        self.target = target
        self.timeout_time = time.time() + 5.0


class Seethreepio(commands.Cog):
    """Random text response based features"""
    def __init__(self, bot):
        self.bot = bot
        self.throwings: dict[int, Throwing] = {}

    @app_commands.command()
    @perms.check()
    async def echo(self, interaction, *, message: str):
        """Repeats a given message"""
        await interaction.response.send_message(message)

    @app_commands.command()
    @perms.check()
    async def flip(self, interaction, member: discord.Member = None):
        """Flips a table... Or a person"""
        if member is None:
            await interaction.response.send_message("(╯°□°）╯︵ ┻━┻")
            return

        if member.id != self.bot.user.id:
            await interaction.response.send_message("(╯°□°）╯︵ " + member.mention)
        else:
            await interaction.response.send_message("Bitch please. \n'(╯°□°）╯︵ " + interaction.user.mention)

    @app_commands.command()
    @perms.check()
    async def throw(self, interaction: discord.Interaction, member: discord.Member, *, item: str = None):
        if member.id == self.bot.user.id:
            await interaction.response.send_message("No u. \n'(∩⚆ᗝ⚆)⊃ --==(O)     " + interaction.user.mention)
            return

        if item is not None:
            await interaction.response.send_message("(∩⚆ᗝ⚆)⊃ --==(" + item + ")     " + member.mention)
        else:
            await interaction.response.send_message("(∩⚆ᗝ⚆)⊃ --==(O)     " + member.mention)
        self.throwings[member.id] = Throwing(interaction.user, member)

    @app_commands.command()
    @perms.check()
    async def stealuserpic(self, interaction, user: discord.User):
        await interaction.response.send_message(user.avatar_url)


async def setup(bot):
    await bot.add_cog(Seethreepio(bot))
