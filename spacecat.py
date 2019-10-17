#!/usr/bin/env python3
from argparse import ArgumentParser
import configparser
import glob
import logging
import os
import shutil
import time

import discord
from discord.ext import commands
import toml

import helpers.appearance as appearance
import helpers.module_handler as module_handler
import helpers.perms as perms
import helpers.perms

# Arguments for API key input
parser = ArgumentParser()
parser.add_argument('--apikey', '-a', help='apikey help', type=str)
parser.add_argument('--user', '-u', help='user help', type=str)
args = parser.parse_args()

# Set command prefix
bot = commands.Bot(command_prefix='!')


class Startup():
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
        # Just some info
        print("Hey there,")
        print("It appears that you don't have a configuration file.")
        print("Don't worry, I'll help you set one up in only 3 steps.")

        input("Press Enter to continue...")
        print('--------------------\n')
        time.sleep(1)

        # Generate Config
        print("[Step 1]")
        print("I'll need to get an API Key from your bot.")
        print("https://discordapp.com/developers/applications/\n")
        print("Open that link and follow these instructions:")
        print("""    1. Create a new application and set a name.
        2. Open the 'Bot' tab on the left.
        3. Select 'Create a Bot' and confirm.
        4. Click on 'Copy' under Token.
        (Don't ever reveal this token to anyone you don't trust)\n""")
        
        keyinput = input("Paste your token right here: ")
        print('--------------------\n')

        config['base'] = {}
        config['base']['apikey'] = keyinput
        run(keyinput)

    def load_modules(self):
        # Fetch modules and remove disabled modules from enable list
        modules = module_handler.get()
        try:
            config = toml.load('config.toml')
            disabled_modules = config['base']['disabled_modules']
            for module in modules:
                if module in disabled_modules:
                    modules.remove(module)
        except KeyError:
            pass

        # Enable modules from list
        bot.add_cog(SpaceCat(bot))
        for x in modules:
            module = 'modules.' + x
            try:
                bot.load_extension(module)
            except Exception as e:
                exc = '{}: {}'.format(type(e).__name__, e)
                print("Failed to load extension {}\n{}\n".format(x, exc))

        self.modules = modules
        self.disabled_modules = disabled_modules

    def run(self, key = None):
        # Run with key input on first run
        if key:
            apikey = key
            try:
                bot.run(apikey)
            except discord.LoginFailure:
                print("""Looks like that API key didn't work.
            Run the program again and use the correct key.""")
        # Run with key in the config
        else:
            config = toml.load('config.toml')
            try:
                apikey = config['base']['apikey']
                print("Active API Key: " + apikey + "\n")
                bot.run(apikey)
            except discord.LoginFailure:
                print("""   [Error]
            The API key doesn't work.
            Set a new key by running the bot again with the --apikey argument.
            Eg. ./spacecat --apikey <insert_key>""")


class SpaceCat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        if os.path.exists('config.toml'):
            config = toml.load('config.toml')
            print(bot.user.name + " has successfully launched")
            print(f"Bot ID: {bot.user.id}")
            if module_handler.get_enabled():
                print(
                    "Enabled Module(s): "
                    f"{', '.join(module_handler.get_enabled())}")
            if module_handler.get_disabled():
                print(
                    "Disabled Module(s): "
                    f"{', '.join(module_handler.get_disabled())}")
            print("--------------------")

            if not os.path.exists("spacecat.db"):
                perms.setup()

            statusname = config['base']['status']
            status = appearance.status_class(statusname)

            try:
                acttypename = config['base']['activity_type']
                activitytype = appearance.activity_type_class(acttypename)

                activity = discord.Activity(
                    type=activitytype,
                    name=config['base']['activity_name'],
                    url="https://www.twitch.tv/monstercat")
                await bot.change_presence(
                    status=status,
                    activity=activity)
            except (KeyError, TypeError):
                await bot.change_presence(status=status)
        else:
            while True:
                # Set a bot admin
                botname = bot.user.name
                print("[Step 2]")
                print(f"Alright, {botname} is now operational.")
                print("Now I'll need to get your discord user ID.")
                print("This will give you admin access to the bot.")
                print("You can set more users later.\n")

                print("Here's what you need to do:")
                print("""    1. Open Discord.
        2. Open your user settings.
        3. Open the appearance tab.
        4. Enable 'Developer Mode' under Advanced.
        5. Exit user settings
        6. Right click on your user and click "Copy ID"\n""")

                idinput = input("Paste your ID right here: ")
                print('--------------------\n')
                
                try:
                    user = bot.get_user(int(idinput))
                    await user.send("Hello there!")
                except (ValueError, AttributeError):
                    print("It looks like that is not a valid ID.")
                    print("Lets try this again.")
                    input("Press Enter to continue...")
                    print('--------------------\n')
                    time.sleep(1)
                    continue

                time.sleep(1)
                
                print("You should've recieved a pm from me through Discord.")
                confirminput = input(
                    "Type 'yes' if you have, or 'no' to set a new ID: ")
                print('--------------------\n')
                if confirminput == "yes":
                    config['Base']['adminuser'] = idinput
                    break
                continue

            config['base']['status'] = 'online'
            config['base']['activity_type'] = None
            config['base']['activity_name'] = None
            toml.dump(config, 'config.toml')
            time.sleep(1)

            # Join a server
            print("[Step 3]")
            
            print("Finally, I need to join your Discord server.")
            print("This is the easiest step.")
            print("Click the link below or copy it into your web browser.")

            botid = bot.user.id
            print(
                f"https://discordapp.com/oauth2/authorize? \
                client_id={botid}&scope=bot&permissions=8")
            print('--------------------\n')


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if os.path.exists('config.ini'):
            perms.new(guild)
        else:
            print("Congrats! I have now had my core functions set up")
            print("You may now continue to configure me through discord.")
            print("Type !help for more info")
            print('--------------------\n')


    # Commands
    @commands.command()
    @perms.check()
    async def ping(self, ctx):
        """A simple command to check if the bot is working."""
        embed = discord.Embed(
            colour=appearance.embed_type('accept'), 
            description=f"{bot.user.name} is operational at \
            {int(bot.latency * 1000)}ms")
        await ctx.send(embed=embed)


    @commands.command()
    @perms.exclusive()
    async def reload(self, ctx, module=None):
        """Reloads all or specified module"""
        if module is None:
            modulelist = module_handler.get()
            for y in modulelist:
                try:
                    z = 'modules.' + y
                    bot.unload_extension(z)
                    bot.load_extension(z)
                except Exception:
                    embed = discord.Embed(
                        colour=appearance.embed_type('warn'),
                        description=f"Failed to reload module {module}. \
                        Reloading has stopped.")
                    await ctx.send(embed=embed)
                    return
            embed = discord.Embed(
                colour=appearance.embed_type('accept'),
                description=f"Reloaded all modules successfully")
            await ctx.send(embed=embed)
            return
        try:
            z = 'modules.' + module
            bot.unload_extension(z)
            bot.load_extension(z)
            embed = discord.Embed(
                colour=appearance.embed_type('accept'),
                description=f"Reloaded module {module} successfully")
        except ModuleNotFoundError:
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"{module} is not a valid module")
        except Exception:
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Failed to load module {module}")
        await ctx.send(embed=embed)


    @commands.command()
    @perms.exclusive()
    async def enable(self, ctx, module):
        """Enables a module"""
        # Check if module exists by taking the list of extensions from the bot
        modules = module_handler.get()
        if module not in modules:
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is disabled
        config = toml.load('config.toml')
        try:
            if module not in config['base']['disabled_modules']:
                raise ValueError('Module not found in list')

            # Enable module and write to config`
            bot.load_extension(f'modules.{module}')
            config['base']['disabled_modules'].remove(module)
            with open("config.toml", "w") as config_file:
                toml.dump(config, config_file)

            # Set message depending on result
            embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"Module `{module}` enabled")
        except KeyError:
            embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` is already enabled")

        await ctx.send(embed=embed)


    @commands.command()
    @perms.exclusive()
    async def disable(self, ctx, module):
        """Disables a module"""
        # Check if module exists by taking the list of extensions from the bot
        modules = module_handler.get()
        if module not in modules:
            embed = discord.Embed(
            colour=appearance.embed_type('warn'),
            description=f"Module `{module}` does not exist")
            await ctx.send(embed=embed)
            return

        # Check config to see if module is already disabled
        config = toml.load('config.toml')
        try:
            if module in config['base']['disabled_modules']:
                embed = discord.Embed(
                colour=appearance.embed_type('warn'),
                description=f"Module `{module}` is already disabled")
                await ctx.send(embed=embed)
                return
            
            # Create or append to list depend on if list exists
            config['base']['disabled_modules'].append(module)
        except KeyError:
            config['base']['disabled_modules'] = [module]

        # Disable module and write to config
        bot.unload_extension(f'modules.{module}')
        with open("config.toml", "w") as config_file:
            toml.dump(config, config_file)

        # Notify user of change
        embed = discord.Embed(
            colour=appearance.embed_type('accept'),
            description=f"Module `{module}` disabled")
        await ctx.send(embed=embed)


    @commands.command()
    @perms.exclusive()
    async def exit(self, ctx):
        """Shuts down the bot."""
        try:
            shutil.rmtree('cache')
        except:
            pass
        
        await bot.logout()
    

def main():
    startup = Startup()
    startup.logging()

    # Check if config exists and run config creator if it doesn't
    try:
        config = toml.load('config.toml')
    except FileNotFoundError:
        startup.create_config()

    # Append New APIKey to config if specified by argument
    if args.apikey is not None:
        config['base']['apikey'] = args.apikey
        toml.dump(config, 'config.toml')
    
    startup.load_modules()
    startup.run()
    

if __name__ == "__main__":
    main()
