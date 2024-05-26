"""
This package provides imports for all action types and repositories.

Actions can be appended to events to be run in sequential order when a
dispatch trigger is executed. The provided classes provide all necessary
data to perform the intended action, with a repository to store data.

This init file allows for the easy import of said actions so that all
actions are are available through the actions package.

The actions provided by this module include:
- Broadcast: Sends a message to all channels the bot has access to.
- ChannelPrivate: Sets a channel to private.
- ChannelPublic: Sets a channel to public.
- Message: Sends a message to a specific channel.
- VoiceKick: Kicks a user from a voice channel.
- VoiceMove: Moves a user to a voice channel.
"""

from .broadcast_action import BroadcastAction, BroadcastActionRepository
from .channelprivate_action import ChannelPrivateAction, ChannelPrivateActionRepository
from .channelpublic_action import ChannelPublicAction, ChannelPublicActionRepository
from .message_action import MessageAction, MessageActionRepository
from .voicekick_action import VoiceKickAction, VoiceKickActionRepository
from .voicemove_action import VoiceMoveAction, VoiceMoveActionRepository

__all__ = [
    "BroadcastAction",
    "BroadcastActionRepository",
    "ChannelPrivateAction",
    "ChannelPrivateActionRepository",
    "ChannelPublicAction",
    "ChannelPublicActionRepository",
    "MessageAction",
    "MessageActionRepository",
    "VoiceKickAction",
    "VoiceKickActionRepository",
    "VoiceMoveAction",
    "VoiceMoveActionRepository",
]
