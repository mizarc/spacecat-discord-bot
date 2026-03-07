import fluxer
from ..base import BaseClient


class FluxerClient(fluxer.Bot, BaseClient):
    def __init__(self, core_engine, *args, **kwargs):
        # Initialize fluxer.Bot with your prefix and intents
        super().__init__(command_prefix="!", intents=fluxer.Intents.default(), *args, **kwargs)
        self.core = core_engine

        # Register commands inside __init__ or via setup methods
        self.add_command(self.ping)

    async def on_ready(self):
        print(f"Fluxer side ready: {self.user.username}")

    # Use the 'ctx' to pass data to your core logic
    @fluxer.command()
    async def ping(self, ctx):
        # We delegate the logic to the core
        response = await self.core.process_command("ping", user=ctx.author.username)
        await ctx.reply(response)

    # Implementation of the BaseClient "contract"
    async def send_message(self, channel_id: str, text: str):
        channel = self.get_channel(channel_id)
        if channel:
            await channel.send(text)

    async def start_bot(self, token: str):
        await self.start(token)