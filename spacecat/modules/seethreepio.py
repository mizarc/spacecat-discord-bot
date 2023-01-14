import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from spacecat.helpers import perms


class Throwing:
    def __init__(self, thrower: discord.Member, target: discord.Member):
        self.thrower = thrower
        self.target = target
        self.timeout_time = time.time() + 5.0

        # Current State
        self.caught = False

class CatchButton(Button):
    def __init__(self, throwing):
        self.throwing = throwing

    async def callback(self, interaction):
        self.throwing.caught = True


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
        if item is None:
            item = "O"

        # Have the bot throw the item at the user if the bot is targeted
        if member.id == self.bot.user.id:
            await interaction.response.send_message(f"No u. \n'(∩òᗝó)⊃ --==({item})          "
                                                    f"∩(óᗝò)∩ {interaction.user.mention}")
            return

        # Throw the item, giving the target a prompt to catch it
        throwing = Throwing(interaction.user, member)
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃ --==({item})          ∩(óᗝò)∩ " + member.mention)

        await asyncio.sleep(3)
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃      --==({item})     ∩(óᗝò)∩ {member.mention}")

        await asyncio.sleep(3)
        if throwing.caught:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} (∩óᗝò)⊃             "
                        f"({item})⸦(òᗝó⸦) {member.mention} has caught it!")
            return
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃                "
                    f"--==({item})Д⨱)∩ {member.mention} got dunked!")


    @app_commands.command()
    @perms.check()
    async def stealuserpic(self, interaction, user: discord.User):
        await interaction.response.send_message(user.avatar_url)


async def setup(bot):
    await bot.add_cog(Seethreepio(bot))
