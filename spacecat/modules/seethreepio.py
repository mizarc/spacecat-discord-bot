import time

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import perms


class Throwing:
    def __init__(self, thrower: discord.User, target: discord.User):
        self.thrower = thrower
        self.target = target
        self.timeout_time = time.time() + 5.0


class Seethreepio(commands.Cog):
    """Random text response based features"""
    def __init__(self, bot):
        self.bot = bot

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
    async def throw(self, interaction, member: discord.Member, *, item: str = None):
        if item is not None:
            await interaction.response.send_message("(∩⚆ᗝ⚆)⊃ --==(" + item + ")     "
                           + member.mention)
        else:
            if member.id != self.bot.user.id:
                await interaction.response.send_message("(∩⚆ᗝ⚆)⊃ --==(O)     " + member.mention)
            else:
                await interaction.response.send_message("Bitch please. \n'(∩⚆ᗝ⚆)⊃ --==(O)     "
                               + interaction.user.mention)

    @app_commands.command()
    @perms.check()
    async def stealuserpic(self, interaction, user: discord.User):
        await interaction.response.send_message(user.avatar_url)


async def setup(bot):
    await bot.add_cog(Seethreepio(bot))
