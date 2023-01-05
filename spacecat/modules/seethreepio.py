import random

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from spacecat.helpers import perms, constants


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
    async def coinflip(self, interaction):
        coin = random.randint(0, 1)
        if coin:
            await interaction.response.send_message("Heads")
        else:
            await interaction.response.send_message("Tails")

    @app_commands.command()
    async def rps(self, interaction: discord.Member, target: discord.Member):
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title="Rock Paper Scissors",
            description=f"<@{target.user_id}> has been challenged by <@{interaction.user}>. Make your moves.")

        # Add buttons
        view = View()
        rock_button = Button(emoji="✊", label="Rock", style=discord.ButtonStyle.green)
        view.add_item(rock_button)
        paper_button = Button(emoji="✋", label="Paper", style=discord.ButtonStyle.green)
        view.add_item(paper_button)
        scissors_button = Button(emoji="✌️", label="Scissors", style=discord.ButtonStyle.green)
        view.add_item(scissors_button)

        await interaction.response.send_message(embed=embed, view=view)

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
