import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants


class ServerSettings:
    def __init__(self, id_, timezone):
        self.id = id_
        self.timezone = timezone


class ServerSettingsRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS server_settings (id INTEGER PRIMARY KEY, timezone TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM server_settings').fetchall()
        reminders = []
        for result in results:
            reminders.append(ServerSettings(result[0], result[1]))
        return reminders

    def get_by_guild(self, guild_id):
        result = self.db.cursor().execute('SELECT * FROM server_settings WHERE id=?', (guild_id,)).fetchone()
        return ServerSettings(result[0], result[1])

    def add(self, server_settings):
        cursor = self.db.cursor()
        values = (str(server_settings.id), server_settings.timezone)
        cursor.execute('INSERT INTO server_settings VALUES (?, ?)', values)
        self.db.commit()

    def update(self, server_settings):
        cursor = self.db.cursor()
        values = (server_settings.timezone, str(server_settings.id))
        cursor.execute('UPDATE server_settings SET timezone=? WHERE id=?', values)
        self.db.commit()

    def remove(self, server_settings):
        cursor = self.db.cursor()
        values = (server_settings.id,)
        cursor.execute('DELETE FROM server_settings WHERE id=?', values)
        self.db.commit()


class Administration(commands.Cog):
    """Modify server wide settings"""
    def __init__(self, bot):
        self.bot = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.server_settings = ServerSettingsRepository(self.database)

    @commands.Cog.listener()
    async def on_ready(self):
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()

        # Create tables if they don't exist
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS command_alias'
            '(server_id INTEGER, alias TEXT, command TEXT)')

        # Compare bot servers and database servers to check if the bot was
        # added to servers while the bot was offline
        cursor.execute('SELECT id FROM server_settings')
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

    @app_commands.command()
    async def timezone(self, interaction: discord.Interaction, region: str):
        server_settings = self.server_settings.get_by_guild(interaction.guild_id)
        server_settings.timezone = region
        self.server_settings.update(server_settings)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Timezone has been set to {region}. This will apply to time based commands."))

    async def _add_server_entry(self, guild):
        db = sqlite3.connect(constants.DATA_DIR + 'spacecat.db')
        cursor = db.cursor()
        value = (guild, None)
        cursor.execute(
            'INSERT OR IGNORE INTO server_settings VALUES (?,?)', value)
        db.commit()
        db.close()

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


async def setup(bot):
    await bot.add_cog(Administration(bot))
