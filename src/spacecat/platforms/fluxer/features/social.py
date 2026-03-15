"""
This module provides fun games for users to play.

Features within this module must be fun little tools or games that the
user can play with their friends. Notable tools include the dice roll
which can be used for things like DnD or general decision making. Games
that are fun to play include the Rock Paper Scissors game.
"""

from __future__ import annotations

import enum
from typing import NamedTuple, Self, cast

import fluxer

from spacecat.platforms.fluxer.helpers import constants, permissions
import spacecat.core.features.social as core_social


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
            self: RPSGame, challenger: fluxer.User | fluxer.Member, target: fluxer.User
    ) -> None:
        """
        Represents a game of Rock Paper Scissors.

        Attributes:
            challenger (fluxer.User): The user who challenged the
                target user.
            target (fluxer.User): The user who is being challenged.
            challenger_action (RPSAction or None): The action chosen by
                the challenger.
            target_action (RPSAction or None): The action chosen by the
                target.
        """
        self.challenger: fluxer.User | fluxer.Member = challenger
        self.target: fluxer.User = target
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

    def play_action(self: Self, user: fluxer.abc.User, action: RPSAction) -> bool:
        """
        Updates the game state with the given action chosen by the user.

        Args:
            user (fluxer.User): The user who made the action.
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

    def get_winner(self: Self) -> fluxer.abc.User | None:
        """
        Determines the winner of a game based on player actions.

        Returns:
            fluxer.User | None: The winning player, or None if the
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


# Note: Button-based interactive features are not available in fluxer
# These classes are kept for compatibility but may not work
class RPSButton:
    """Placeholder for RPS button functionality."""

    def __init__(self, *args, **kwargs):
        pass

    async def callback(self, *args, **kwargs):
        pass


class CatchButton:
    """Placeholder for catch button functionality."""

    def __init__(self, *args, **kwargs):
        pass

    async def callback(self, *args, **kwargs):
        pass


class Fun(fluxer.Cog):
    """Random text response based features."""

    def __init__(self: Fun, bot: fluxer.Bot) -> None:
        """
        Initializes a new instance of the Fun class.

        Args:
            bot (fluxer.Bot): The bot instance.
        """
        super().__init__(bot)
        # self.throwings: dict[int, Throwing] = {}

    @fluxer.Cog.command()
    @permissions.check()
    async def coinflip(self: Self, ctx) -> None:
        """
        Simulates a coin flip.

        Args:
            ctx: The command context.
        """
        message = core_social.coinflip()
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def diceroll(self: Self, ctx, sides: int = 6) -> None:
        """
        Simulates a dice roll with a given number of sides.

        Args:
            ctx: The command context.
            sides (int, optional): The number of sides on the dice.
                Defaults to 6.
        """
        message = core_social.diceroll(int(sides))
        await ctx.reply(message)

    @fluxer.Cog.command()
    @permissions.check()
    async def throw(
            self: Self,
            ctx,
            member: fluxer.Member,
            *,
            item: str | None = None,
    ) -> None:
        """
        Throws an item at a specified member.

        Parameters:
            ctx: The command context.
            member (fluxer.Member): The member to throw the item at.
            item (str, optional): The item to throw. Defaults to "O".
        """
        if item is None:
            item = "O"

        # Have the bot throw the item at the user if the bot is targeted
        if self.bot.user and member.id == self.bot.user.id:
            await ctx.reply(
                f"No u. {ctx.author.mention} ∩(óᗝò)∩"
                f"                                 ({item})==-- ⸦(òᗝó∩) "
            )
            return

        # Have the item boomerang back at the user if they're throwing at themselves
        if member.id == ctx.author.id:
            await ctx.reply(
                f"But why? {ctx.author.mention} (∩òᗝó)⊃ --==({item})"
            )
            return

        # Simple throw animation (simplified from the original)
        await ctx.reply(
            f"{ctx.author.mention} (∩òᗝó)⊃ --==({item})"
            f"                                             ∩(óᗝò)∩ {member.mention} got dunked!"
        )


async def setup(bot: fluxer.Bot) -> None:
    """
    Load the Fun cog.

    Args:
        bot (fluxer.Bot): The Fluxer bot instance.
    """
    await bot.add_cog(Fun(bot))
