import asyncio
import configparser
import logging
import os
import shutil
import sqlite3
import sys
import time

import discord
from discord.ext import commands
import toml

from spacecat.helpers import constants
import spacecat.helpers.module_handler as module_handler
import spacecat.helpers.perms as perms


class SpaceCat(commands.Cog):
    """The bare minimum for bot functionality"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')

        # Create cache folder if it doesn't exist
        try:
            os.mkdir(constants.CACHE_DIR)
        except FileExistsError:
            pass
        
        # Run initial configurator as long as values are missing
        if 'adminuser' not in config['base']:
            await self._set_admin()
        if 'prefix' not in config['base']:
            await self._set_prefix()
        servers = self.bot.guilds
        if not servers:
            await self._send_invite()

        # Output launch completion message
        print(self.bot.user.name + " has successfully launched")
        print(f"Bot ID: {self.bot.user.id}")
        if module_handler.get_enabled():
            print(
                "Enabled Module(s): "
                f"{', '.join(module_handler.get_enabled())}")
        if module_handler.get_disabled():
            print(
                "Disabled Module(s): "
                f"{', '.join(module_handler.get_disabled())}")
        print("--------------------")

        # Change status if specified in config
        try:
            status_name = config['base']['status']
            status = discord.Status[status_name]
            await self.bot.change_presence(status=status)
        except KeyError:
            pass

        # Change activity if specified in config
        try:
            activity_name = config['base']['activity_type']
            activity_type = discord.ActivityType[activity_name]

            activity = discord.Activity(
                type=activity_type,
                name=config['base']['activity_name'],
                url="https://www.twitch.tv/monstercat")
            await self.bot.change_presence(activity=activity)
        except (KeyError, TypeError):
            pass
            
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Run automatic permission assignment based on presets
        # Not implemented yet, just here as a placeholder
        if os.path.exists('config.ini'):
            perms.new(guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check for both nickname and non nickname mentions
        mentions = [f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>']
        for mention in mentions:
            if mention == message.content:
                prefix = await self.bot.get_prefix(message)

                # Info on how to use the bot
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['info'],
                    title=f"{constants.EmbedIcon.HELP} Hello There!",
                    description="I'm here to provide a useful set a features")
                embed.add_field(
                    name=f"Current Prefix",
                    value=f"`{prefix[2]}`", inline=False)
                embed.add_field(
                    name=f"Need Help?",
                    value=f"Type `{prefix[2]}help` to get a list of commands",
                    inline=False) 
                embed.add_field(
                    name=f"Want more features added?",
                    value=f"[Request them here]"
                    "(https://gitlab.com/Mizarc/spacecat-discord-bot/issues)",
                    inline=False) 
                await message.channel.send(embed=embed)
                return

    # Commands
    @commands.command()
    @perms.check()
    async def ping(self, ctx):
        """
        A simple ping to check if the bot is responding
        The ping will show in milliseconds the connection between the
        bot host and the discord servers.
        """
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'], 
            description=f"{self.bot.user.name} is operational at \
            {int(self.bot.latency * 1000)}ms")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def version(self, ctx):
        """
        Check the current bot version
        This links to the gitlab source page, showing the most updated
        version of the bot.
        """
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['info'], 
            description="**Bot is currently using version:**\n"
            "[SpaceCat Discord Bot `v0.3.0`]"
            "(https://gitlab.com/Mizarc/spacecat-discord-bot)")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def globalprefix(self, ctx, prefix):
        """
        Changes the global command prefix
        Servers with a custom prefix override as specified with the
        'prefix' command are not affected by this change.
        """
        # Changes the prefix entry in the config
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['prefix'] = prefix
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
                colour=constants.EMBED_TYPE['accept'],
                description=f"Global command prefix changed to: `{prefix}`.\n\
                Servers with prefix override will not be affected.")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def modules(self, ctx):
        """
        Lists all currently available modules
        Will show which modules are currently enabled or disabled.
        """
        enabled = module_handler.get_enabled()
        disabled = module_handler.get_disabled()

        # Create embed
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['info'],
            title=f"{constants.EmbedIcon.INFORMATION} {self.bot.user.name} Modules")

        # Categorise modules into enabled and disabled fields
        if enabled:
            embed.add_field(
                name="Enabled",
                value=', '.join(enabled),
                inline=False)
        if disabled:
            embed.add_field(
                name="Disabled",
                value=', '.join(disabled),
                inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def reload(self, ctx, module=None):
        """
        Reloads all or specified module
        Used for applying changes that were done to the source code.
        """
        module_list = module_handler.get_enabled()
        modules_to_load = []
        failed_modules = []

        # Set modules to load depending on if a specific module is selected
        if module:
            if module not in module_list:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"{module} is not a valid or enabled module")
                await ctx.send(embed=embed)
                return
            modules_to_load = [module]
        else:
            modules_to_load = module_list

        # Reload modules in list
        for module in modules_to_load:
            try:
                module = 'modules.' + module
                self.bot.reload_extension(module)
            except:
                failed_modules.append(module[8:])

        # Ouput error messages depending on if only one or multiple modules
        if failed_modules and len(modules_to_load) == 1:
            embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"Failed to reload module \
                    `{module[8:]}`")
            await ctx.send(embed=embed)
            return
        elif failed_modules:
            embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"Failed to reload module(s): \
                    `{', '.join(failed_modules)}`. \
                    Other modules have successfully reloaded")
            await ctx.send(embed=embed)
            return
        
        # Notify user of successful module reloading
        if len(modules_to_load) == 1:
            embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Reloaded module `{module[8:]}` successfully")
        else:
            embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"All modules reloaded successfully")
        
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def enable(self, ctx, module):
        """
        Enables a module
        New modules added to the bot in the modules folder can started
        using this command rather than having to restart the bot.
        """
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is already enabled
        disabled_modules = module_handler.get_disabled()
        if disabled_modules is None or module not in disabled_modules:
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Module `{module}` is already enabled")
            await ctx.send(embed=embed)
            return

        # Enable module and write to config
        self.bot.load_extension(f'{constants.MAIN_DIR}.modules.{module}')
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['disabled_modules'].remove(module)
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Module `{module}` enabled")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def disable(self, ctx, module):
        """
        Disables a module
        Modules can be safely disabled, which will stop all commands and
        listeners from functioning.
        """
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=constants.EMBED_TYPE['warn'],
                description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is already disabled
        disabled_modules = module_handler.get_disabled()   
        try:
            if module in disabled_modules:
                embed = discord.Embed(
                    colour=constants.EMBED_TYPE['warn'],
                    description=f"Module `{module}` is already disabled")
                await ctx.send(embed=embed)
                return

        # Add to list if list exists or create list if it doesn't
            config = toml.load(constants.DATA_DIR + 'config.toml')
            config['base']['disabled_modules'].append(module)
        except TypeError:
            config = toml.load(constants.DATA_DIR + 'config.toml')
            config['base']['disabled_modules'] = [module]   

        # Disable module and write to config
        self.bot.unload_extension(f'{constants.MAIN_DIR}.modules.{module}')
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=constants.EMBED_TYPE['accept'],
            description=f"Module `{module}` disabled")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def exit(self, ctx):
        """
        Shuts down the bot
        Ensures that proper shutdown prodedures are done so that issues
        do not arise during next start.
        """
        # Clear the cache folder if it exists
        try:
            shutil.rmtree(constants.CACHE_DIR)
        except:
            pass
        
        await self.bot.logout()

    async def _set_admin(self):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        confirm = None

        while confirm != "yes":
            # Set a bot administrator
            print(
                "[Bot Administrator]\n"
                f"Alright, {self.bot.user.name} is now operational.\n"
                "Now I'll need to get your discord user ID.\n"
                "This will give you admin access to the bot in Discord.\n"
                "You can set more users later.\n\n"

                "Here's what you need to do:\n"
                "1. Open Discord.\n"
                "2. Open your user constants.\n"
                "3. Open the settings tab.\n"
                "4. Enable 'Developer Mode' under Advanced.\n"
                "5. Exit user settings\n"
                "6. Right click on your user and click 'Copy ID'\n")

            # Check to see if the user ID is valid
            try:
                idinput = int(input("Paste your ID right here: "))
                print('--------------------\n')
                user = self.bot.get_user(idinput)
                await user.send("Hello there!")
            except (ValueError, AttributeError):
                print(
                    "It looks like that is not a valid ID.\n"
                    "Lets try this again.\n")
                input("Press Enter to continue...")
                print('--------------------\n')
                time.sleep(1)
                continue
            time.sleep(1)
            
            # Ask for confirmation
            while True:
                print(
                    f"Verify that {user} is you.\n"
                    "If your user settings allow it, you should've also "
                    "recieved a private message from me.\n")
                confirm = input(
                    "Type 'yes' to confirm, or 'no' to set a new ID: ")
                print('--------------------\n')

                if confirm == "yes":
                    config['base']['adminuser'] = [idinput]
                    break
                elif confirm == "no":
                    break
                else:
                    continue

        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        time.sleep(1)

    async def _set_prefix(self):
        # Ask to set a command prefix
        print(
            "[Prefix]\n"
            "Your bot will need a prefix in order to run commands.\n"
            "You can set it to be whatever you want,\n"
            "though I recommend you keep it short\n")

        prefix_input = input("Enter your bot prefix here: ")
        print('--------------------\n')

        # Save prefix to config
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['prefix'] = prefix_input
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        time.sleep(1)

    async def _send_invite(self):
        # Provide a link to join the server
        print(
            "[Invite]\n"
            "I need to join your Discord server if i'm not in it already.\n"
            "Click the link below or copy it into your web browser.\n"
            "You can give this link to other users to help "
            "spread your bot around.\n\n"

            "https://discordapp.com/oauth2/authorize?"
            f"client_id={self.bot.user.id}&scope=bot&permissions=8\n"
            "--------------------\n")

        # Set default values and save config
        config = toml.load(constants.DATA_DIR + 'config.toml')
        config['base']['status'] = 'online'
        config['base']['activity_type'] = None
        config['base']['activity_name'] = None
        with open(constants.DATA_DIR + "config.toml", "w") as config_file:
            toml.dump(config, config_file)
        await asyncio.sleep(1)


def introduction(config):
    # Output introduction
    print(
        "Hey there,\n"
        "The bot will need some configuring to be able to run.\n"
        "Don't worry, I'll walk you through everything.\n")

    input("Press Enter to continue...")
    print('--------------------\n')
    time.sleep(1)

    # Ask users to provide an API key for the bot
    print(
        "[API Key]\n"
        "I'll need to get an API Key from your bot.\n"
        "https://discordapp.com/developers/applications/\n\n"
        "Open that link and follow these instructions:\n"
        "1. Create a new application and set a name.\n"
        "2. Open the 'Bot' tab on the left.\n"
        "3. Select 'Create a Bot' and confirm.\n"
        "4. Click on 'Copy' under Token.\n"
        "(Don't ever reveal this token to anyone you don't trust)\n")
    
    keyinput = input("Paste your token right here: ")
    print('--------------------\n')

    # Add API key to config file
    config = toml.load(constants.DATA_DIR + 'config.toml')
    config['base']['apikey'] = keyinput
    with open(constants.DATA_DIR + "config.toml", "w") as config_file:
        toml.dump(config, config_file)
    return True

    
def load_modules(bot):
    """Loads all modules from the modules folder for the bot"""
    # Enable enabled modules from list
    bot.add_cog(SpaceCat(bot))
    modules = module_handler.get_enabled()
    for module in modules:
        module = f'{constants.MAIN_DIR}.modules.' + module
        try:
            bot.load_extension(module)
        except Exception as exception:
            print(
                f"Failed to load extension {module}\n"
                f"{type(exception).__name__}: {exception}\n")
    return bot


def get_prefix(bot, message):
    # Access database if it exists and fetch server's custom prefix if set
    try:
        db = sqlite3.connect(f'file:{constants.DATA_DIR}spacecat.db?mode=ro', uri=True)
        cursor = db.cursor()
        query = (message.guild.id,)
        cursor.execute(
            "SELECT prefix FROM server_settings WHERE server_id=?", query)
        prefix = cursor.fetchone()[0]
        db.close()

        if prefix:
            return commands.when_mentioned_or(prefix)(bot, message)
    except sqlite3.OperationalError:
        pass

    # Use the prefix set in config if no custom server prefix is set
    config = toml.load(constants.DATA_DIR + 'config.toml')
    prefix = config['base']['prefix']
    return commands.when_mentioned_or(prefix)(bot, message)


def run(firstrun=False):
    config = toml.load(constants.DATA_DIR + 'config.toml')
    apikey = config['base']['apikey']

    # Attempt to use API key from config and output error if unable to run
    try:
        print("Active API Key: " + apikey + "\n")
        bot = commands.Bot(command_prefix=get_prefix)
        bot = load_modules(bot)
        bot.run(apikey)
    except discord.LoginFailure:
        if firstrun:
            print(
                "Looks like that API key didn't work.\n"
                "Run the program again and use the correct key.")
            os.remove(constants.DATA_DIR + "config.toml")
            return
        print(
            "[Error]\n"
            "The API key doesn't work.\n"
            "Set a new key by running the bot again"
            "with the --apikey argument.\n"
            "Eg. ./spacecat --apikey <insert_key>")
        return