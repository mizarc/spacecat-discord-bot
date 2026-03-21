import asyncio

import fluxer
from tortoise import Tortoise

from spacecat.core.registry import ServiceRegistry
from spacecat.platforms.base import BaseClient
from spacecat.platforms.fluxer.dispatcher import FluxerDispatcher
from spacecat.platforms.fluxer.features.scheduler import Scheduler
from spacecat.platforms.fluxer.features.social import Social
from spacecat.platforms.fluxer.features.utility import Utility


class FluxerClient(fluxer.Bot, BaseClient):
    def __init__(self, *args, **kwargs):
        # Initialize fluxer.Bot with your prefix and intents
        super().__init__(command_prefix="!", intents=fluxer.Intents.default(), *args, **kwargs)
        self.dispatcher = FluxerDispatcher(self)
        self._register_handlers()

    def _register_handlers(self):
        @self.event
        async def on_ready():
            print(f"Fluxer endpoint ready: {self.user.username}")
            ServiceRegistry.start_all()
            print("Automation Schedulers: ONLINE")

    async def start_bot(self, token: str):
        # 1. Initialize the Services and Schedulers
        await Tortoise.init(
            db_url="sqlite://spacecat.db",
            modules={
                "models": [
                    "spacecat.core.models.events",
                    "spacecat.core.models.reminders",
                    "spacecat.core.models.actions",
                ]
            },
        )
        await Tortoise.generate_schemas()
        ServiceRegistry.initialize(self.dispatcher)

        # 2. Register Cogs
        await self._register_cogs()

        # 3. Start the bot connection
        try:
            await self.start(token)
        finally:
            # 4. Graceful cleanup on shutdown
            await ServiceRegistry.stop_all()

    async def _register_cogs(self):
        """Register all cogs for the bot."""
        await self.add_cog(Scheduler(self))
        await self.add_cog(Social(self))
        await self.add_cog(Utility(self))
