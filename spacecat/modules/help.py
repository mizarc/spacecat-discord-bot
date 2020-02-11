import sqlite3

import discord
from discord.ext import commands

from spacecat.helpers import settings


class Help(commands.Cog):
    """Information on how to use commands"""
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command('help')

    @commands.command()
    async def help(self, ctx, *, command=None):
        """Information on how to use commands"""
        # Generate main help menu
        if command is None:
            embed = discord.Embed(colour=settings.embed_type('info'),
            description=f"Type !help <module> to list all commands in the module")
            image = discord.File(
                settings.embed_icons("help"), filename="image.png")
            embed.set_author(name="Help Menu", icon_url="attachment://image.png")

            # Add all modules to the embed
            modules = self.bot.cogs
            for module in modules.values():
                embed.add_field(
                    name=f"**{module.qualified_name}**",
                    value=f"{module.description}")
            await ctx.send(file=image, embed=embed)
            return

        # Check if specified argument is actually a module
        module = self.bot.get_cog(command)
        if module:
            await self.command_list(ctx, module)
            return

        # Check if specified argument is a command
        cmds = command.split(' ')
        cmd = self.bot.all_commands.get(cmds[0])
        if cmd:
            for subcmd in cmds[1:]:
                check = cmd.all_commands.get(subcmd)
                if not check:
                    break
                cmd = check
            await self.command_info(ctx, cmd)
            return
        
        # Output alert if argument is neither a valid module or command
        embed = discord.Embed(
            colour=settings.embed_type('warn'),
            description=f"There is no module or command with that name")
        await ctx.send(embed=embed)

    async def command_list(self, ctx, module):
        """Get a list of commands from the selected module"""
        commands = module.get_commands()
        command_output, command_group_output = await self.get_formatted_command_list(commands)

        # Create embed
        embed = discord.Embed(colour=settings.embed_type('info'),
        description=f"Type !help <command> for more info on a command")
        image = discord.File(
            settings.embed_icons("help"), filename="image.png")
        embed.set_author(
            name=f"{module.qualified_name} Commands",
            icon_url="attachment://image.png")

        if command_group_output:
            embed.add_field(
                name=f"**Command Groups**",
                value="\n".join(command_group_output))

        if command_output:
            embed.add_field(
                name=f"**Commands**",
                value="\n".join(command_output),
                inline=False)
            
        await ctx.send(file=image, embed=embed)

    async def command_info(self, ctx, command):
        """Gives you information on how to use a command"""
        # Check for command parents to use as prefix and signature as suffix
        if command.full_parent_name:
            parents = f'{command.full_parent_name} '
        else:
            parents = ''
        if command.signature:
            arguments = f' {command.signature}'
        else:
            arguments = ''

        # Add base command entry with command name and usage
        embed = discord.Embed(
            colour=settings.embed_type('info'),
            description=f"```{parents}{command.name}{arguments}```")
        embed.set_author(
            name=f"{parents.title()}{command.name.title()}",
            icon_url="attachment://image.png")

        # Get all aliases of command from database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, command.name)
        cursor.execute("SELECT alias FROM command_alias WHERE server_id=? AND command=?", value)
        aliases = cursor.fetchall()
        db.close()

        # Add command alias field
        if aliases:
            alias_output = []
            for alias in aliases:
                alias_output.append(f"`{alias[0]}`")
            embed.add_field(name="Aliases", value=", ".join(alias_output))

        # Add commnand description field
        if command.help:
            embed.add_field(name="Description", value=command.help, inline=False)

        # Add command subcommand field
        try:
            subcommands = command.all_commands.values()
            subcommand_output, subcommand_group_output = await self.get_formatted_command_list(subcommands)

            if subcommand_group_output:
                embed.add_field(
                    name="Subcommand Groups",
                    value='\n'.join(subcommand_group_output))
            
            if subcommand_output:
                embed.add_field(
                    name="Subcommands",
                    value='\n'.join(subcommand_output),
                    inline=False)
        except:
            pass

        image = discord.File(
            settings.embed_icons("help"), filename="image.png")
        await ctx.send(file=image, embed=embed)


    async def get_formatted_command_list(self, commands):
        """Format the command list to look pretty"""
        command_group_output = []
        command_output = []
        for command in commands:
            # Check if command has arguments
            if command.signature:
                arguments = f' {command.signature}'
            else:
                arguments = ''

            # Categorise commands and command groups
            command_format = f"`{command.name}{arguments}`: {command.short_doc}"
            try:
                command.all_commands
                command_group_output.append(command_format)
            except AttributeError:
                command_output.append(command_format)
        return command_output, command_group_output


def setup(bot):
    bot.add_cog(Help(bot))