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

from typing import Self, cast

import discord
import discord.ext
import discord.ext.commands
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants


class Help(commands.Cog):
    """Provides information on how to use commands."""

    def __init__(self: Help, bot: commands.Bot) -> None:
        """
        Initializes the Help class with the provided bot instance.

        Args:
            bot (commands.Bot): The Discord bot instance.
        """
        self.bot = bot
        bot.remove_command("help")

    @app_commands.command()
    async def help(
        self: Self, interaction: discord.Interaction, *, command: str | None = None
    ) -> None:
        """
        Information on how to use commands.

        Args:
            interaction (discord.Interaction): The user interaction.
            command (str | None, optional): The name of a module or
                command. Defaults to None.
        """
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
            embed = await self.generate_command_list(module)
            await interaction.response.send_message(embed=embed)
            return

        # Check if specified argument is a command
        cmds = command.split(" ")
        cmd = self.bot.tree.get_command(cmds[0])
        if cmd:
            if isinstance(cmd, app_commands.Group):
                cmd_group = cast(app_commands.Group, cmd)
                for subcmd in cmds[1:]:
                    check = cmd_group.get_command(subcmd)
                    if not check:
                        break
                    cmd = check
            embed = await self.generate_command_info(cmd)
            await interaction.response.send_message(embed=embed)
            return

        # Output alert if argument is neither a valid module or command
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="There is no module or command with that name",
        )
        await interaction.response.send_message(embed=embed)

    async def generate_command_list(self: Self, module: commands.Cog) -> discord.Embed:
        """Get a list of commands from the selected module.

        Args:
            module (commands.Cog): The module to get the commands from.

        Returns:
            discord.Embed: The embed containing the command list.
        """
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

    async def generate_command_info(
        self: Self, command: app_commands.Command | app_commands.Group
    ) -> discord.Embed:
        """
        Gives you information on how to use a command.

        Args:
            command (app_commands.Command | app_commands.Group): The
                command to get info on.

        Returns:
            discord.Embed: The embed containing the command info.
        """
        # Add arguments if any exists
        try:
            command = cast(app_commands.Command, command)
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
            command = cast(app_commands.Group, command)
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
        """
        Filter out commands that users don't have permission for.

        Args:
            ctx (commands.Context): The context of the command.
            commands (list[commands.Command]): The list of commands to
                filter.

        Returns:
            list[commands.Command]: The filtered list of commands.
        """
        filtered_commands = []
        for command in commands:
            try:
                check = await command.can_run(ctx)
                if check:
                    filtered_commands.append(command)
            except discord.ext.commands.CommandError:
                pass
        return filtered_commands

    async def get_formatted_command_list(
        self: Self, commands: list[app_commands.Command | app_commands.Group]
    ) -> tuple[list[str], list[str]]:
        """
        Format the command list to look pretty.

        Args:
            commands (list[app_commands.Command | app_commands.Group]):
                The list of commands.

        Returns:
            tuple[list[str], list[str]]: The formatted command list.
        """
        command_group_output = []
        command_output = []
        for command in commands:
            # Add as command if it is not a group
            if isinstance(command, app_commands.Command):
                # Add arguments if any exists
                arguments = ""
                for param in command.parameters:
                    if param.required:
                        arguments += f" <{param.name}>"
                    else:
                        arguments += f" [{param.name}]"
            else:
                arguments = ""

            command_output.append(f"`{command.name}{arguments}`: {command.description}")

            # Add as group
            if isinstance(command, app_commands.Group):
                command_group_output.append(f"`{command.name}`: {command.description}")

        return command_output, command_group_output


async def setup(bot: commands.Bot) -> None:
    """
    Load the Help cog.

    Args:
        bot (commands.Bot): The Discord bot instance.
    """
    await bot.add_cog(Help(bot))
