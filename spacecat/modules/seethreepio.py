import enum
import random

import asyncio
import time

import discord
import typing
from discord import app_commands
from discord.ext import commands
from discord.ui import Button

from spacecat.helpers import perms, constants
from spacecat.helpers.views import DefaultView


class RPSAction(enum.Enum):
    Rock = "✊"
    Paper = "✋"
    Scissors = "✌️"


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

    def play_action(self, user: discord.User, action: RPSAction) -> bool:
        if user == self.challenger and not self.challenger_action:
            self.challenger_action = action
            return True
        elif user == self.target and not self.target_action:
            self.target_action = action
            return True
        return False

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
                 emoji: typing.Union[discord.PartialEmoji, str], style: discord.ButtonStyle):
        super().__init__(label=label, emoji=emoji, style=style)
        self.rps_game = rps_game
        self.action = action

    async def callback(self, interaction):
        await interaction.response.defer()

        # Tell non-players that they cannot play this game
        if not (interaction.user == self.rps_game.challenger or interaction.user == self.rps_game.target):
            await interaction.followup.send(content="You are not included in this game.", ephemeral=True)
            return

        # Alert user of choice
        action_result = self.rps_game.play_action(interaction.user, self.action)
        if action_result:
            await interaction.followup.send(content=f"You have chosen {self.action.value}", ephemeral=True)
        else:
            await interaction.followup.send(content="You have already made a selection.", ephemeral=True)

        # Declare winner
        if self.rps_game.has_both_chosen():
            self.rps_game.get_winner()
            win_text = f"<@{self.rps_game.get_winner().id}> has won!" if self.rps_game.get_winner() else "It's a draw!"
            embed = discord.Embed(
                colour=constants.EmbedStatus.GAME.value,
                title="Rock Paper Scissors",
                description=f"<@{self.rps_game.challenger.id}> {self.rps_game.challenger_action.value} vs"
                            f" {self.rps_game.target_action.value} <@{self.rps_game.target.id}>"
                            f"\n\n{win_text}")
            await interaction.followup.send(embed=embed)

            # Disable buttons after game has completed
            buttons = self.view.children
            for button in buttons:
                button.disabled = True
            self.disabled = True
            await interaction.edit_original_response(view=self.view)

    async def on_timeout(self):
        self.disabled = True


class Throwing:
    def __init__(self, thrower: discord.Member, target: discord.Member):
        self.thrower = thrower
        self.target = target
        self.timeout_time = time.time() + 5.0

        # Current State
        self.caught = False


class CatchButton(Button):
    def __init__(self, throwing):
        super().__init__(label="Catch", emoji="🫴", style=discord.ButtonStyle.green)
        self.throwing = throwing

    async def callback(self, interaction):
        if self.throwing.target.id is not interaction.user.id:
            await interaction.response.send_message("You are not the target.", ephemeral=True)
            return

        self.throwing.caught = True
        await interaction.response.send_message("You are prepared to catch.", ephemeral=True)


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
    async def coinflip(self, interaction):
        coin = random.randint(0, 1)
        if coin:
            await interaction.response.send_message("Heads")
        else:
            await interaction.response.send_message("Tails")

    @app_commands.command()
    async def diceroll(self, interaction, sides: int = 6):
        result = random.randint(1, sides)
        await interaction.response.send_message(f"You rolled a {result} on a {sides} sided dice")

    @app_commands.command()
    async def rps(self, interaction: discord.Interaction, target: discord.User):
        embed = discord.Embed(
            colour=constants.EmbedStatus.GAME.value,
            title="Rock Paper Scissors",
            description=f"<@{target.id}> has been challenged by <@{interaction.user.id}>. Make your moves.")

        rps_game = RPSGame(interaction.user, target)

        # Add buttons
        view = DefaultView(embed=embed)
        rock_button = RPSButton(rps_game, RPSAction.Rock, emoji="✊", label="Rock", style=discord.ButtonStyle.green)
        view.add_item(rock_button)
        paper_button = RPSButton(rps_game, RPSAction.Paper, emoji="✋", label="Paper", style=discord.ButtonStyle.green)
        view.add_item(paper_button)
        scissors_button = RPSButton(rps_game, RPSAction.Scissors, emoji="✌️",
                                    label="Scissors", style=discord.ButtonStyle.green)
        view.add_item(scissors_button)

        # If playing against the bot, set target action randomly
        if target.id == self.bot.user.id:
            rps_game.target_action = random.choice(list(RPSAction))

        await view.send(interaction)

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
            await interaction.response.send_message(
                f"No u. (∩òᗝó)⊃ --==({item})                                                                   "
                f"--==({item})Д⨱)∩ {interaction.user.mention}")
            return

        # Throw the item, giving the target a prompt to catch it
        allowed_mentions = discord.AllowedMentions()
        allowed_mentions.users = [member]
        throwing = Throwing(interaction.user, member)
        view = DefaultView()
        view.add_item(CatchButton(throwing))
        await interaction.response.send_message(
            content=f"{interaction.user.mention} (∩òᗝó)⊃ --==({item})                                             "
                    f"∩(óᗝò)∩ " + member.mention,
            view=view, allowed_mentions=allowed_mentions)

        # Moves the item closer
        await asyncio.sleep(2)
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃                     --==({item})                         "
                    f"∩(óᗝò)∩ {member.mention}",
            view=view, allowed_mentions=allowed_mentions)

        # Change result depending on whether the target user caught it or not
        await asyncio.sleep(2)
        if throwing.caught:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} (∩óᗝò)⊃                                                      "
                        f"({item})⸦(òᗝó⸦) {member.mention} has caught it!",
                view=None, allowed_mentions=allowed_mentions)
            return
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃                                                          "
                    f"--==({item})Д⨱)∩ {member.mention} got dunked!",
            view=None, allowed_mentions=allowed_mentions)

    @app_commands.command()
    @perms.check()
    async def stealuserpic(self, interaction, user: discord.User):
        await interaction.response.send_message(user.avatar_url)


async def setup(bot):
    await bot.add_cog(Seethreepio(bot))
