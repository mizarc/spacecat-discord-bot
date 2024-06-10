"""
Module for providing Dad jokes.

This module is meant to annoy the hell out of users. It listens to a
special keyword and replies with a stupid dad response.
"""

from __future__ import annotations

from typing import Self

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants, perms


class Dad(commands.Cog):
    """A minor annoyance and a pinch of fun."""

    def __init__(self: Dad, bot: commands.Bot) -> None:
        """
        Initialize the Dad cog with the provided bot instance.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        self.toggle = True

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        """
        Listens for the special message trigger to activate dad mode.

        Args:
            message (discord.Message): The message received by the bot.
        """
        if self.toggle:
            words = message.content.lower().split()
            triggers = ["im", "i'm"]

            # Compare first word to each trigger word
            for x in triggers:
                # Reply if first word starts with trigger word
                if x in words[:1]:
                    qualitycontent = f'Hi {" ".join(words[1:])}, I\'m a Cat!'

                    # Different reply if next words start with "a cat"
                    if "a cat" in " ".join(words[1:3]):
                        qualitycontent = "No you're not, I'm a cat."

                    await message.channel.send(qualitycontent)
                    return

    @app_commands.command()
    @perms.check()
    async def toggledad(self: Self, interaction: discord.Interaction) -> None:
        """
        Toggles the Dad feature on and off.

        Args:
         interaction (discord.Interaction): The Discord interaction
            triggering the toggle.
        """
        if self.toggle:
            self.toggle = False
            embed = discord.Embed(
                colour=constants.EmbedStatus.NO.value, description="Dad has been disabled"
            )
            await interaction.response.send_message(embed=embed)
        elif not self.toggle:
            self.toggle = True
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value, description="Dad has been enabled"
            )
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """
    Load the Dad cog.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(Dad(bot))
