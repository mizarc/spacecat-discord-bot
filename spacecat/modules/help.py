"""
Module for providing information on how to use commands.

This module adds a new command, /help, which takes an optional argument,
the name of a module or command. If the argument is not provided, the
help menu is shown, which displays all the modules and their
descriptions. If the argument is a module, the help menu for that module
is shown, which lists all the commands in that module. If the argument
is a command, information about how to use that command is shown.

This module also removes the default help command, as it conflicts with
the new command.
"""

from __future__ import annotations

from typing import Self

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants


class Help(commands.Cog):
    """Provides information on how to use commands."""

    def __init__(self: Help, bot: commands.Bot) -> None:
        """
        Initializes the Help class with the provided bot instance.

        Args:
            self (Self): The Help class instance.
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        bot.remove_command("help")

    @commands.Cog.listener()
    async def on_message(self: Self, message: str) -> None:
        """
        Listens for messages and <x>.

        Args:
            self (Self): The Help class instance.
            message (str): The message content.
        """
        for _ in self.bot.cogs.values():
            return

        if "wah" not in message.content:
            return

        ctx = await self.bot.get_context(message)
        await ctx.send(",".join(str(command.name) for command in self.__cog_app_commands__))

    @app_commands.command()
    async def help(
        self: Self, interaction: discord.Interaction, *, command: str | None = None
    ) -> None:
        """Information on how to use commands."""
        # Generate main help menu
        if command is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.INFO.value,
                title=f"{constants.EmbedIcon.HELP} Help Menu",
                description="Type /help <category> to list all commands in the category "
                "(case sensitive)",
            )

            # Add all modules to the embed
            for cog in self.bot.cogs.values():
                cog_commands = cog.__cog_app_commands__
                if cog_commands:
                    embed.add_field(name=f"**{cog.qualified_name}**", value=f"{cog.description}")
            await interaction.response.send_message(embed=embed)
            return

        # Check if specified argument is actually a module
        module = self.bot.get_cog(command)
        if module:
            embed = await self.command_list(module)
            await interaction.response.send_message(embed=embed)
            return

        # Check if specified argument is a command
        cmds = command.split(" ")
        cmd = self.bot.tree.get_command(cmds[0])
        if cmd:
            for subcmd in cmds[1:]:
                check = cmd.get_command(subcmd)
                if not check:
                    break
                cmd = check
            embed = await self.command_info(cmd)
            await interaction.response.send_message(embed=embed)
            return

        # Output alert if argument is neither a valid module or command
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="There is no module or command with that name",
        )
        await interaction.response.send_message(embed=embed)

    async def command_list(self: Self, module: commands.Cog) -> discord.Embed:
        """Get a list of commands from the selected module."""
        command_output, command_group_output = await self.get_formatted_command_list(
            module.__cog_app_commands__
        )

        # Create embed
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.HELP} {module.qualified_name} Commands",
            description="Type !help <command> for more info on a command",
        )

        if command_group_output:
            embed.add_field(name="**Command Groups**", value="\n".join(command_group_output))

        if command_output:
            embed.add_field(name="**Commands**", value="\n".join(command_output), inline=False)

        return embed

    async def command_info(self: Self, command: commands.Command) -> discord.Embed:
        """Gives you information on how to use a command."""
        # Add arguments if any exists
        try:
            if len(command._params) > 0:  # noqa: SLF001
                arguments = ""
                for param in command._params.values():  # noqa: SLF001
                    if param.required:
                        arguments += f" <{param.name}>"
                    else:
                        arguments += f" [{param.name}]"
            else:
                arguments = ""

            # Add base command entry with command name and usage
            embed = discord.Embed(
                colour=constants.EmbedStatus.INFO.value,
                title=f"{constants.EmbedIcon.HELP} {command.qualified_name.title()} Usage",
                description=f"```{command.qualified_name}{arguments}```",
            )

            # Add commnand description field
            if command.description:
                embed.add_field(name="Description", value=command.description, inline=False)
        except AttributeError:
            # Add base command entry with command name and usage
            embed = discord.Embed(
                colour=constants.EmbedStatus.INFO.value,
                title=f"{constants.EmbedIcon.HELP} {command.qualified_name.title()} Subcommands",
            )

            subcommand_output, subcommand_group_output = await self.get_formatted_command_list(
                command.commands
            )

            if subcommand_group_output:
                embed.add_field(name="Subcommand Groups", value="\n".join(subcommand_group_output))

            if subcommand_output:
                embed.add_field(
                    name="Subcommands", value="\n".join(subcommand_output), inline=False
                )

        return embed

    async def filter_commands(
        self: Self, ctx: commands.Context, commands: list[commands.Command]
    ) -> list[commands.Command]:
        """Filter out commands that users don't have permission for."""
        filtered_commands = []
        for command in commands:
            try:
                check = await command.can_run(ctx)
                if check:
                    filtered_commands.append(command)
            except discord.ext.commands.CommandError:  # noqa: PERF203
                pass
        return filtered_commands

    async def get_formatted_command_list(
        self: Self, commands: list[commands.Command]
    ) -> tuple[list[str], list[str]]:
        """Format the command list to look pretty."""
        command_group_output = []
        command_output = []
        for command in commands:
            # Add as command if it is not a group
            if hasattr(command, "_params") and command._params:
                # Add arguments if any exists
                arguments = ""
                for param in command._params.values():
                    if param.required:
                        arguments += f" <{param.name}>"
                    else:
                        arguments += f" [{param.name}]"
            else:
                arguments = ""

            command_output.append(f"`{command.name}{arguments}`: {command.description}")

            # Add as group
            if not hasattr(command, "_params") or not command._params:
                command_group_output.append(f"`{command.name}`: {command.description}")

        return command_output, command_group_output


async def setup(bot: commands.Bot) -> None:
    """
    Load the Help cog.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(Help(bot))
