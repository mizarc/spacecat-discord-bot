import fluxer
from ..base import BaseClient


class FluxerClient(fluxer.Bot, BaseClient):
    def __init__(self, core_engine, *args, **kwargs):
        # Initialize fluxer.Bot with your prefix and intents
        super().__init__(command_prefix="!", intents=fluxer.Intents.default(), *args, **kwargs)
        self.core = core_engine

    async def on_ready(self):
        print(f"Fluxer side ready: {self.user.username}")

    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author.id == self.user.id:
            return
        
        # Check if message starts with command prefix
        if message.content.startswith('!'):
            command = message.content[1:].split()[0].lower()
            
            # Delegate to core engine for command processing
            response = await self.core.process_command(command, user=message.author.username)
            await message.reply(response)

    # Implementation of the BaseClient "contract"
    async def send_message(self, channel_id: str, text: str):
        await self.http_client.create_message(
            channel_id=channel_id,
            content=text
        )

    async def start_bot(self, token: str):
        await self.start(token)
