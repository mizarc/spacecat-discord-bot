import configparser
from itertools import islice
import os
import sqlite3

import discord
from discord.ext import commands
import toml

from spacecat.helpers import constants
from spacecat.helpers import perms


class Configuration(commands.Cog):
    """Modify Discord wide bot settings"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Auto generate the permissions config category with
        # default (@everyone) role
        config = toml.load(constants.DATA_DIR + 'config.toml')
        try:
            config['permissions']
        except KeyError:
            config['permissions'] = {}
        try:
            config['permissions']['default']
        except KeyError:
            config['permissions']['default'] = []

        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            prefix = ctx.prefix
            cmd = ctx.message
            cmd_name = cmd.content.split()[0][len(prefix):]
            cmd_args = cmd.content.split()[1:]

            # Query if command exists as an alias in database
            db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
            cursor = db.cursor()
            query = (ctx.guild.id, cmd_name)
            cursor.execute(f"SELECT command FROM command_alias WHERE server_id=? AND alias=?", query)
            result = cursor.fetchall()
            db.close()

            # Use command linked to alias to replace command process
            if result:
                cmd.content = f"{prefix}{result[0][0]} {' '.join(cmd_args)}"
                await self.bot.process_commands(cmd)

    @commands.command()
    @perms.exclusive()
    async def status(self, ctx, status_name):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        status = discord.Status[status_name]
        activity_name = config['base']['activity_type']
        try:
            activity = discord.Activity(
                type=discord.ActivityType[activity_name],
                name=config['base']['activity_name'])
        except KeyError:
            activity = None
        
        # Check if valid status name was used
        if status == None:
            embed = discord.Embed(colour=constants.EmbedStatus.FAIL, description=f"That's not a valid status")
            await ctx.send(embed=embed)
            return

        if activity:
            await self.bot.change_presence(status=status, activity=activity)
        else:
            await self.bot.change_presence(status=status)

        config['base']['status'] = status_name
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.command()
    @perms.exclusive()
    async def activity(self, ctx, activity_name, *, name):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        activity_type = discord.ActivityType[activity_name]
        activity = discord.Activity(type=activity_type, name=name, url="https://www.twitch.tv/yeet")
        try:
            status = config['base']['status']
        except KeyError:
            status = None

        if activity_type == None:
            embed = discord.Embed(colour=constants.EmbedStatus.FAIL, description=f"That's not a valid activity type")
            await ctx.send(embed=embed)
            return

        if status:
            await self.bot.change_presence(activity=activity, status=status)
        else:
            await self.bot.change_presence(activity=activity)


        config['base']['activity_type'] = activity_type
        config['base']['activity_name'] = name
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @commands.group(invoke_without_command=True)
    @perms.exclusive()
    async def permpreset(self, ctx):
        """
        Configure permission presets
        Permissions assigned to presets can be utilised by server
        administrators to simplify permission assignment
        """
        await ctx.invoke(self.permpreset_list)

    @permpreset.command(name='create')
    @perms.exclusive()
    async def permpreset_create(self, ctx, name):
        """Creates a new permission preset list"""
        config = toml.load(constants.DATA_DIR + 'config.toml')
        
        try:
            config['permissions'][name]
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL,
                description="There's already a preset with that name")
            await ctx.send(embed=embed)
            return
        except KeyError:
            pass

        config['permissions'][name] = []
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES,
            description=f"Added permission preset `{name}`")
        await ctx.send(embed=embed)

    @permpreset.command(name='destroy')
    @perms.exclusive()
    async def permpreset_destroy(self, ctx, name):
        """Completely deletes a preset and all its contents"""
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Alert if there's no preset with that name
        try:
            del config['permissions'][name]
        except:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL,
                description=f"There is no preset with the name `{name}`")
            await ctx.send(embed=embed)
            return

        if name == 'default':
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL,
                description=f"You cannot remove the default preset")
            await ctx.send(embed=embed)
            return

        # Apply changes and output result to user
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES,
            description=f"Deleted permission preset `{name}`")
        await ctx.send(embed=embed)

    @permpreset.command(name='add')
    @perms.exclusive()
    async def permpreset_add(self, ctx, preset, perm):
        """Adds a valid permission to a permission preset"""
        config = toml.load(constants.DATA_DIR + 'config.toml')
        perm_values = perm.split('.')
        skip = False

        # Add wildcard permission if it doesn't already exist
        if perm == '*':
            if perm in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"Permission preset `{preset}` "
                    "already has the wildcard permission")
                await ctx.send(embed=embed)
                return
            else:
                config['permissions'][preset].append('*')
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES,
                    description="Wildcard permission added to "
                    f"permission preset `{preset}`")
                await ctx.send(embed=embed)
                skip = True

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog = self.bot.get_cog(perm_values[0])

            # Check if non-wildcard permission has been chosen and move onto
            # the next section for command level perm handling
            if cog and perm_values[1] != '*':
                perm_values.pop(0)
     
            # Add permission group permission if it doesn't already exist
            elif cog and perm in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"`{preset}` already has the"
                    f"`{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return
            elif cog and perm not in config['permissions'][preset]:
                config['permissions'][preset].append(
                    f"{cog.qualified_name}.*")
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES,
                    description=f"Permission group `{cog.qualified_name}`"
                    f" added to preset `{preset}`")
                await ctx.send(embed=embed)
                skip = True

        # Check if permission is a command
        if not skip:
            command_perm = '.'.join(perm_values)
            
            # Exclude subcommand wildcard when checking if command exists
            if command_perm[-1] == '*':
                command = self.bot.get_command(command_perm[:-2].replace('.', ' '))
            else:
                command = self.bot.get_command(command_perm.replace('.', ' '))

            # Alert if no permission goes by that name after checking
            # both module and command names
            try:
                if not command or command.cog != cog:
                    embed = discord.Embed(
                        colour=constants.EmbedStatus.FAIL,
                        description=f"Permission does not exist. "
                        "Please enter a valid permission")
                    await ctx.send(embed=embed) 
                    return
            except UnboundLocalError:
                pass
                
            # Add command permission if it doesn't already exist
            full_permission = f"{command.cog.qualified_name}.{command_perm}"
            if full_permission in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"`{preset}` already has that permission")
                await ctx.send(embed=embed) 
                return
            else:
                config['permissions'][preset].append(
                    f"{command.cog.qualified_name}.{command_perm}")
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES,
                    description=f"Command `{command.cog.qualified_name}.{command_perm}` added to preset `{preset}`")
                await ctx.send(embed=embed)
            
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @permpreset.command(name='remove')
    @perms.exclusive()
    async def permpreset_remove(self, ctx, preset, perm):
        """Removes an existing permission from a preset"""
        config = toml.load(constants.DATA_DIR + 'config.toml')
        perm_values = perm.split('.')
        skip = False

        # Remove wildcard permission if it exists in preset entry
        if perm == '*':
            if perm in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"Preset `{preset}` doesn't have the "
                    "wildcard permission")
                await ctx.send(embed=embed) 
                return
            else:
                config['permissions'][preset].remove(perm)
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"Wildcard permission removed from preset "
                    f"`{preset}`")
                await ctx.send(embed=embed) 
                skip = True

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog = self.bot.get_cog(perm_values[0])

            # Check if non-wildcard permission has been chosen and move onto
            # the next section for command level perm handling
            if cog and perm_values[1] != '*':
                perm_values.pop(0)

            # Remove command group permission if it doesn't already exist
            elif cog and perm not in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES,
                    description=f"`{preset}` doesn't have the "
                    f"`{cog.qualified_name}` permission group")
                await ctx.send(embed=embed)
                return
            elif cog and perm in config['permissions'][preset]:
                config['permissions'][preset].remove(
                    f"{cog.qualified_name}.*")
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"Permission group `{cog.qualified_name}` "
                    f"removed from preset `{preset}`")
                await ctx.send(embed=embed)
                skip = True

        # Check if permission is a command
        if not skip:
            command_perm = '.'.join(perm_values)

            # Exclude subcommand wildcard when checking if command exists
            if command_perm[-1] == '*':
                command = self.bot.get_command(command_perm[:-2].replace('.', ' '))
            else:
                command = self.bot.get_command(command_perm.replace('.', ' '))

            # Alert if no permission goes by that name after checking
            # both module and command names
            try:
                if not command or command.cog != cog:
                    embed = discord.Embed(
                        colour=constants.EmbedStatus.FAIL,
                        description=f"Permission does not exist. "
                        "Please enter a valid permission")
                    await ctx.send(embed=embed) 
                    return
            except UnboundLocalError:
                pass

            # Add command permission if it doesn't already exist
            full_permission = f"{command.cog.qualified_name}.{command_perm}"
            if full_permission not in config['permissions'][preset]:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL,
                    description=f"`{preset}` doesn't have that permission")
                await ctx.send(embed=embed) 
                return
            else:
                config['permissions'][preset].remove(
                    f"{command.cog.qualified_name}.{command_perm}")
                embed = discord.Embed(
                    colour=constants.EmbedStatus.YES,
                    description=f"Command `{command.cog.qualified_name}."
                    f"{command_perm}` removed from preset `{preset}`")
                await ctx.send(embed=embed)
            
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)

    @permpreset.command(name='list')
    @perms.exclusive()
    async def permpreset_list(self, ctx):
        """List all available presets"""
        config = toml.load(constants.DATA_DIR + 'config.toml')
        perm_presets = config['permissions']

        # Format playlist songs into pretty list
        perm_presets_output = []
        for index, preset_name in enumerate(islice(perm_presets, 0, 10)):
            perm_presets_output.append(f"{index + 1}. {preset_name}")

        # Output list of presets in a pretty embed
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO,
            title=f"{constants.EmbedIcon.INFORMATION} Permission Presets")
        embed.add_field(
            name=f"{len(perm_presets)} available",
            value='\n'.join(perm_presets_output), inline=False)
        await ctx.send(embed=embed)

    @permpreset.command(name='view')
    @perms.exclusive()
    async def permpreset_view(self, ctx, preset):
        """Lists all the permissions assigned to a preset"""
        # Fetch permissions of preset from the config
        config = toml.load(constants.DATA_DIR + 'config.toml')
        perms = config['permissions'][preset]
        perms_output = [f'`{perm}`' for perm in perms]

        # Output list of permissions in a pretty embed
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO,
            title=f"{constants.EmbedIcon.INFORMATION} Permissions of {preset}")
        embed.add_field(
            name=f"{len(perms)} assigned perms",
            value=', '.join(perms_output))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Configuration(bot))