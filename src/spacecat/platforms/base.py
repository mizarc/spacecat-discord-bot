from abc import ABC, abstractmethod


class BaseClient(ABC):
    @abstractmethod
    async def start(self, token: str):
        """Logic to log into the platform."""
