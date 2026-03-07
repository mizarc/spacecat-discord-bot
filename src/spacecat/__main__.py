import argparse
import asyncio
from spacecat.platforms.fluxer.client import FluxerClient
#from spacecat.platforms.discord.client import DiscordClient  # Assuming this is ready


async def start_app():
    # 1. Setup Argument Parser
    parser = argparse.ArgumentParser(description="Spacecat Discord Bot Runner")
    parser.add_argument(
        "platform",
        choices=["fluxer", "discord"],
        help="Which platform to launch"
    )
    parser.add_argument("--token", help="Override the token from CLI", default=None)

    args = parser.parse_args()
    engine = CoreEngine()

    # 2. Select the Client
    if args.platform == "fluxer":
        print("--- Launching Fluxer Platform ---")
        client = FluxerClient(core_engine=engine)
        token = args.token or "YOUR_DEFAULT_FLUXER_TOKEN"
    else:
        print("--- Launching Discord Platform ---")
        client = DiscordClient(core_engine=engine)
        token = args.token or "YOUR_DEFAULT_DISCORD_TOKEN"

    # 3. Run the selected client
    async with client:
        await client.start_bot(token)


def main():
    try:
        asyncio.run(start_app())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")


if __name__ == "__main__":
    main()