import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

import toml

from spacecat.core.engine import CoreEngine

try:
    from spacecat.platforms.fluxer.client import FluxerClient
    FLUXER_AVAILABLE = True
except ImportError as e:
    FLUXER_AVAILABLE = False

try:
    from spacecat.platforms.discord.spacecat import DiscordClient
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False


class InstanceManager:
    """Manages bot instances and their configurations."""
    
    def __init__(self):
        self.base_dir = Path("data")
        self.base_dir.mkdir(exist_ok=True)
        # Initialize platform directories if they don't exist
        for platform in ["discord", "fluxer"]:
            (self.base_dir / platform).mkdir(exist_ok=True)

    def _get_config_path(self, platform: str, name: str) -> Path:
        return self.base_dir / platform / name / "config.toml"
    
    def get_instances(self, platform: str) -> list:
        """Get list of folder names for a given platform."""
        platform_path = self.base_dir / platform
        if not platform_path.exists():
            return []
        return [d.name for d in platform_path.iterdir() if d.is_dir()]
    
    def add_instance(self, platform: str, name: str, token: str, **kwargs):
        """Create a new instance folder."""
        instance_path = self.base_dir / platform / name
        instance_path.mkdir(parents=True, exist_ok=True)

        # Create a clean TOML structure
        config = {
            "settings": {
                "token": token,
                "enabled": True
            }
        }

        # Save to toml file
        with open(self._get_config_path(platform, name), 'w') as f:
            toml.dump(config, f)

    def get_instance_config(self, platform: str, name: str) -> Optional[dict]:
        """
        Get the config file for the instance.
        """
        config_path = self._get_config_path(platform, name)
        if not config_path.exists():
            return None

        try:
            return toml.load(config_path)
        except Exception as e:
            print(f"Error loading TOML: {e}")
            return None


class SpacecatCLI:
    """Main CLI interface for SpaceCat bot."""
    
    def __init__(self):
        self.instance_manager = InstanceManager()
        self.engine = CoreEngine()
    
    def interactive_mode(self):
        """Run interactive CLI mode."""
        print(r"   _____                       ______      __ ")
        print(r"  / ___/____  ____ _________  / ____/___ _/ /_")
        print(r"  \__ \/ __ \/ __ `/ ___/ _ \/ /   / __ `/ __/")
        print(r" ___/ / /_/ / /_/ / /__/  __/ /___/ /_/ / /_  ")
        print(r"/____/ .___/\__,_/\___/\___/\____/\__,_/\__/  ")
        print(r"    /_/                                       ")
        print("=" * 30)
        
        # Platform selection
        platforms = []
        if FLUXER_AVAILABLE:
            platforms.append("fluxer")
        if DISCORD_AVAILABLE:
            platforms.append("discord")
        
        if not platforms:
            print("No platforms are available. Please install platform dependencies:")
            print("  - For Fluxer: pip install spacecat[fluxer]")
            print("  - For Discord: pip install spacecat[discord]")
            print("  - For both: pip install spacecat[all]")
            sys.exit(1)
        
        print("\nAvailable platforms:")
        for i, platform in enumerate(platforms, 1):
            print(f"{i}. {platform.capitalize()}")
        print("0. Exit")
        
        while True:
            try:
                choice = input(f"\nSelect platform (0-{len(platforms)}): ").strip()
                if choice == "0":
                    print("Goodbye!")
                    sys.exit(0)
                
                platform_idx = int(choice) - 1
                if 0 <= platform_idx < len(platforms):
                    platform = platforms[platform_idx]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
        
        # Instance selection
        instances = self.instance_manager.get_instances(platform)
        
        if instances:
            print(f"\nAvailable {platform} instances:")
            for i, instance in enumerate(instances, 1):
                print(f"{i}. {instance}")
            print(f"{len(instances) + 1}. Add new instance")
            print("0. Back to platform selection")
            
            while True:
                try:
                    choice = input(f"\nSelect instance (0-{len(instances) + 1}): ").strip()
                    if choice == "0":
                        return self.interactive_mode()
                    
                    instance_idx = int(choice) - 1
                    
                    if 0 <= instance_idx < len(instances):
                        instance_name = instances[instance_idx]
                        config = self.instance_manager.get_instance_config(platform, instance_name)
                        return platform, instance_name, config.get("settings", {}).get("token")
                    elif instance_idx == len(instances):
                        return self._add_new_instance(platform)
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a number.")
        else:
            print(f"\nNo {platform} instances found.")
            print("1. Add new instance")
            print("0. Back to platform selection")
            
            while True:
                try:
                    choice = input("Select option (0-1): ").strip()
                    if choice == "0":
                        return self.interactive_mode()  # Go back to platform selection
                    elif choice == "1":
                        return self._add_new_instance(platform)
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a number.")
    
    def _add_new_instance(self, platform: str):
        """Add a new instance interactively."""
        print(f"\nAdding new {platform} instance:")
        
        name = input("Instance name: ").strip()
        if not name:
            print("Instance name cannot be empty.")
            return self.interactive_mode()
        
        token = input("Bot token: ").strip()
        if not token:
            print("Token cannot be empty.")
            return self.interactive_mode()
        
        self.instance_manager.add_instance(platform, name, token)
        print(f"Instance '{name}' added successfully!")
        
        return platform, name, token
    
    def run_direct(self, platform: str, instance: Optional[str] = None, token: Optional[str] = None):
        """Run bot directly with command line arguments."""
        if instance and not token:
            config = self.instance_manager.get_instance_config(platform, instance)
            if not config:
                print(f"Instance '{instance}' not found for platform '{platform}'")
                sys.exit(1)
            token = config.get("token")
        
        if not token:
            print("Token is required for direct execution")
            sys.exit(1)
        
        instance_name = instance or "default"
        return platform, instance_name, token


async def start_app():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="SpaceCat Hybrid Bot Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  spacecat                           # Interactive mode
  spacecat discord                   # Interactive mode for Discord
  spacecat fluxer --instance mybot   # Direct execution with saved instance
  spacecat discord --token TOKEN     # Direct execution with token
        """
    )
    
    parser.add_argument(
        "platform",
        nargs="?",
        choices=["fluxer", "discord"],
        help="Platform to run (discord/fluxer). If omitted, runs in interactive mode."
    )
    
    parser.add_argument(
        "--instance", "-i",
        help="Instance name to run (requires saved configuration)"
    )
    
    parser.add_argument(
        "--token", "-t",
        help="Bot token (overrides instance token)"
    )
    
    parser.add_argument(
        "--list-instances", "-l",
        action="store_true",
        help="List all configured instances"
    )
    
    args = parser.parse_args()
    
    cli = SpacecatCLI()
    
    # Handle list instances
    if args.list_instances:
        print("Configured instances:")
        for platform in ["discord", "fluxer"]:
            instances = cli.instance_manager.get_instances(platform)
            if instances:
                print(f"\n{platform.capitalize()}:")
                for instance in instances:
                    print(f"  - {instance}")
        return
    
    # Determine execution mode
    if not args.platform:
        # Interactive mode
        platform, instance_name, token = cli.interactive_mode()
    else:
        # Direct mode
        if args.platform == "discord" and not DISCORD_AVAILABLE:
            print("Discord platform is not available. Install with: pip install spacecat[discord]")
            sys.exit(1)
        
        if args.platform == "fluxer" and not FLUXER_AVAILABLE:
            print("Fluxer platform is not available. Install with: pip install spacecat[fluxer]")
            sys.exit(1)
        
        platform, instance_name, token = cli.run_direct(args.platform, args.instance, args.token)
    
    # Launch the bot
    print(f"\n--- Launching {platform.capitalize()} Platform ({instance_name}) ---")
    
    try:
        if platform == "fluxer":
            if not FLUXER_AVAILABLE:
                print("Fluxer platform is not available. Install with: pip install spacecat[fluxer]")
                sys.exit(1)
            client = FluxerClient(core_engine=cli.engine)
        elif platform == "discord":
            if not DISCORD_AVAILABLE:
                print("Discord platform is not available. Install with: pip install spacecat[discord]")
                sys.exit(1)
            client = DiscordClient(core_engine=cli.engine)
        else:
            print(f"Unsupported platform: {platform}")
            sys.exit(1)
        
        await client.start_bot(token)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


def main():
    """Entry point for the spacecat command."""
    try:
        asyncio.run(start_app())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
