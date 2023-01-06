import enum
import random

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

from spacecat.helpers import perms, constants


class RPSAction(enum.Enum):
    Rock = 0
    Paper = 1
    Scissors = 2


class RPSGame:
    def __init__(self, challenger: discord.User, target: discord.User):
        self.challenger = challenger
        self.target = target
        self.challenger_action = None
        self.target_action = None

    def has_both_chosen(self):
        if self.challenger_action and self.target_action:
            return True
        return False

    def play_action(self, user: discord.User, action: RPSAction):
        if user == self.challenger:
            self.challenger_action = action
        elif user == self.target:
            self.target_action = action

    def get_winner(self):
        if self.challenger_action == self.target_action:
            return None
        elif self.challenger_action == RPSAction.Rock:
            if self.target_action == RPSAction.Scissors:
                return self.challenger
            else:
                return self.target
        elif self.challenger_action == RPSAction.Paper:
            if self.target_action == RPSAction.Rock:
                return self.challenger
            else:
                return self.target
        elif self.challenger_action == RPSAction.Scissors:
            if self.target_action == RPSAction.Paper:
                return self.challenger
            else:
                return self.target


class RPSButton(Button):
    def __init__(self, rps_game: RPSGame, action: RPSAction, label: str,
                 emoji: discord.PartialEmoji, style: discord.ButtonStyle):
        super().__init__(label=label, emoji=emoji, style=style)
        self.rps_game = rps_game
        self.action = action

    async def callback(self, interaction):
        self.rps_game.play_action(interaction.user, self.action)
        if self.rps_game.has_both_chosen():
            self.rps_game.get_winner()


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
    async def rps(self, interaction: discord.Interaction, target: discord.Member):
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title="Rock Paper Scissors",
            description=f"<@{target.id}> has been challenged by <@{interaction.user.id}>. Make your moves.")

        # Add buttons
        view = View()
        rock_button = RPSButton(emoji="✊", label="Rock", style=discord.ButtonStyle.green)
        view.add_item(rock_button)
        paper_button = RPSButton(emoji="✋", label="Paper", style=discord.ButtonStyle.green)
        view.add_item(paper_button)
        scissors_button = RPSButton(emoji="✌️", label="Scissors", style=discord.ButtonStyle.green)
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
