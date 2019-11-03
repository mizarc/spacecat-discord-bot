#!/usr/bin/env python3
from argparse import ArgumentParser
import asyncio
import configparser
import glob
import logging
import os
import shutil
import sqlite3
import time

import discord
from discord.ext import commands
import toml

import helpers.appearance as appearance
import helpers.module_handler as module_handler
import helpers.perms as perms


# Arguments for API key input
parser = ArgumentParser()
parser.add_argument('--apikey', '-a', help='apikey help', type=str)
parser.add_argument('--user', '-u', help='user help', type=str)
args = parser.parse_args()


class Startup():
    def __init__(self):
        self.bot = commands.Bot(command_prefix=self.get_prefix)

    def logging(self):
        # Setup file logging
        logger = logging.getLogger('discord')
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(
            filename='spacecat.log',
            encoding='utf-8',
            mode='w'
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s:%(levelname)s:%(name)s: %(message)s')
        )
        logger.addHandler(handler)

    def create_config(self):
        # Output introduction
        print(
            "Hey there,\n"
            "It appears that you don't have a configuration file.\n"
            "Don't worry, I'll help you set one up in only 4 steps.\n")

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

        config = {}
        config['base'] = {}
        config['base']['apikey'] = keyinput
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)

        self.run(firstrun=True)

    def load_modules(self):
        # Enable enabled modules from list
        self.bot.add_cog(SpaceCat(self.bot))
        modules = module_handler.get_enabled()
        for module in modules:
            module = 'modules.' + module
            try:
                self.bot.load_extension(module)
            except Exception as exception:
                print(
                    f"Failed to load extension {module}\n"
                    f"{type(exception).__name__}: {exception}\n")

        self.modules = modules

    def run(self, firstrun=False):
        config = toml.load('config.toml')
        apikey = config['base']['apikey']

        # Attempt to use API key from config and output error if unable to run
        try:
            print("Active API Key: " + apikey + "\n")
            self.bot.run(apikey)
        except discord.LoginFailure:
            if firstrun:
                print(
                    "Looks like that API key didn't work.\n"
                    "Run the program again and use the correct key.")
                os.remove("config.toml")
                return
            print(
                "[Error]\n"
                "The API key doesn't work.\n"
                "Set a new key by running the bot again"
                "with the --apikey argument.\n"
                "Eg. ./spacecat --apikey <insert_key>")
            return

    def get_prefix(self, bot, message):
        # Access database if it exists and fetch server's custom prefix if set
        try:
            db = sqlite3.connect('file:spacecat.db?mode=ro', uri=True)
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
        config = toml.load('config.toml')
        prefix = config['base']['prefix']
        return commands.when_mentioned_or(prefix)(bot, message)


class SpaceCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        config = toml.load('config.toml')

        # Create cache folder if it doesn't exist
        try:
            os.mkdir('cache')
        except FileExistsError:
            pass
        
        # Run initial configurator as long as values are missing
        if 'adminuser' not in config['base']:
            await self._set_admin()
        if 'prefix' not in config['base']:
            await self._set_prefix()
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
            statusname = config['base']['status']
            status = appearance.status_class(statusname)
            await self.bot.change_presence(status=status)
        except KeyError:
            pass

        # Change activity if specified in config
        try:
            acttypename = config['base']['activity_type']
            activitytype = appearance.activity_type_class(acttypename)

            activity = discord.Activity(
                type=activitytype,
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
                    colour=appearance.embed_type('info'),
                    description="I'm here to provide a useful set a features")
                image = discord.File(
                    appearance.embed_icons("information"), filename="image.png")
                embed.set_author(
                    name="Hello There!", icon_url="attachment://image.png")
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
                await message.channel.send(file=image, embed=embed)
                return

    # Commands
    @commands.command()
    @perms.check()
    async def ping(self, ctx):
        """A simple ping to check if the bot is responding."""
        embed = discord.Embed(
            colour=appearance.embed_type('accept'), 
            description=f"{self.bot.user.name} is operational at \
            {int(self.bot.latency * 1000)}ms")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.check()
    async def version(self, ctx):
        """Check the current bot version."""
        embed = discord.Embed(
            colour=appearance.embed_type('info'), 
            description="**Bot is currently using version:**\n"
            "[SpaceCat Discord Bot `v0.1.0`]"
            "(https://gitlab.com/Mizarc/spacecat-discord-bot)")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def globalprefix(self, ctx, prefix):
        """Changes the global command prefix"""
        # Changes the prefix entry in the config
        config = toml.load('config.toml')
        config['base']['prefix'] = prefix
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
                colour=appearance.embed_type('accept'),
                description=f"Global command prefix changed to: `{prefix}`.\n\
                Servers with prefix override will not be affected.")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def modules(self, ctx):
        enabled = module_handler.get_enabled()
        disabled = module_handler.get_disabled()

        # Create embed with enabled modules
        image = discord.File(
            appearance.embed_icons("information"),
            filename="image.png")
        embed = discord.Embed(
            colour=appearance.embed_type('info'))
        embed.set_author(
            name=f"{self.bot.user.name} Modules",
            icon_url="attachment://image.png")
        embed.add_field(
            name="Enabled",
            value=', '.join(enabled),
            inline=False)

        # Add disabled modules if there are any
        try:
            embed.add_field(
                name="Disabled",
                value=', '.join(disabled),
                inline=False)
        except TypeError:
            pass

        await ctx.send(file=image, embed=embed)

    @commands.command()
    @perms.exclusive()
    async def reload(self, ctx, module=None):
        """Reloads all or specified module"""
        module_list = module_handler.get_enabled()
        modules_to_load = []
        failed_modules = []

        # Set modules to load depending on if a specific module is selected
        if module:
            if module not in module_list:
                embed = discord.Embed(
                    colour=appearance.embed_type('warn'),
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
                    colour=appearance.embed_type('warn'),
                    description=f"Failed to reload module \
                    `{module[8:]}`")
            await ctx.send(embed=embed)
            return
        elif failed_modules:
            embed = discord.Embed(
                    colour=appearance.embed_type('warn'),
                    description=f"Failed to reload module(s): \
                    `{', '.join(failed_modules)}`. \
                    Other modules have successfully reloaded")
            await ctx.send(embed=embed)
            return
        
        # Notify user of successful module reloading
        if len(modules_to_load) == 1:
            embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"Reloaded module `{module[8:]}` successfully")
        else:
            embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"All modules reloaded successfully")
        
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def enable(self, ctx, module):
        """Enables a module"""
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is already enabled
        disabled_modules = module_handler.get_disabled()
        if disabled_modules is None or module not in disabled_modules:
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` is already enabled")
            await ctx.send(embed=embed)
            return

        # Enable module and write to config
        self.bot.load_extension(f'modules.{module}')
        config = toml.load('config.toml')
        config['base']['disabled_modules'].remove(module)
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"Module `{module}` enabled")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def disable(self, ctx, module):
        """Disables a module"""
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is already disabled
        disabled_modules = module_handler.get_disabled()   
        try:
            if module in disabled_modules:
                embed = discord.Embed(
                    colour=appearance.embed_type('warn'),
                    description=f"Module `{module}` is already disabled")
                await ctx.send(embed=embed)
                return

        # Add to list if list exists or create list if it doesn't
            config = toml.load('config.toml')
            config['base']['disabled_modules'].append(module)
        except TypeError:
            config = toml.load('config.toml')
            config['base']['disabled_modules'] = [module]   

        # Disable module and write to config
        self.bot.unload_extension(f'modules.{module}')
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)
        embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"Module `{module}` disabled")
        await ctx.send(embed=embed)

    @commands.command()
    @perms.exclusive()
    async def exit(self, ctx):
        """Shuts down the bot."""
        # Clear the cache folder if it exists
        try:
            shutil.rmtree('cache')
        except:
            pass
        
        await self.bot.logout()

    async def _set_admin(self):
        config = toml.load('config.toml')
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
                "2. Open your user settings.\n"
                "3. Open the appearance tab.\n"
                "4. Enable 'Developer Mode' under Advanced.\n"
                "5. Exit user settings\n"
                "6. Right click on your user and click 'Copy ID'\n")

            idinput = input("Paste your ID right here: ")
            print('--------------------\n')
            
            # Check to see if the user ID is valid
            try:
                user = self.bot.get_user(int(idinput))
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
                    config['base']['adminuser'] = idinput
                    break
                elif confirm == "no":
                    break
                else:
                    continue

        with open("config.toml", "w") as config_file:
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
        config = toml.load('config.toml')
        config['base']['prefix'] = prefix_input
        with open("config.toml", "w") as config_file:
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
        config = toml.load('config.toml')
        config['base']['status'] = 'online'
        config['base']['activity_type'] = None
        config['base']['activity_name'] = None
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)
        await asyncio.sleep(1)


def main():
    startup = Startup()
    startup.logging()
    startup.load_modules()

    # Check if config exists and run config creator if it doesn't
    try:
        config = toml.load('config.toml')
    except FileNotFoundError:
        setup = startup.create_config()
        if not setup:
            return

    # Append New APIKey to config if specified by argument
    if args.apikey is not None:
        config['base']['apikey'] = args.apikey
        toml.dump(config, 'config.toml')
    
    startup.run()
    

if __name__ == "__main__":
    main()
