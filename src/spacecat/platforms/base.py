from abc import ABC, abstractmethod

class BaseClient(ABC):
    @abstractmethod
    async def start(self, token: str):
        """Logic to log into the platform."""
        pass

    @abstractmethod
    async def send_message(self, channel_id: str, text: str):
        """Standardized way to send a message."""
        pass