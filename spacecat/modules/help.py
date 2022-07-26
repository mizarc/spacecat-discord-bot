import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants


class Help(commands.Cog):
    """Information on how to use commands"""
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command('help')

    @commands.Cog.listener()
    async def on_message(self, message):
        for cog in self.bot.cogs.values():
            return

        if "wah" not in message.content:
            return

        ctx = await self.bot.get_context(message)
        await ctx.send(",".join(str(command.name) for command in self.__cog_app_commands__))

    @app_commands.command()
    async def help(self, interaction, *, command: str = None):
        """Information on how to use commands"""
        # Generate main help menu
        if command is None:
            embed = discord.Embed(
                colour=constants.EmbedStatus.INFO.value,
                title=f"{constants.EmbedIcon.HELP} Help Menu",
                description="Type /help <category> to list all commands in the category (case sensitive)")

            # Add all modules to the embed
            for cog in self.bot.cogs.values():
                #commands = await self.filter_commands(ctx, module.get_commands())
                cog_commands = cog.__cog_app_commands__
                if cog_commands:
                    embed.add_field(
                        name=f"**{cog.qualified_name}**",
                        value=f"{cog.description}")
            await interaction.response.send_message(embed=embed)
            return

        # Check if specified argument is actually a module
        module = self.bot.get_cog(command)
        if module:
            embed = await self.command_list(module)
            await interaction.response.send_message(embed=embed)
            return

        # Check if specified argument is a command
        cmds = command.split(' ')
        cmd = self.bot.tree.get_command(cmds[0])
        if cmd:
            for subcmd in cmds[1:]:
                check = cmd.all_commands.get(subcmd)
                if not check:
                    break
                cmd = check
            embed = await self.command_info(cmd)
            await interaction.response.send_message(embed=embed)
            return

        # Output alert if argument is neither a valid module or command
        embed = discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description="There is no module or command with that name")
        await interaction.response.send_message(embed=embed)

    async def command_list(self, module):
        """Get a list of commands from the selected module"""
        # Get all the commands in the module. Alert if user doesn't
        # have permission to view any commands in the module
        #commands = await self.filter_commands(ctx, module.get_commands())
        #if not commands:
        #    embed = discord.Embed(
        #        colour=constants.EmbedStatus.FAIL.value,
        #        description="You don't have permission to view that module's help page")
        #    await ctx.send(embed=embed)
        #    return
        command_output, command_group_output = await self.get_formatted_command_list(module.__cog_app_commands__)

        # Create embed
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.HELP} {module.qualified_name} Commands",
            description="Type !help <command> for more info on a command")

        if command_group_output:
            embed.add_field(
                name="**Command Groups**",
                value="\n".join(command_group_output))

        if command_output:
            embed.add_field(
                name="**Commands**",
                value="\n".join(command_output),
                inline=False)

        return embed

    async def command_info(self, command):
        """Gives you information on how to use a command"""
        # Alert if user doesn't have permission to use that command
        #check = await self.filter_commands(ctx, [command])
        #if not check:
        #    embed = discord.Embed(
        #        colour=constants.EmbedStatus.FAIL.value,
        #        description="You don't have permission to view that command's help page")
        #    await ctx.send(embed=embed)
        #    return

        # Check for command parents to use as prefix and signature as suffix
        #if command.qualified_Name:
        #    parents = f'{command.full_parent_name} '
        #else:
        #    parents = ''
        # Add arguments if any exists
        if len(command._params) > 0:
            arguments = ''
            for param in command._params.values():
                if param.required:
                    arguments += f' <{param.name}>'
                else:
                    arguments += f' [{param.name}]'
        else:
            arguments = ''

        # Add base command entry with command name and usage
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.HELP} {command.qualified_name.title()}",
            description=f"```{command.qualified_name}{arguments}```")

        # Get all aliases of command from database
        #db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        #cursor = db.cursor()
        #value = (ctx.guild.id, command.name)
        #cursor.execute(
        #    'SELECT alias FROM command_alias '
        #    'WHERE server_id=? AND command=?', value)
        #aliases = cursor.fetchall()
        #db.close()

        # Add commnand description field
        if command.description:
            embed.add_field(name="Description", value=command.description, inline=False)

        # Add command alias field
        #if aliases:
        #    alias_output = []
        #    for alias in aliases:
        #        alias_output.append(f"`{alias[0]}`")
        #    embed.add_field(name="Aliases", value=", ".join(alias_output))

        # Add command subcommand field
        try:
            #subcommands = await self.filter_commands(
            #    ctx, command.all_commands.values())
            subcommand_output, subcommand_group_output = await self.get_formatted_command_list(command.commands)

            if subcommand_group_output:
                embed.add_field(
                    name="Subcommand Groups",
                    value='\n'.join(subcommand_group_output))

            if subcommand_output:
                embed.add_field(
                    name="Subcommands",
                    value='\n'.join(subcommand_output),
                    inline=False)
        except AttributeError:
            pass

        return embed

    async def filter_commands(self, ctx, commands):
        """Filter out commands that users don't have permission to use"""
        filtered_commands = []
        for command in commands:
            try:
                check = await command.can_run(ctx)
                if check:
                    filtered_commands.append(command)
            except discord.ext.commands.CommandError:
                pass
        return filtered_commands

    async def get_formatted_command_list(self, commands):
        """Format the command list to look pretty"""
        command_group_output = []
        command_output = []
        for command in commands:
            # Add as command if it is not a group
            try:
                # Add arguments if any exists
                if len(command._params) > 0:
                    arguments = ''
                    for param in command._params.values():
                        if param.required:
                            arguments += f' <{param.name}>'
                        else:
                            arguments += f' [{param.name}]'
                else:
                    arguments = ''
                command_output.append(f"`{command.name}{arguments}`: {command.description}")

            # Add as group
            except AttributeError:
                command_group_output.append(f"`{command.name}`: {command.description}")

        return command_output, command_group_output


async def setup(bot):
    await bot.add_cog(Help(bot))
