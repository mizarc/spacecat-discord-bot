from itertools import islice
import configparser
import os
import sqlite3

import discord
from discord.ext import commands
import toml

from helpers import perms
from helpers import settings


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()

        # Create tables if they don't exist
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS server_settings'
            '(server_id INTEGER PRIMARY KEY, prefix TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS command_alias'
            '(server_id INTEGER, alias TEXT, command TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS group_permission'
            '(server_id INTEGER, group_id INTEGER, permission TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS user_permission'
            '(server_id INTEGER, user_id INTEGER, permission TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS group_parent'
            '(server_id INTEGER, parent_id INTEGER, child_id INTEGER)')

        # Compare bot servers and database servers to check if the bot was 
        # added to servers while the bot was offline
        cursor.execute("SELECT server_id FROM server_settings")
        servers = self.bot.guilds
        server_ids = {server.id for server in servers}
        db_servers = cursor.fetchall()
        db_server_ids = {server for server, in db_servers}
        missing_servers = list(server_ids - db_server_ids)

        # Add missing servers to database
        for server in missing_servers:
            await self._add_server_entry(server)

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self._add_server_entry(guild.id)

    @commands.group()
    @perms.check()
    async def alias(self, ctx):
        """Configure command aliases"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Please specify a valid subcommand: `add/remove`")
            await ctx.send(embed=embed)

    @alias.command(name='add')
    @perms.check()
    async def addalias(self, ctx, alias, *, command):
        """Allows a command to be executed with an alias"""        
        # Limit alias to 15 chars
        if len(alias) > 15:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Alias name is too long")
            await ctx.send(embed=embed)
            return

        # Alert user if alias is already in use
        check = await self._alias_check(ctx, alias)
        if check:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Alias `{alias}` is already assigned to `{check}`")
            await ctx.send(embed=embed)
            return

        # Add alias to database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, alias, command)
        cursor.execute("INSERT INTO command_alias VALUES (?,?,?)", value)
        db.commit()
        db.close()

        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Alias `{alias}` has been assigned to `{command}`")
        await ctx.send(embed=embed)

    @alias.command(name='remove')
    @perms.check()
    async def removealias(self, ctx, alias):
        """Removes an existing alias"""
        # Alert user if alias is not in use
        check = await self._alias_check(ctx, alias)
        if not check:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Alias `{alias}` hasn't been assigned to anything")
            await ctx.send(embed=embed)
            return

        # Remove alias from database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, alias)
        cursor.execute("DELETE FROM command_alias WHERE server_id=? AND alias=?", value)
        db.commit()
        db.close()

        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Alias `{alias}` has been removed`")
        await ctx.send(embed=embed)

    @alias.command(name='list')
    @perms.check()
    async def listalias(self, ctx, page=1):
        # Get all aliases from database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id,)
        cursor.execute("SELECT alias, command FROM command_alias WHERE server_id=?", value)
        result = cursor.fetchall()
        db.close()

        # Tell user if no aliases exist
        if not result:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"No aliases currently exist")
            await ctx.send(embed=embed)
            return

        # Modify page variable to get every ten results
        page -= 1
        if page > 0: page = page * 10

        # Get a list of 10 aliases
        aliases = []
        for index, alias in enumerate(islice(result, page, page + 10)):
            # Cut off the linked command to 70 chars
            if len(alias[1]) > 70:
                command = f"{alias[1][:67]}..." 
            else:
                command = alias[1]

            aliases.append(f"{page + index + 1}. `{alias[0]}`: {command}")

        if not aliases:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"There are no aliases on that page")
            await ctx.send(embed=embed)
            return
            
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("database"), filename="image.png")
        embed.set_author(name="Command Aliases", icon_url="attachment://image.png")
        embed.add_field(name="Aliases", value='\n'.join(aliases))
        await ctx.send(embed=embed, file=image)

    @commands.group()
    @perms.check()
    async def perm(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Please specify a valid subcommand: `group/user`")
            await ctx.send(embed=embed)
    
    @perm.group()
    @perms.check()
    async def group(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Please specify a valid subcommand: `add/remove/parent/unparent/info`")
            await ctx.send(embed=embed)

    @group.command(name='add')
    @perms.check()
    async def addgroup(self, ctx, group: discord.Role, perm):
        perm_values = perm.split('.')
        skip = False
        cog = None

        # Check for wildcard permission
        if perm == '*':
            exists = await self._wildcard_check(ctx, 'group', group.id)
            if exists is False:
                value = (ctx.guild.id, group.id, "*")   
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Wildcard permission added to group `{group.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Group `{group.name}` already has the wildcard permission")
                await ctx.send(embed=embed) 
                return

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog, exists = await self._module_check(ctx, 'group', group.id, perm_values[0])
            # Add a cog wildcard permission to give groups all cog permissions
            if cog and perm_values[1] != '*':
                perm_values.pop(0)
            # Check if non-wildcard permission has been chosen
            elif cog and not exists and perm_values[1] == '*':
                value = (ctx.guild.id, group.id, f"{cog.qualified_name}.*")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Permission group `{cog.qualified_name}` added to group `{group.name}`")
                skip = True
            # Already existing wildcard permission
            elif cog and exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"`{group.name}` already has the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'group', group.id, perm, cog)
            if command and not exists:
                value = (ctx.guild.id, group.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Command `{perm}` added to group `{group.name}`")
                skip = True
            elif command and exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"{group.name} already has that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Add permission to database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute("INSERT INTO group_permission VALUES (?,?,?)", value)
        db.commit()
        db.close()
        
        await ctx.send(embed=embed) 

    @group.command(name='remove')
    @perms.check()
    async def removegroup(self, ctx, group: discord.Role, perm):
        perm_values = perm.split('.')
        skip = False
        cog = None

        # Check for wildcard permission
        if perm == '*':
            exists = await self._wildcard_check(ctx, 'group', group.id)
            if exists:
                query = (ctx.guild.id, group.id, "*")   
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Wildcard permission removed from group `{group.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Group `{group.name}` doesn't have the wildcard permission")
                await ctx.send(embed=embed) 
                return

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog, exists = await self._module_check(ctx, 'group', group.id, perm_values[0])
            # Check if non wildcard permission
            if cog and perm_values[1] != '*':
                perm_values.pop(0)
            # Check if permission group wildcard
            elif cog and exists and perm_values[1] == '*':
                query = (ctx.guild.id, group.id, f"{cog.qualified_name}.*")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Permission group `{cog.qualified_name}` removed from group `{group.name}`")
                skip = True
            # Check if group doesn't have the group permission
            elif cog and not exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"`{group.name}` doesn't have the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'group', group.id, perm, cog)
            if command and exists:
                query = (ctx.guild.id, group.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Command `{perm}` removed from group `{group.name}`")
                skip = True
            elif command and not exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"{group.name} doesn't have that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute("DELETE FROM group_permission WHERE server_id=? AND group_id=? AND permission=?", query)
        db.commit()
        db.close()

        await ctx.send(embed=embed)
        

    @group.command()
    @perms.check()
    async def parent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if check:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Cannot add parent to group as selected parent is already a parent of group")
            await ctx.send(embed=embed)
            return

        # Query database to check if parent is a child of group
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (parent_group.id, child_group.id)
        cursor.execute("SELECT child_id FROM group_parent WHERE parent_id=? AND child_id=?", query)
        check = cursor.fetchall()
        if check:
            db.close()
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Cannot add parent to group as selected parent is a child of group")
            await ctx.send(embed=embed)  
            return

        # Remove permission from database and notify user
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("INSERT INTO group_parent VALUES (?,?,?)", values)
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"`{child_group.name}` now inherits permissions from `{parent_group.name}`")
        await ctx.send(embed=embed)  
        db.commit()
        db.close()

    @group.command()
    @perms.check()
    async def unparent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if not check:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Cannot remove parent from group as selected parent isn't a parent of group")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database and notify user
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("DELETE FROM group_parent WHERE server_id=? AND parent_id=? AND child_id=?", values)
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"`{child_group.name}` is no longer inheriting permissions from `{parent_group.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @group.command(name='info')
    @perms.check()
    async def infogroup(self, ctx, group: discord.Role):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()

        # Add user's name to embed
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("database"), filename="image.png")
        embed.set_author(name=f"Group Perms of {group.name}", icon_url="attachment://image.png")

        # Query group's parents
        query = (ctx.guild.id, group.id)
        cursor.execute(
                'SELECT parent_id FROM group_parent WHERE server_id=? AND child_id=?', query)
        parents = cursor.fetchall()

        # Output formatted parents list
        if parents:
            parents_output = []
            for parent in parents:
                group = discord.utils.get(ctx.guild.roles, id=parent[0])
                parents_output.append("`" + group.name + " (" + str(parent[0]) + ")`")
            embed.add_field(name="Parents", value=', '.join(parents_output), inline=False)

        # Query group's perms
        cursor.execute(
                'SELECT permission FROM group_permission WHERE server_id=? AND group_id=?', query)
        perms = cursor.fetchall()

        # Output formatted perms list
        if perms:
            perms_output = []
            for perm in perms:
                perms_output.append("`" + perm[0] + "`")
            embed.add_field(name="Permissions", value=', '.join(perms_output), inline=False)

        await ctx.send(file=image, embed=embed)

    @group.command(name='purge')
    @perms.check()
    async def purgegroup(self, ctx, role: discord.Role):
        # Query database to get all user permissions
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, role.id)
        cursor.execute(
                'SELECT perm FROM group_permission WHERE server_id=? AND group_id=?', query)
        perms = cursor.fetchall()

        # Notify if specified user doesn't have any perms to clear
        if not perms:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"{role.name} doesn't have any permissions")
            await ctx.send(embed=embed) 
            return

        # Clear all permissions
        cursor.execute("DELETE FROM group_permission WHERE server_id=? AND group_id=?", query)
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"All permissions cleared from `{role.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @perm.group()
    @perms.check()
    async def user(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=settings.embed_type('warn'), description="Please enter a valid subcommand: `add/remove/info`")
            await ctx.send(embed=embed) 

    @user.command(name='add')
    @perms.check()
    async def adduser(self, ctx, user: discord.User, perm):
        perm_values = perm.split('.')
        skip = False
        cog = None

        # Check for wildcard permission
        if perm == '*':
            exists = await self._wildcard_check(ctx, 'user', user.id)
            if exists is False:
                value = (ctx.guild.id, user.id, "*")   
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Wildcard permission added to user `{user.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"User `{user.name}` already has the wildcard permission")
                await ctx.send(embed=embed) 
                return

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog, exists = await self._module_check(ctx, 'user', user.id, perm_values[0])

            # Add a cog wildcard permission to give users all cog permissions
            if cog and perm_values[1] != '*':
                perm_values.pop(0)

            # Check if non-wildcard permission has been chosen
            elif cog and not exists and perm_values[1] == '*':
                value = (ctx.guild.id, user.id, f"{cog.qualified_name}.*")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Permission group `{cog.qualified_name}` added to user `{user.name}`")
                skip = True

            # Already existing wildcard permission
            elif cog and exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"{user.name} already has the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'user', user.id, perm, cog)

            # Add if user doesn't have command permission
            if command and not exists:
                value = (ctx.guild.id, user.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Command `{perm}` added to user `{user.name}`")
                skip = True

            # Notify if user already has permission
            elif command and exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"`{user.name}` already has that permission")
                await ctx.send(embed=embed) 
                return

        # Notify if permission doesn't exist
        if not skip:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Add permission to database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute("INSERT INTO user_permission VALUES (?,?,?)", value)
        db.commit()
        db.close()
        
        await ctx.send(embed=embed) 

    @user.command(name='remove')
    @perms.check()
    async def removeuser(self, ctx, user: discord.User, perm):
        perm_values = perm.split('.')
        skip = False
        cog = None

        # Check for wildcard permission
        if perm == '*':
            exists = await self._wildcard_check(ctx, 'user', user.id)
            if exists:
                query = (ctx.guild.id, user.id, "*")   
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Wildcard permission removed from user `{user.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"User `{user.name}` doesn't have the wildcard permission")
                await ctx.send(embed=embed) 
                return

        # Check if permission starts with a cog
        if not skip and len(perm_values) > 1:
            cog, exists = await self._module_check(ctx, 'user', user.id, perm_values[0])
            # Check if non wildcard permission
            if cog and perm_values[1] != '*':
                perm_values.pop(0)
            # Check if permission group wildcard
            elif cog and exists and perm_values[1] == '*':
                query = (ctx.guild.id, user.id, f"{cog.qualified_name}.*")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Permission group `{cog.qualified_name}` removed from user `{user.name}`")
                skip = True
            # Check if user doesn't have the group permission
            elif cog and not exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"`{user.name}` doesn't have the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'user', user.id, perm, cog)
            if command and exists:
                query = (ctx.guild.id, user.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=settings.embed_type('accept'), description=f"Command `{perm}` removed from user `{user.name}`")
                skip = True
            elif command and not exists:
                embed = discord.Embed(colour=settings.embed_type('warn'), description=f"{user.name} doesn't have that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute("DELETE FROM user_permission WHERE server_id=? AND user_id=? AND permission=?", query)
        db.commit()
        db.close()

        await ctx.send(embed=embed)
        

    @user.command(name='info')
    @perms.check()
    async def infouser(self, ctx, user: discord.Member):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()

        # Add user's name to embed
        embed = discord.Embed(colour=settings.embed_type('info'))
        image = discord.File(settings.embed_icons("database"), filename="image.png")
        embed.set_author(name=f"User Perms of {user.name}", icon_url="attachment://image.png")

        # Output formatted groups list
        groups_output = []
        for role in user.roles:
            groups_output.append("`" + role.name + " (" + str(role.id) + ")`")
        embed.add_field(name="Groups", value=', '.join(groups_output), inline=False)

        # Query group's perms
        query = (ctx.guild.id, user.id)
        cursor.execute(
                'SELECT permission FROM user_permission WHERE server_id=? AND user_id=?', query)
        perms = cursor.fetchall()

        # Output formatted perms list
        if perms:
            perms_output = []
            for perm in perms:
                perms_output.append("`" + perm[0] + "`")
            embed.add_field(name="Permissions", value=', '.join(perms_output), inline=False)

        await ctx.send(file=image, embed=embed)

    @user.command(name='purge')
    @perms.check()
    async def purgeuser(self, ctx, user: discord.User):
        # Query database to get all user permissions
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, user.id)
        cursor.execute(
                'SELECT permission FROM user_permission WHERE server_id=? AND user_id=?', query)
        perms = cursor.fetchall()

        # Notify if specified user doesn't have any perms to clear
        if not perms:
            embed = discord.Embed(colour=settings.embed_type('warn'), description=f"`{user.name}` doesn't have any permissions")
            await ctx.send(embed=embed) 
            return

        # Clear all permissions
        cursor.execute("DELETE FROM user_permission WHERE server_id=? AND user_id=?", query)
        embed = discord.Embed(colour=settings.embed_type('accept'), description=f"All permissions cleared from `{user.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    async def _add_server_entry(self, guild):
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        value = (guild, None)
        cursor.execute(
            "INSERT OR IGNORE INTO server_settings VALUES (?,?)",
            value)
        db.commit()
        db.close()

    async def _alias_check(self, ctx, alias):
        # Query database for specified alias
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, alias)
        cursor.execute(f"SELECT command FROM command_alias WHERE server_id=? AND alias=?", query)
        result = cursor.fetchall()
        db.close()

        if result:
            return result[0][0]
        return False

    async def _wildcard_check(self, ctx, type_, id_):
        # Query database for wildcard permission
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, "*")
        cursor.execute(f"SELECT permission FROM {type_}_permission WHERE {type_}_id=? AND permission=?", query)
        result = cursor.fetchall()
        db.close()

        if result:
            return True
        return False

    async def _module_check(self, ctx, type_, id_, module):
        # Check if command exists by trying to get command object
        cog = self.bot.get_cog(module)
        if not cog:
            return None, None

        # Query database for group permissions
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{cog.qualified_name}.*")
        cursor.execute(f"SELECT permission FROM {type_}_permission WHERE {type_}_id=? AND permission=?", query)
        result = cursor.fetchall()
        db.close()

        if result:
            return cog, True
        return cog, False

    async def _command_check(self, ctx, type_, id_, perm, cog=None):
        command_parents = perm.split('.')

        if command_parents[-1] == '*':
            command = self.bot.get_command(perm[:-2].replace('.', ' '))
        else:
            command = self.bot.get_command(perm.replace('.', ' '))

        if command is None:
                return None, None

        # Query database for group permissions
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{command.cog.qualified_name}.{perm}")
        cursor.execute(f"SELECT perm FROM {type_}_permission WHERE {type_}_id=? AND permission=?", query)
        result = cursor.fetchall()
        db.close()

        if result:
            return command, True
        return command, False

    async def _parent_query(self, ctx, child, parent):
        # Query database to check if group already has the parent
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (child, parent)
        cursor.execute("SELECT parent_id FROM group_parent WHERE parent_id=? AND child_id=?", query)
        result = cursor.fetchall()
        if result:
            db.close()
            return True

        db.close()
        return False

    @commands.command()
    @perms.check()
    async def prefix(self, ctx, prefix):
        """Sets the server specific prefix for commands"""
        # Deny if specified prefix is too long
        if len(prefix) > 30:
            embed = discord.Embed(
                colour=settings.embed_type('warn'),
                description=f"Specified prefix is too long")
            await ctx.send(embed=embed)
            return

        # Set the prefix for the current server in database
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (prefix, ctx.guild.id)
        cursor.execute(
            "UPDATE server_settings SET prefix=? WHERE server_id=?", query)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"Command prefix has been set to: `{prefix}`")
        await ctx.send(embed=embed)
        return

    @commands.command()
    @perms.check()
    async def resetprefix(self, ctx):
        """Sets the prefix back to the config specified prefix"""
        # Set the prefix for the current server
        db = sqlite3.connect(settings.data + 'spacecat.db')
        cursor = db.cursor()
        query = (None, ctx.guild.id)
        cursor.execute(
            "UPDATE server_settings SET prefix=? WHERE server_id=?", query)
        db.commit()
        db.close()

        # Get original prefix
        config = toml.load(settings.data + 'config.toml')
        prefix = config['base']['prefix']

        embed = discord.Embed(
            colour=settings.embed_type('accept'),
            description=f"Command prefix has been reset back to: `{prefix}`")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Administration(bot))