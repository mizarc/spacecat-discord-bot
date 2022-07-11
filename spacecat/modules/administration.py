import sqlite3
from itertools import islice

import discord
from discord import app_commands
from discord.ext import commands

import toml

from spacecat.helpers import constants
from spacecat.helpers import perms
from spacecat.modules.configuration import Configuration


class Administration(commands.Cog):
    """Modify server wide settings"""
    def __init__(self, bot):
        self.bot = bot

    alias_group = app_commands.Group(name="alias", description="...")

    @commands.Cog.listener()
    async def on_ready(self):
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()

        # Create tables if they don't exist
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS server_settings'
            '(server_id INTEGER PRIMARY KEY, prefix TEXT, advanced_permission BOOLEAN)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS command_alias'
            '(server_id INTEGER, alias TEXT, command TEXT)')

        # Compare bot servers and database servers to check if the bot was
        # added to servers while the bot was offline
        cursor.execute('SELECT server_id FROM server_settings')
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

    @alias_group.command(name="add")
    @perms.check()
    async def alias_add(self, ctx, alias: str, *, command: str):
        """Allows a command to be executed with an alias"""
        # Limit alias to 15 chars
        if len(alias) > 15:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="Alias name is too long")
            await ctx.send(embed=embed)
            return

        # Alert user if alias is already in use
        check = await self._alias_check(ctx, alias)
        if check:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Alias `{alias}` is already assigned to `{check}`")
            await ctx.send(embed=embed)
            return

        # Add alias to database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, alias, command)
        cursor.execute(
            'INSERT INTO command_alias VALUES (?,?,?)', value)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Alias `{alias}` has been assigned to `{command}`")
        await ctx.send(embed=embed)

    @alias_group.command(name="remove")
    @perms.check()
    async def alias_remove(self, ctx, alias: str):
        """Removes an existing alias"""
        # Alert user if alias is not in use
        check = await self._alias_check(ctx, alias)
        if not check:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Alias `{alias}` hasn't been assigned to anything")
            await ctx.send(embed=embed)
            return

        # Remove alias from database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id, alias)
        cursor.execute(
            'DELETE FROM command_alias WHERE server_id=? AND alias=?', value)
        db.commit()
        db.close()

        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value,
            description=f"Alias `{alias}` has been removed`")
        await ctx.send(embed=embed)

    @alias_group.command(name="list")
    @perms.check()
    async def alias_list(self, ctx, page: int = 1):
        """Gets a list of available aliases"""
        # Get all aliases from database
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (ctx.guild.id,)
        cursor.execute(
            'SELECT alias, command FROM command_alias'
            'WHERE server_id=?', value)
        result = cursor.fetchall()
        db.close()

        # Tell user if no aliases exist
        if not result:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="No aliases currently exist")
            await ctx.send(embed=embed)
            return

        # Modify page variable to get every ten results
        page -= 1
        if page > 0:
            page = page * 10

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
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no aliases on that page")
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DATABASE} Command Aliases")
        embed.add_field(name="Aliases", value='\n'.join(aliases))
        await ctx.send(embed=embed)

    async def _add_server_entry(self, guild):
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (guild, None, None)
        cursor.execute(
            'INSERT OR IGNORE INTO server_settings VALUES (?,?,?)', value)
        db.commit()
        db.close()

    async def _alias_check(self, ctx, alias):
        # Query database for specified alias
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (ctx.guild.id, alias)
        cursor.execute(
            'SELECT command FROM command_alias '
            'WHERE server_id=? AND alias=?', query)
        result = cursor.fetchall()
        db.close()

        if result:
            return result[0][0]
        return False

    async def _wildcard_check(self, ctx, type_, id_):
        # Query database for wildcard permission
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, "*")
        cursor.execute(
            f'SELECT permission FROM {type_}_permission '
            f'WHERE {type_}_id=? AND permission=?', query)
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
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{cog.qualified_name}.*")
        cursor.execute(
            f'SELECT permission FROM {type_}_permission '
            f'WHERE {type_}_id=? AND permission=?', query)
        result = cursor.fetchall()
        db.close()

        if result:
            return cog, True
        return cog, False

    async def _command_check(self, ctx, type_, id_, perm, cog=None):
        command_parents = perm.split('.')

        if command_parents[-1] == '*':
            command = self.bot.slash.commands.get(perm[:-2].replace('.', ' '))
        else:
            command = self.bot.slash.commands.get(perm.replace('.', ' '))

        if command is None:
            return None, None

        # Query database for group permissions
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (id_, f"{command.cog.qualified_name}.{perm}")
        cursor.execute(
            f'SELECT permission FROM {type_}_permission '
            f'WHERE {type_}_id=? AND permission=?', query)
        result = cursor.fetchall()
        db.close()

        if result:
            return command, True
        return command, False

    async def _parent_query(self, ctx, child, parent):
        # Query database to check if group already has the parent
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        query = (parent, child)
        cursor.execute(
            'SELECT parent_id FROM group_parent '
            'WHERE parent_id=? AND child_id=?', query)
        result = cursor.fetchall()
        if result:
            db.close()
            return True

        db.close()
        return False

    async def _server_settings_database(self):
        """Ensures that keys in server_settings table exist post creation"""
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        cursor.execute('PRAGMA table_info(server_settings)')
        table_keys = cursor.fetchall()

        # Fetch all key names from table keys
        key_names = []
        for table_key in table_keys:
            key_names.append(table_key[1])

        # Add advanced_permission key if it doesn't exist
        if 'advanced_permission' not in key_names:
            cursor.execute(
                'ALTER TABLE server_settings '
                'ADD advanced_permission BOOLEAN')
        db.commit()
        db.close()


async def setup(bot):
    await bot.add_cog(Administration(bot))
