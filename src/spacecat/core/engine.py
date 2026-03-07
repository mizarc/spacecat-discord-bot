# src/spacecat/core/engine.py

class CoreEngine:
    def __init__(self):
        # A dictionary mapping strings to function objects
        self.commands = {}
        self._register_default_commands()

    def _register_default_commands(self):
        """Register built-in commands."""
        self.register("ping", self._cmd_ping)
        self.register("status", self._cmd_status)

    def register(self, name: str, func):
        """Allows you to add new commands from anywhere!"""
        self.commands[name.lower()] = func

    async def process_command(self, command_name: str, **kwargs) -> str:
        command_name = command_name.lower()

        # Look up the command in the registry
        handler = self.commands.get(command_name)

        if handler:
            return await handler(**kwargs)

        return f"I'm sorry, I don't recognize the command: {command_name}"

    # --- Commands move to their own methods (or even separate files) ---

    async def _cmd_ping(self, **kwargs) -> str:
        user = kwargs.get("user", "User")
        return f"Pong! Nice to see you, {user}!"

    async def _cmd_status(self, **kwargs) -> str:
        return "All systems go."