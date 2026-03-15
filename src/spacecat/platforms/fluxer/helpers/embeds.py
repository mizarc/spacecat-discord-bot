"""Helper functions for formatting UniversalEmbed to fluxer Embed format."""

from __future__ import annotations

import fluxer

from spacecat.core.features.utility import UniversalEmbed


def format_universal_embed(universal_embed: UniversalEmbed) -> fluxer.Embed:
    """Convert a UniversalEmbed to a fluxer Embed.
    
    Args:
        universal_embed: The UniversalEmbed object to convert.
        
    Returns:
        A fluxer Embed object.
    """
    embed = fluxer.Embed(
        title=universal_embed["title"],
        color=universal_embed["color"]
    )
    
    # Add fields to the embed
    for field in universal_embed["fields"]:
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field["inline"]
        )
    
    return embed
