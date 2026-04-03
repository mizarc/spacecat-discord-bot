"""
This module provides informational and reference tools.

Commands within this module focus on knowledge retrieval, including
Wikipedia lookups, dictionary definitions, and language translation.
"""

from __future__ import annotations

import asyncio
from typing import Self

import fluxer

import spacecat.core.features.knowledge as core_knowledge
from spacecat.platforms.fluxer.helpers import permissions


class Knowledge(fluxer.Cog):
    """Commands suite to provide reference and knowledge lookups."""

    def __init__(self: Knowledge, bot: fluxer.Bot) -> None:
        """Initializes the Knowledge cog."""
        super().__init__(bot)

    @fluxer.Cog.command()
    @permissions.check()
    async def currency(
        self: Self, ctx: fluxer.Message, amount: float, base: str, target: str
    ) -> None:
        """
        Convert currency. Usage: !convert 100 USD EUR.

        Args:
            ctx: The command context.
            amount: The number to convert.
            base: The starting currency code (e.g. USD).
            target: The target currency code (e.g. EUR).
        """
        result = await asyncio.to_thread(core_knowledge.currency, amount, base, target)

        if not result["success"]:
            await ctx.reply(f"❌ {result['error']}")
            return

        # Build the Embed
        embed = fluxer.Embed(title="💱 Currency Conversion")

        # Text Data
        embed.add_field(
            name="Result",
            value=(
                f"{result['amount']:,} {result['base']} = {result['result']:,} {result['target']}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Exchange Rate",
            value=f"1 {result['base']} = {result['rate']:.4f} {result['target']}",
            inline=True,
        )

        # Attach the Graph
        if result["graph_url"]:
            embed.set_image(url=result["graph_url"])
            embed.set_footer(text="Graph shows 1-year historical trend line.")

        await ctx.reply(embed=embed)

    @fluxer.Cog.command()
    @permissions.check()
    async def define(self: Self, ctx: fluxer.Message, word: str) -> None:
        """
        Get the definition of a word.

        Args:
            ctx: The command context.
            word: The word to define.
        """
        result = await asyncio.to_thread(core_knowledge.define, word)

        if "error" in result:
            await ctx.reply(result["error"])
            return

        phonetic = f" *({result['phonetic']})*" if result["phonetic"] else ""
        response = f"📚 **{result['word']}**{phonetic}\n{result['definition']}"
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def thesaurus(self: Self, ctx: fluxer.Message, word: str) -> None:
        """Find synonyms and antonyms for a word."""
        result = await asyncio.to_thread(core_knowledge.thesaurus, word)

        if "error" in result:
            await ctx.reply(result["error"])
            return

        syns = ", ".join(result["synonyms"]) or "None found."
        ants = ", ".join(result["antonyms"]) or "None found."

        response = f"📖 **{result['word']}**\n**Synonyms:** {syns}\n**Antonyms:** {ants}"
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def translate(
        self: Self, ctx: fluxer.Message, target_language: str, *, text: str
    ) -> None:
        """
        Translate text to a specific language.

        Args:
            ctx: The command context.
            target_language: The target language code (e.g., 'es', 'cn', 'jp').
            text: The text to translate.
        """
        translation = await core_knowledge.translate(text, target_language)
        await ctx.reply(f"🌍 **Translation ({target_language}):** {translation}")

    @fluxer.Cog.command()
    @permissions.check()
    async def wiki(self: Self, ctx: fluxer.Message, *, query: str) -> None:
        """
        Search Wikipedia for a topic.

        Args:
            ctx: The command context.
            query: The topic to search for.
        """
        result = await asyncio.to_thread(core_knowledge.wikipedia, query)

        if "error" in result:
            await ctx.reply(result["error"])
            return

        response = f"📖 **{result['title']}**\n{result['content']}\n\n🔗 <{result['url']}>"
        await ctx.reply(response)


async def setup(bot: fluxer.Bot) -> None:
    """Load the Knowledge cog."""
    await bot.add_cog(Knowledge(bot))
