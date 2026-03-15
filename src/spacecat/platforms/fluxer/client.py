import asyncio
import fluxer

from .features.utility import Utility
from ..base import BaseClient
from .features.social import Fun


class FluxerClient(fluxer.Bot, BaseClient):
    def __init__(self, *args, **kwargs):
        # Initialize fluxer.Bot with your prefix and intents
        super().__init__(command_prefix="!", intents=fluxer.Intents.default(), *args, **kwargs)
        self._register_handlers()
        asyncio.create_task(self._register_cogs())

    def _register_handlers(self):
        @self.event
        async def on_ready():
            print(f"Fluxer side ready: {self.user.username}")

    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author.id == self.user.id:
            return

        # Check if message starts with command prefix
        if message.content.startswith('!'):
            command = message.content[1:].split()[0].lower()

            # Delegate to core engine for command processing
            print(command)
            response = await self.core.process_command(command, user=message.author.username)
            print(response)
            await message.reply(response)

    async def _register_cogs(self):
        """Register all cogs for the bot."""
        await self.add_cog(Fun(self))
        await self.add_cog(Utility(self))

    # Implementation of the BaseClient "contract"
    async def send_message(self, channel_id: str, text: str):
        await self.http_client.create_message(
            channel_id=channel_id,
            content=text
        )

    async def start_bot(self, token: str):
        await self.start(token)
