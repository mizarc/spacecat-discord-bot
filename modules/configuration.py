import configparser
import os
import sqlite3

import discord
from discord.ext import commands
import toml

from helpers import perms
from helpers.appearance import activity_type_class, status_class, embed_type, embed_icons

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Create tables if they don't exist
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS server_settings 
            (server_id integer, prefix text)''')
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS group_permissions
            (serverid integer, groupid integer, perm text)''')
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS user_permissions
            (serverid integer, userid integer, perm text)''')
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS group_parents
            (serverid integer, child_group, parent_group)''')

        # Add server to db if the bot was added to a new server while offline
        servers = self.bot.guilds
        for server in servers:
            query = (str(server.id),)
            cursor.execute(
                "SELECT server_id FROM server_settings WHERE server_id=?",
                query)
            check = cursor.fetchall()

            if not check:
                await self._add_server_entry(str(server.id))

        db.commit()
        db.close()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self._add_server_entry(str(guild.id))

    @commands.command()
    @perms.exclusive()
    async def status(self, ctx, statusname):
        config = toml.load('config.toml')
        activity = discord.Activity(type=activity_type_class(config['base']['activity_type']), name=config['base']['activity_name'])
        status = status_class(statusname)

        if status == None:
            embed = discord.Embed(colour=embed_type('warn'), description=f"That's not a valid status")
            await ctx.send(embed=embed)
            return

        print(status)
        await self.bot.change_presence(status=status, activity=activity)

        self.config['Base']['status'] = statusname
        toml.dump(config, 'config.toml')

    @commands.command()
    @perms.exclusive()
    async def activity(self, ctx, acttype, *, name):
        config = toml.load('config.toml')
        activitytype = activity_type_class(acttype)
        activity = discord.Activity(type=activitytype, name=name, url="https://www.twitch.tv/yeet")

        if activitytype == None:
            embed = discord.Embed(colour=embed_type('warn'), description=f"That's not a valid activity type")
            await ctx.send(embed=embed)
            return

        await self.bot.change_presence(activity=activity, status=config['base']['status'])

        config['Base']['activity_type'] = acttype
        config['Base']['activity_name'] = name
        toml.dump(config, 'config.toml')

    @commands.group()
    @perms.check()
    async def perm(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=embed_type('warn'), description="Please specify a valid subcommand: `group/user`")
            await ctx.send(embed=embed)
    
    @perm.group()
    @perms.check()
    async def group(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=embed_type('warn'), description="Please specify a valid subcommand: `add/remove/parent/unparent/info`")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Wildcard permission added to group `{group.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=embed_type('accept'), description=f"Group `{group.name}` already has the wildcard permission")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Permission group `{cog.qualified_name}` added to group `{group.name}`")
                skip = True
            # Already existing wildcard permission
            elif cog and exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"`{group.name}` already has the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'group', group.id, perm, cog)
            if command and not exists:
                value = (ctx.guild.id, group.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{perm}` added to group `{group.name}`")
                skip = True
            elif command and exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"{group.name} already has that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Add permission to database
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        cursor.execute("INSERT INTO group_permissions VALUES (?,?,?)", value)
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Wildcard permission removed from group `{group.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=embed_type('accept'), description=f"Group `{group.name}` doesn't have the wildcard permission")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Permission group `{cog.qualified_name}` removed from group `{group.name}`")
                skip = True
            # Check if group doesn't have the group permission
            elif cog and not exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"`{group.name}` doesn't have the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'group', group.id, perm, cog)
            if command and exists:
                query = (ctx.guild.id, group.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{perm}` removed from group `{group.name}`")
                skip = True
            elif command and not exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"{group.name} doesn't have that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        cursor.execute("DELETE FROM group_permissions WHERE serverid=? AND groupid=? AND perm=?", query)
        db.commit()
        db.close()

        await ctx.send(embed=embed)
        

    @group.command()
    @perms.check()
    async def parent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if check:
            embed = discord.Embed(colour=embed_type('warn'), description="Cannot add parent to group as selected parent is already a parent of group")
            await ctx.send(embed=embed)
            return

        # Query database to check if parent is a child of group
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (parent_group.id, child_group.id)
        cursor.execute("SELECT child_group FROM group_parents WHERE child_group=? AND parent_group=?", query)
        check = cursor.fetchall()
        if check:
            db.close()
            embed = discord.Embed(colour=embed_type('warn'), description="Cannot add parent to group as selected parent is a child of group")
            await ctx.send(embed=embed)  
            return

        # Remove permission from database and notify user
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("INSERT INTO group_parents VALUES (?,?,?)", values)
        embed = discord.Embed(colour=embed_type('accept'), description=f"`{child_group.name}` now inherits permissions from `{parent_group.name}`")
        await ctx.send(embed=embed)  
        db.commit()
        db.close()

    @group.command()
    @perms.check()
    async def unparent(self, ctx, child_group: discord.Role, parent_group: discord.Role):
        # Open server's config file
        check = await self._parent_query(ctx, child_group.id, parent_group.id)
        if not check:
            embed = discord.Embed(colour=embed_type('warn'), description="Cannot remove parent from group as selected parent isn't a parent of group")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, child_group.id, parent_group.id)
        cursor.execute("DELETE FROM group_parents WHERE serverid=? AND child_group=? AND parent_group=?", values)
        embed = discord.Embed(colour=embed_type('accept'), description=f"`{child_group.name}` is no longer inheriting permissions from `{parent_group.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @group.command(name='info')
    @perms.check()
    async def infogroup(self, ctx, group: discord.Role):
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Add user's name to embed
        embed = discord.Embed(colour=embed_type('info'))
        image = discord.File(embed_icons("database"), filename="image.png")
        embed.set_author(name=f"Group Perms of {group.name}", icon_url="attachment://image.png")

        # Query group's parents
        query = (ctx.guild.id, group.id)
        cursor.execute(
                'SELECT parent_group FROM group_parents WHERE serverid=? AND child_group=?', query)
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
                'SELECT perm FROM group_permissions WHERE serverid=? AND groupid=?', query)
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
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, role.id)
        cursor.execute(
                'SELECT perm FROM group_permissions WHERE serverid=? AND groupid=?', query)
        perms = cursor.fetchall()

        # Notify if specified user doesn't have any perms to clear
        if not perms:
            embed = discord.Embed(colour=embed_type('warn'), description=f"{role.name} doesn't have any permissions")
            await ctx.send(embed=embed) 
            return

        # Clear all permissions
        cursor.execute("DELETE FROM group_permissions WHERE serverid=? AND groupid=?", query)
        embed = discord.Embed(colour=embed_type('accept'), description=f"All permissions cleared from `{role.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @perm.group()
    @perms.check()
    async def user(self, ctx):
        """Configure server permissions"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(colour=embed_type('warn'), description="Please enter a valid subcommand: `add/remove/info`")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Wildcard permission added to user `{user.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=embed_type('accept'), description=f"User `{user.name}` already has the wildcard permission")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Permission group `{cog.qualified_name}` added to user `{user.name}`")
                skip = True

            # Already existing wildcard permission
            elif cog and exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"{user.name} already has the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'user', user.id, perm, cog)

            # Add if user doesn't have command permission
            if command and not exists:
                value = (ctx.guild.id, user.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{perm}` added to user `{user.name}`")
                skip = True

            # Notify if user already has permission
            elif command and exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"`{user.name}` already has that permission")
                await ctx.send(embed=embed) 
                return

        # Notify if permission doesn't exist
        if not skip:
            embed = discord.Embed(colour=embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Add permission to database
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        cursor.execute("INSERT INTO user_permissions VALUES (?,?,?)", value)
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Wildcard permission removed from user `{user.name}`")
                skip = True
            else:
                embed = discord.Embed(colour=embed_type('accept'), description=f"User `{user.name}` doesn't have the wildcard permission")
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
                embed = discord.Embed(colour=embed_type('accept'), description=f"Permission group `{cog.qualified_name}` removed from user `{user.name}`")
                skip = True
            # Check if user doesn't have the group permission
            elif cog and not exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"`{user.name}` doesn't have the `{cog.qualified_name}` permission group")
                await ctx.send(embed=embed) 
                return

        # Check if permission is a command and if command permission exists
        if not skip:
            perm = '.'.join(perm_values)
            command, exists = await self._command_check(ctx, 'user', user.id, perm, cog)
            if command and exists:
                query = (ctx.guild.id, user.id, f"{command.cog.qualified_name}.{perm}")
                embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{perm}` removed from user `{user.name}`")
                skip = True
            elif command and not exists:
                embed = discord.Embed(colour=embed_type('warn'), description=f"{user.name} doesn't have that permission")
                await ctx.send(embed=embed) 
                return

        if not skip:
            embed = discord.Embed(colour=embed_type('warn'), description=f"Permission does not exist. Please enter a valid permission")
            await ctx.send(embed=embed) 
            return

        # Remove permission from database
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        cursor.execute("DELETE FROM user_permissions WHERE serverid=? AND userid=? AND perm=?", query)
        db.commit()
        db.close()

        await ctx.send(embed=embed)
        

    @user.command(name='info')
    @perms.check()
    async def infouser(self, ctx, user: discord.Member):
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()

        # Add user's name to embed
        embed = discord.Embed(colour=embed_type('info'))
        image = discord.File(embed_icons("database"), filename="image.png")
        embed.set_author(name=f"User Perms of {user.name}", icon_url="attachment://image.png")

        # Output formatted groups list
        groups_output = []
        for role in user.roles:
            groups_output.append("`" + role.name + " (" + str(role.id) + ")`")
        embed.add_field(name="Groups", value=', '.join(groups_output), inline=False)

        # Query group's perms
        query = (ctx.guild.id, user.id)
        cursor.execute(
                'SELECT perm FROM user_permissions WHERE serverid=? AND userid=?', query)
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
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, user.id)
        cursor.execute(
                'SELECT perm FROM user_permissions WHERE serverid=? AND userid=?', query)
        perms = cursor.fetchall()

        # Notify if specified user doesn't have any perms to clear
        if not perms:
            embed = discord.Embed(colour=embed_type('warn'), description=f"`{user.name}` doesn't have any permissions")
            await ctx.send(embed=embed) 
            return

        # Clear all permissions
        cursor.execute("DELETE FROM user_permissions WHERE serverid=? AND userid=?", query)
        embed = discord.Embed(colour=embed_type('accept'), description=f"All permissions cleared from `{user.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @commands.group()
    @perms.exclusive()
    async def permpreset(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def create(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def removed(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def append(self, ctx):
        print('nah')

    @permpreset.command()
    @perms.exclusive()
    async def truncate(self, ctx):
        print('nah')

    @permpreset.command()
    async def prefix(self, ctx, prefix):
        """Sets the server specific prefix for commands"""
        # Query database for wildcard permission
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, "*")
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
        result = cursor.fetchall()
        db.close()

    async def _wildcard_check(self, ctx, type_, id_):
        # Query database for wildcard permission
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, "*")
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
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
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{cog.qualified_name}.*")
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
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
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{command.cog.qualified_name}.{perm}")
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
        result = cursor.fetchall()
        db.close()

        if result:
            return command, True
        return command, False

    async def _parent_query(self, ctx, child, parent):
        # Query database to check if group already has the parent
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (child, parent)
        cursor.execute("SELECT parent_group FROM group_parents WHERE child_group=? AND parent_group=?", query)
        result = cursor.fetchall()
        if result:
            db.close()
            return True

        db.close()
        return False

    async def _add_server_entry(self, guild):
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        value = (guild, "NULL")
        cursor.execute("INSERT INTO server_settings VALUES (?,?)", value)
        db.commit()
        db.close()


def setup(bot):
    bot.add_cog(Configuration(bot))
