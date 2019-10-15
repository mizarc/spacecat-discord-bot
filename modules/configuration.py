import configparser
import sqlite3

import discord
from discord.ext import commands
import toml

from helpers import perms
from helpers.appearance import activity_type_class, status_class, embed_type, embed_icons

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    async def addgroup(self, ctx, group: discord.Role, command):
        # Query database to check if the group has the permission already
        perm = await self._perm_query(ctx, 'group', group.id, command)
        if perm is None:
            return
        elif perm is True:
            embed = discord.Embed(colour=embed_type('warn'), description=f"`{group.name}` already has that permission")
            await ctx.send(embed=embed)
            return
        
        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, group.id, command)
        cursor.execute("INSERT INTO group_permissions VALUES (?,?,?)", values)
        embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{command}` added to group `{group.name}`")
        await ctx.send(embed=embed)
        db.commit()
        db.close()

    @group.command(name='remove')
    @perms.check()
    async def removegroup(self, ctx, group: discord.Role, command):
        # Query database to check if the group has the permission already
        perm = await self._perm_query(ctx, 'group', group.id, command)
        if perm is None:
            return
        elif perm is False:
            embed = discord.Embed(colour=embed_type('warn'), description=f"`{group.name}` doesn't have that permission")
            await ctx.send(embed=embed)
            return
        
        # Remove permission from database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, group.id, command)
        cursor.execute("DELETE FROM group_permissions WHERE serverid=? AND groupid=? AND perm=?", query)
        embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{command}` removed from group `{group.name}`")
        await ctx.send(embed=embed)
        db.commit()
        db.close()

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
    async def adduser(self, ctx, user: discord.User, command):
        # Query database to check if the user has the permission already
        perm = await self._perm_query(ctx, 'user', user.id, command)
        if perm is None:
            return
        elif perm is True:
            embed = discord.Embed(colour=embed_type('warn'), description=f"{user.name} already has that permission")
            await ctx.send(embed=embed) 
            return 

        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        values = (ctx.guild.id, user.id, command)
        cursor.execute("INSERT INTO user_permissions VALUES (?,?,?)", values)
        embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{command}` added to group `{user.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()

    @user.command(name='remove')
    @perms.check()
    async def removeuser(self, ctx, user: discord.User, command):
        # Query database to check if the user has the permission already
        perm = await self._perm_query(ctx, 'user', user.id, command)
        if perm is None:
            return
        elif perm is False:
            embed = discord.Embed(colour=embed_type('warn'), description=f"{user.name} doesn't have that permission")
            await ctx.send(embed=embed) 
            return 

        # Append permission to database and notify user
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, user.id, command)
        cursor.execute("DELETE FROM user_permissions WHERE serverid=? AND userid=? AND perm=?", query)
        embed = discord.Embed(colour=embed_type('accept'), description=f"Command `{command}` removed from user `{user.name}`")
        await ctx.send(embed=embed) 
        db.commit()
        db.close()
        
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

    async def _perm_query(self, ctx, type_, id_, command):
        # Loop through command list and check if command exists
        command_exists = False
        for bot_command in ctx.bot.commands:
            if command == bot_command.name:
                command_exists = True
                break

        # Send message if command does not exist
        if not command_exists:
            await ctx.send("That command does not exist")
            return None

        # Query database for group permissions
        db = sqlite3.connect('spacecat.db')
        cursor = db.cursor()
        query = (id_, command)
        cursor.execute(f"SELECT perm FROM {type_}_permissions WHERE {type_}id=? AND perm=?", query)
        result = cursor.fetchall()
        db.close()
        if result:
            return True
        return False

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



def setup(bot):
    bot.add_cog(Configuration(bot))
