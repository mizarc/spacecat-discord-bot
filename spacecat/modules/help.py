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
    async def help(self, ctx, command=None):
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
        cmd = self.bot.all_commands.get(command)
        if cmd:
            await self.command_info(ctx, cmd)

        # Output alert if argument is neither a valid module or command
        embed = discord.Embed(
            colour=settings.embed_type('warn'),
            description=f"There is no module or command with that name")
        await ctx.send(embed=embed)

    async def command_list(self, ctx, module):
        """Get a list of commands from the selected module"""
        commands = module.get_commands()
        command_output = []
        for command in commands:
            if command.signature:
                arguments = f' {command.signature}'
            else:
                arguments = ''
            command_output.append(f"`{command.name}{arguments}`: {command.short_doc}")

        # Create embed
        embed = discord.Embed(colour=settings.embed_type('info'),
        description=f"Type !help <command> for more info on a command")
        image = discord.File(
            settings.embed_icons("help"), filename="image.png")
        embed.set_author(name="Help Menu", icon_url="attachment://image.png")

        embed.add_field(
            name=f"**Commands**",
            value="\n".join(command_output))
        await ctx.send(file=image, embed=embed)

    async def command_info(self, ctx, command):
        """Gives you information on how to use a command"""
        # Add base command entry with command name and usage
        if command.signature:
            arguments = f' {command.signature}'
        else:
            arguments = ''
        embed = discord.Embed(colour=settings.embed_type('info'),
        description=f"```{command.name}{arguments}```")
        embed.set_author(name=command.name.title(), icon_url="attachment://image.png")

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

        image = discord.File(
            settings.embed_icons("help"), filename="image.png")
        await ctx.send(file=image, embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))