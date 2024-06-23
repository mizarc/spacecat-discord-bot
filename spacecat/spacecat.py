#!/usr/bin/env python3

"""
This module represents the core bot functionality.

It holds the main bot class `SpaceCat` that is responsible for starting
the bot and setting up the bot instance. The `Core` cog provides basic
features for bot administrators to use to configure bot extensions.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands
from discord.ext import commands

from spacecat.helpers import constants, module_handler, permissions

if TYPE_CHECKING:
    from spacecat.instance import Instance


class SpaceCat(commands.Bot):
    """The main bot class."""

    def __init__(self: SpaceCat, instance: Instance) -> None:
        """
        Initializes the SpaceCat class with the provided bot instance.

        Args:
            instance (Instance): The instance data to use for the bot.
        """
        self.instance = instance
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self: SpaceCat) -> None:
        """
        Sets up the modules on bot load.

        This function is called when the bot is ready to start running.
        It loads all the modules that are required for the bot to
        function properly.
        """
        permissions.init_database(self.instance.get_database())
        await self.setup_server_data_tables()
        await self.load_modules()

    async def load_modules(self: Self) -> None:
        """Loads all modules from the modules folder for the bot."""
        # Enable enabled modules from list
        await self.add_cog(Core(self))
        modules = module_handler.get_enabled()
        for module in modules:
            module_path = "spacecat.modules." + module
            try:
                await self.load_extension(module_path)
            except Exception:  # noqa: BLE001 Anything could error here.
                try:
                    module_path = f"spacecat.modules.{module}.{module}"
                    await self.load_extension(module_path)
                except Exception as exception:  # noqa: BLE001 Once again.
                    print(
                        f"Failed to load extension {module}\n"
                        f"{type(exception).__name__}: {exception}\n"
                    )

    async def setup_server_data_tables(self: Self) -> None:
        """Sets up the server data table."""
        database = self.instance.get_database()
        database.execute(
            "CREATE TABLE IF NOT EXISTS server_settings (id INTEGER PRIMARY KEY, timezone TEXT, "
            "disable_default_permissions INTEGER)"
        )


class Core(commands.Cog):
    """The bare minimum for bot functionality."""

    def __init__(self: Core, bot: SpaceCat) -> None:
        """
        Initializes a new instance of the Core class.

        Args:
            bot (SpaceCat): The SpaceCat bot instance.
        """
        self.bot = bot

    def cog_load(self: Core) -> None:
        """Listener that sets up the server settings on load."""
        self.bot.tree.on_error = self.on_command_error

    @commands.Cog.listener()
    async def on_ready(self: Core) -> None:
        """
        Performs basic bot launch actions.

        This configures the cache, as well as setting status and
        activity. Useful info is displayed to the console.
        """
        config = self.bot.instance.get_config()

        if self.bot.user is None:
            return

        # Create cache folder if it doesn't exist
        Path(constants.CACHE_DIR).mkdir(parents=True, exist_ok=True)

        # Run initial configurator as long as values are missing
        if "adminuser" not in config["base"]:
            await self._set_admin()
        servers = self.bot.guilds
        if not servers:
            await self._send_invite()

        # Output launch completion message
        print(self.bot.user.name + " has successfully launched")
        print(f"Bot ID: {self.bot.user.id}")
        if module_handler.get_enabled():
            print("Enabled Module(s): " f"{', '.join(module_handler.get_enabled())}")
        if module_handler.get_disabled():
            print("Disabled Module(s): " f"{', '.join(module_handler.get_disabled())}")
        print("--------------------")

        # Change status if specified in config
        try:
            status_name = config["base"]["status"]
            status = discord.Status[status_name]
            await self.bot.change_presence(status=status)
        except KeyError:
            pass

        # Change activity if specified in config
        try:
            activity_name = config["base"]["activity_type"]
            activity_type = discord.ActivityType[activity_name]

            activity = discord.Activity(
                type=activity_type,
                name=config["base"]["activity_name"],
                url="https://www.twitch.tv/monstercat",
            )
            await self.bot.change_presence(activity=activity)
        except (KeyError, TypeError):
            pass

    @commands.Cog.listener()
    async def on_guild_join(self: Self, guild: discord.Guild) -> None:
        """
        Runs on guild join.

        Args:
            guild (discord.Guild): The guild that was joined.
        """

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        """
        Performs actions on detected keywords.

        If the bot user is mentioned, it spits out an info message to
        help the user understand how to use the bot.

        If the word "sync" is included, it performs a command tree
        structure sync of the bot.

        Parameters:
            message (discord.Message): The message object representing
                the incoming message.
        """
        if message.author.bot or self.bot.user is None:
            return

        words = message.content.split()
        mentions = [f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"]
        for mention in mentions:
            if mention == message.content:
                await self.process_info(message.channel)
                return
            if len(words) > 0 and words[0] == mention and words[1] == "sync":
                await self.process_sync(message.channel)
                return

    async def on_command_error(
        self: Self, interaction: discord.Interaction, _: app_commands.AppCommandError
    ) -> None:
        """
        Throws out users without permission to use the command.

        Args:
            interaction (discord.Interaction): The user interaction.
        """
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )

    async def process_info(self: Self, channel: discord.abc.Messageable) -> None:
        """
        Outputs a info box to the user.

        Args:
            channel (discord.abc.Messagable): The channel to send the
                response to.
        """
        # Info on how to use the bot
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} Hello There!",
            description="I'm here to provide a useful set a features",
        )
        embed.add_field(
            name="Need Help?", value="Type `/help` to get a list of commands", inline=False
        )
        embed.add_field(
            name="Want more features added?",
            value="[Request them here]" "(https://gitlab.com/Mizarc/spacecat-discord-bot/issues)",
            inline=False,
        )
        await channel.send(embed=embed)

    async def process_sync(self: Self, channel: discord.abc.Messageable) -> None:
        """
        Resyncronises the command tree of the bot.

        Run this whenever commands or other UI features are added and
        need to be synced.

        Args:
            channel (discord.abc.Messagable): The channel to send the
                response to.
        """
        await self.bot.tree.sync()
        await channel.send("Commands have been synced")

    # Commands
    @app_commands.command()
    @permissions.check()
    async def ping(self: Self, interaction: discord.Interaction) -> None:
        """A simple ping to check the bot response time."""
        if self.bot.user is None:
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"{self.bot.user.name} is operational at {int(self.bot.latency * 1000)}ms",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.check()
    async def version(self: Self, interaction: discord.Interaction) -> None:
        """Check the current bot version and source page."""
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description="**Bot is currently using version:**\n"
            "[SpaceCat Discord Bot `v0.4.0 Experimental`]"
            "(https://gitlab.com/Mizarc/spacecat-discord-bot)",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.exclusive()
    async def modules(self: Self, interaction: discord.Interaction) -> None:
        """Lists all currently available modules."""
        if self.bot.user is None:
            return

        enabled = module_handler.get_enabled()
        disabled = module_handler.get_disabled()

        # Create embed
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} {self.bot.user.name} Modules",
        )

        # Categorise modules into enabled and disabled fields
        if enabled:
            embed.add_field(name="Enabled", value=", ".join(enabled), inline=False)
        if disabled:
            embed.add_field(name="Disabled", value=", ".join(disabled), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.exclusive()
    async def reload(
        self: Self, interaction: discord.Interaction, module: str | None = None
    ) -> None:
        """Reloads all or specified module."""
        enabled_modules = module_handler.get_enabled()
        modules_to_load = []
        failed_modules = []

        # If a module is specified, set it to load (if valid)
        # Otherwise, load all enabled modules
        if module:
            if module not in enabled_modules:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"{module} is not a valid or enabled module",
                )
                await interaction.response.send_message(embed=embed)
                return
            modules_to_load = [module]
        else:
            modules_to_load = enabled_modules

        # Reload modules in list
        for module in modules_to_load:
            try:
                module_path = "modules." + module
                await self.bot.reload_extension(module_path)
            except commands.ExtensionNotLoaded:
                try:
                    module_path = f"modules.{module}.{module}"
                    await self.bot.reload_extension(module_path)
                except commands.ExtensionNotLoaded:
                    failed_modules.append(module[8:])

        # Ouput error if specified module failed to load
        if module and failed_modules:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Failed to reload module \
                `{module[8:]}`",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Output error if some modules failed to load
        if failed_modules:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Failed to reload module(s): \
                `{', '.join(failed_modules)}`. \
                Other modules have successfully reloaded",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Notify user of successful module reloading
        if module:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Reloaded module `{module[8:]}` successfully",
            )
        else:
            embed = discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description="All modules reloaded successfully",
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.exclusive()
    async def enable(self: Self, interaction: discord.Interaction, module: str) -> None:
        """Enables a module."""
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Module `{module}` does not exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Check config to see if module is already enabled
        disabled_modules = module_handler.get_disabled()
        if disabled_modules is None or module not in disabled_modules:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Module `{module}` is already enabled",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Enable module and write to config
        await self.bot.load_extension(f"{constants.MAIN_DIR}.modules.{module}")
        config = self.bot.instance.get_config()
        config["base"]["disabled_modules"].remove(module)
        self.bot.instance.save_config(config)
        embed = discord.Embed(
            colour=constants.EmbedStatus.YES.value, description=f"Module `{module}` enabled"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.exclusive()
    async def disable(self: Self, interaction: discord.Interaction, module: str) -> None:
        """Disables a module."""
        # Check if module exists by taking the list of extensions from the bot
        if module not in module_handler.get():
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Module `{module}` does not exist",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Check config to see if module is already disabled
        disabled_modules = module_handler.get_disabled()
        try:
            if module in disabled_modules:
                embed = discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"Module `{module}` is already disabled",
                )
                await interaction.response.send_message(embed=embed)
                return

            # Add to list if list exists or create list if it doesn't
            config = self.bot.instance.get_config()
            config["base"]["disabled_modules"].append(module)
        except TypeError:
            config = self.bot.instance.get_config()
            config["base"]["disabled_modules"] = [module]

        # Disable module and write to config
        await self.bot.unload_extension(f"{constants.MAIN_DIR}.modules.{module}")
        self.bot.instance.save_config(config)
        embed = discord.Embed(
            colour=constants.EmbedStatus.NO.value, description=f"Module `{module}` disabled"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command()
    @permissions.exclusive()
    async def exit(self: Self, _: discord.Interaction) -> None:
        """Shuts down the bot."""
        # Clear the cache folder if it exists
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(constants.CACHE_DIR)

        await self.bot.close()

    async def _set_admin(self: Self) -> None:
        """
        Prompts the user to set a bot administrator.

        User are to be instructed to find their user ID and paste it
        into the console in order for the bot to recognise them as the
        bot administrator.
        """
        if self.bot.user is None:
            return

        config = self.bot.instance.get_config()
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
                "6. Right click on your user and click 'Copy ID'\n"
            )

            # Check to see if the user ID is valid
            try:
                idinput = int(input("Paste your ID right here: "))
                print("--------------------\n")
                user = await self.bot.fetch_user(idinput)
                await user.send("Hello there!")
            except (ValueError, AttributeError):
                print("It looks like that is not a valid ID.\n" "Lets try this again.\n")
                input("Press Enter to continue...")
                print("--------------------\n")
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(1)

            # Ask for confirmation
            while True:
                print(
                    f"Verify that {user} is you.\n"
                    "If your user settings allow it, you should've also "
                    "recieved a private message from me.\n"
                )
                confirm = input("Type 'yes' to confirm, or 'no' to set a new ID: ")
                print("--------------------\n")

                if confirm == "yes":
                    config["base"]["adminuser"] = [idinput]
                    break
                if confirm == "no":
                    break
                continue

        self.bot.instance.save_config(config)
        await asyncio.sleep(1)

    async def _send_invite(self: Self) -> None:
        """
        Sends the user an invite link to add bot to server.

        This is just a method that sends a text output to the console.
        Ensure that the link is still functional using current method.
        """
        if self.bot.user is None:
            return

        # Provide a link to join the server
        print(
            "[Invite]\n"
            "I need to join your Discord server if i'm not in it already.\n"
            "Click the link below or copy it into your web browser.\n"
            "You can give this link to other users to help "
            "spread your bot around.\n\n"
            "https://discordapp.com/oauth2/authorize?"
            f"client_id={self.bot.user.id}&scope=bot&permissions=8\n"
            "--------------------\n"
        )

        # Set default values and save config
        config = self.bot.instance.get_config()
        config["base"]["status"] = "online"
        config["base"]["activity_type"] = None
        config["base"]["activity_name"] = None
        self.bot.instance.save_config(config)


def introduction(instance: Instance) -> None:
    """
    Guides the user through the introduction setup sequence.

    Parameters:
        instance (Instance): The instance of the bot.
    """
    print(
        "Hey there,\n"
        "The bot will need some configuring to be able to run.\n"
        "Don't worry, I'll walk you through everything.\n"
    )

    input("Press Enter to continue...")
    print("--------------------\n")
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
        "(Don't ever reveal this token to anyone you don't trust)\n"
    )

    keyinput = input("Paste your token right here: ")
    print("--------------------\n")

    # Add API key to config file
    config = instance.get_config()
    config["base"]["apikey"] = keyinput
    instance.save_config(config)


def run(instance: Instance, *, first_run: bool) -> None:
    """
    Performans initialisations to run the bot.

    Args:
        instance (Instance): The instance of the bot.
        first_run (bool, optional): Whether or not to run the first run
            sequence of the bot.
    """
    config = instance.get_config()
    apikey = config["base"]["apikey"]

    # Attempt to use API key from config and output error if unable to run
    try:
        print("Active API Key: " + apikey + "\n")
        bot = SpaceCat(instance)
        bot.run(apikey)
    except discord.LoginFailure:
        if first_run:
            print(
                "Looks like that API key didn't work.\n"
                "Run the program again and use the correct key."
            )
            config["base"].pop("apikey")
            instance.save_config(config)
            return
        print(
            "[Error]\n"
            "The API key doesn't work.\n"
            "Set a new key by running the bot again"
            "with the --apikey argument.\n"
            "Eg. ./spacecat --apikey <insert_key>"
        )
        return
