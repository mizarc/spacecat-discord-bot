"""
This module provides fun games for users to play.

Features within this module must be fun little tools or games that the
user can play with their friends. Notable tools include the dice roll
which can be used for things like DnD or general decision making. Games
that are fun to play include the Rock Paper Scissors game.
"""

from __future__ import annotations

import asyncio
import enum
import random
import time
from typing import NamedTuple, Self, cast

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button

from spacecat.helpers import constants, permissions
from spacecat.helpers.views import DefaultView


class RPSAction(enum.Enum):
    """Enum representing possible actions in Rock Paper Scissors."""

    Rock = "✊"
    Paper = "✋"
    Scissors = "✌️"


class RPSGame:
    """
    Represents a game of Rock Paper Scissors.

    This class allows users to challenge each other to a game of Rock
    Paper Scissors. It keeps track of the players, their actions, and
    determines the winner based on the game rules.
    """

    def __init__(
        self: RPSGame, challenger: discord.User | discord.Member, target: discord.User
    ) -> None:
        """
        Represents a game of Rock Paper Scissors.

        Attributes:
            challenger (discord.User): The user who challenged the
                target user.
            target (discord.User): The user who is being challenged.
            challenger_action (RPSAction or None): The action chosen by
                the challenger.
            target_action (RPSAction or None): The action chosen by the
                target.
        """
        self.challenger: discord.User | discord.Member = challenger
        self.target: discord.User = target
        self.challenger_action: RPSAction | None = None
        self.target_action: RPSAction | None = None

    def has_both_chosen(self: Self) -> bool:
        """
        Check if both players have chosen an action.

        Returns:
            bool: True if both players have chosen an action, False
                otherwise.
        """
        if self.challenger_action and self.target_action:
            return True
        return False

    def play_action(self: Self, user: discord.abc.User, action: RPSAction) -> bool:
        """
        Updates the game state with the given action chosen by the user.

        Args:
            user (discord.User): The user who made the action.
            action (RPSAction): The action chosen by the user.

        Returns:
            bool: True if the action was successfully added to the game
                state, False otherwise.
        """
        if user == self.challenger and not self.challenger_action:
            self.challenger_action = action
            return True
        if user == self.target and not self.target_action:
            self.target_action = action
            return True
        return False

    def get_winner(self: Self) -> discord.abc.User | None:
        """
        Determines the winner of a game based on player actions.

        Returns:
            discord.User | None: The winning player, or None if the
                result is a tie.
        """
        if not self.has_both_chosen():
            return None
        challenger_action: RPSAction = cast(RPSAction, self.challenger_action)
        target_action: RPSAction = cast(RPSAction, self.target_action)

        class Response(NamedTuple):
            first: RPSAction
            second: RPSAction

        outcomes = {
            Response(RPSAction.Rock, RPSAction.Scissors): self.challenger,
            Response(RPSAction.Paper, RPSAction.Rock): self.challenger,
            Response(RPSAction.Scissors, RPSAction.Paper): self.challenger,
        }

        if self.challenger_action == self.target_action:
            return None
        return outcomes.get(Response(challenger_action, target_action))


class RPSButton(Button):
    """Represents a button for the Rock Paper Scissors game."""

    def __init__(
        self: RPSButton,
        rps_game: RPSGame,
        action: RPSAction,
        label: str,
        emoji: discord.PartialEmoji | str,
        style: discord.ButtonStyle,
    ) -> None:
        """
        Initializes a new instance of the RPSButton class.

        Args:
            rps_game (RPSGame): The Rock Paper Scissors game instance.
            action (RPSAction): The action associated with the button.
            label (str): The label text for the button.
            emoji (typing.Union[discord.PartialEmoji, str]): The emoji for the button.
            style (discord.ButtonStyle): The style of the button.
        """
        super().__init__(label=label, emoji=emoji, style=style)
        self.rps_game = rps_game
        self.action = action

    async def callback(self: Self, interaction: discord.Interaction) -> None:
        """
        Callback function for the RPSButton.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        await interaction.response.defer()

        # Tell non-players that they cannot play this game
        if interaction.user not in (self.rps_game.challenger, self.rps_game.target):
            await interaction.followup.send(
                content="You are not included in this game.", ephemeral=True
            )
            return

        # Alert user of choice
        action_result = self.rps_game.play_action(interaction.user, self.action)
        if action_result:
            await interaction.followup.send(
                content=f"You have chosen {self.action.value}", ephemeral=True
            )
        else:
            await interaction.followup.send(
                content="You have already made a selection.", ephemeral=True
            )

        # Declare winner
        challenger_action = self.rps_game.challenger_action
        target_action = self.rps_game.target_action
        if challenger_action and target_action:
            winner = self.rps_game.get_winner()
            win_text = f"<@{winner.id}> has won!" if winner else "It's a draw!"
            embed = discord.Embed(
                colour=constants.EmbedStatus.GAME.value,
                title="Rock Paper Scissors",
                description=f"<@{self.rps_game.challenger.id}> "
                f"{challenger_action.value} vs {target_action.value} "
                f"<@{self.rps_game.target.id}>\n\n{win_text}",
            )
            await interaction.followup.send(embed=embed)

            # Disable buttons after game has completed
            if self.view is not None:
                buttons = self.view.children
                for button in buttons:
                    button.disabled = True
                self.disabled = True
                await interaction.edit_original_response(view=self.view)

    async def on_timeout(self: Self) -> None:
        """Disables the button on timeout."""
        self.disabled = True


class Throwing:
    """Represents a throwing action."""

    def __init__(self: Throwing, thrower: discord.abc.User, target: discord.abc.User) -> None:
        """
        Initialises a throwing instance.

        Args:
            thrower (discord.Member): The user who is throwing.
            target (discord.Member): The user who is being thrown at.
            timeout_time (float): The time at which the throw times out.
            caught (bool): Whether the throw was caught.
        """
        self.thrower = thrower
        self.target = target
        self.timeout_time = time.time() + 5.0
        self.caught = False


class CatchButton(Button):
    """Represents a button for catching a thrown item."""

    def __init__(self: CatchButton, throwing: Throwing) -> None:
        """
        Initializes a CatchButton object.

        Args:
            throwing (Throwing): The Throwing object representing the
                throwing action.
        """
        super().__init__(label="Catch", emoji="🫴", style=discord.ButtonStyle.green)
        self.throwing = throwing

    async def callback(self: Self, interaction: discord.Interaction) -> None:
        """
        Callback that generates a text response on button press.

        This is designed to send an ephemeral message to the user that
        pressed the button, with a message indicating whether they are
        catching or not the target.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        if self.throwing.target.id is not interaction.user.id:
            await interaction.response.send_message("You are not the target.", ephemeral=True)
            return

        self.throwing.caught = True
        await interaction.response.send_message("You are prepared to catch.", ephemeral=True)


class Seethreepio(commands.Cog):
    """Random text response based features."""

    def __init__(self: Seethreepio, bot: commands.Bot) -> None:
        """
        Initializes a new instance of the Seethreepio class.

        Args:
            bot (commands.Bot): The bot instance.
        """
        self.bot = bot
        self.throwings: dict[int, Throwing] = {}

    @app_commands.command()
    @permissions.check()
    async def echo(self: Self, interaction: discord.Interaction, *, message: str) -> None:
        """Repeats a given message.

        Args:
            interaction (discord.Interaction): The interaction object.
            message (str): The message to repeat.
        """
        await interaction.response.send_message(message)

    @app_commands.command()
    async def coinflip(self: Self, interaction: discord.Interaction) -> None:
        """
        Simulates a coin flip.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        coin = random.randint(0, 1)  # noqa: S311
        if coin:
            await interaction.response.send_message("Heads")
        else:
            await interaction.response.send_message("Tails")

    @app_commands.command()
    async def diceroll(self: Self, interaction: discord.Interaction, sides: int = 6) -> None:
        """
        Simulates a dice roll with a given number of sides.

        Args:
            interaction (discord.Interaction): The interaction object.
            sides (int, optional): The number of sides on the dice.
                Defaults to 6.
        """
        result = random.randint(1, sides)  # noqa: S311
        await interaction.response.send_message(f"You rolled a {result} on a {sides} sided dice")

    @app_commands.command()
    async def rps(self: Self, interaction: discord.Interaction, target: discord.User) -> None:
        """
        Starts a game of Rock Paper Scissors against a target user.

        Args:
            interaction (discord.Interaction): The interaction object.
            target (discord.User): The user to challenge.
        """
        embed = discord.Embed(
            colour=constants.EmbedStatus.GAME.value,
            title="Rock Paper Scissors",
            description=f"<@{target.id}> has been challenged by <@{interaction.user.id}>. "
            "Make your moves.",
        )

        rps_game = RPSGame(interaction.user, target)

        # Add buttons
        view = DefaultView(embed=embed)
        rock_button = RPSButton(
            rps_game,
            RPSAction.Rock,
            emoji="✊",
            label="Rock",
            style=discord.ButtonStyle.green,
        )
        view.add_item(rock_button)
        paper_button = RPSButton(
            rps_game,
            RPSAction.Paper,
            emoji="✋",
            label="Paper",
            style=discord.ButtonStyle.green,
        )
        view.add_item(paper_button)
        scissors_button = RPSButton(
            rps_game,
            RPSAction.Scissors,
            emoji="✌️",
            label="Scissors",
            style=discord.ButtonStyle.green,
        )
        view.add_item(scissors_button)

        # If playing against the bot, set target action randomly
        if target and self.bot.user and target.id == self.bot.user.id:
            rps_game.target_action = random.choice(list(RPSAction))  # noqa: S311

        await view.send(interaction)

    @app_commands.command()
    @permissions.check()
    async def throw(
        self: Self,
        interaction: discord.Interaction,
        member: discord.Member,
        *,
        item: str | None = None,
    ) -> None:
        """
        Throws an item at a specified member.

        Parameters:
            interaction (discord.Interaction): The interaction object.
            member (discord.Member): The member to throw the item at.
            item (str, optional): The item to throw. Defaults to "O".
        """
        if item is None:
            item = "O"
        allowed_mentions = discord.AllowedMentions()
        allowed_mentions.users = False

        # Have the bot throw the item at the user if the bot is targeted
        if self.bot.user and member.id == self.bot.user.id:
            await interaction.response.send_message(
                f"No u. {interaction.user.mention} ∩(óᗝò)∩"
                f"                                 ({item})==-- ⸦(òᗝó∩) ",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"No u. {interaction.user.mention} ∩(óᗝò)∩"
                f"                   ({item})==-                 ⸦(òᗝó∩)",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"No u. {interaction.user.mention} ∩(⨱Д({item})==--"
                f"                                         ⸦(òᗝó∩)",
                allowed_mentions=allowed_mentions,
            )
            return

        # Have the item boomerang back at the user if they're throwing at themselves
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                f"But why? {interaction.user.mention} (∩òᗝó)⊃ --==({item})",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"But why? {interaction.user.mention} (∩òᗝó)⊃"
                f"                 -=({item})",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"But why? {interaction.user.mention} (∩òᗝó)⊃"
                f"                                ({item})",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"But why? {interaction.user.mention} ∩(óᗝò)∩"
                f"                    ({item})=-",
                allowed_mentions=allowed_mentions,
            )
            await asyncio.sleep(1)
            await interaction.edit_original_response(
                content=f"But why? {interaction.user.mention} ∩(⨱Д({item})==--",
                allowed_mentions=allowed_mentions,
            )
            return

        # Throw the item, giving the target a prompt to catch it
        allowed_mentions.users = [member]
        throwing = Throwing(interaction.user, member)
        view = DefaultView()
        view.add_item(CatchButton(throwing))
        await interaction.response.send_message(
            content=f"{interaction.user.mention} (∩òᗝó)⊃ --==({item})"
            f"                                             ∩(óᗝò)∩ " + member.mention,
            view=view,
            allowed_mentions=allowed_mentions,
        )

        # Moves the item closer
        await asyncio.sleep(2)
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃"
            f"                     --==({item})                         ∩(óᗝò)∩ {member.mention}",
            view=view,
            allowed_mentions=allowed_mentions,
        )

        # Change result depending on whether the target user caught it or not
        await asyncio.sleep(2)
        if throwing.caught:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention} (∩óᗝò)⊃"
                f"                                                      "
                f"({item})⸦(òᗝó⸦) {member.mention} has caught it!",
                view=None,
                allowed_mentions=allowed_mentions,
            )
            return
        await interaction.edit_original_response(
            content=f"{interaction.user.mention} (∩òᗝó)⊃"
            f"                                                     "
            f"--==({item})Д⨱)∩ {member.mention} got dunked!",
            view=None,
            allowed_mentions=allowed_mentions,
        )

    @app_commands.command()
    @permissions.check()
    async def stealuserpic(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """
        Steals the profile picture of a target user.

        Args:
            interaction (discord.Interaction): The interaction object.
            user (discord.User): The user whose avatar URL is to be retrieved.
        """
        if user.avatar is not None:
            await interaction.response.send_message(user.avatar.url)


async def setup(bot: commands.Bot) -> None:
    """
    Load the Seethreepio cog.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(Seethreepio(bot))
