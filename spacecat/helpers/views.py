"""
Module for providing custom views for discord interactions.

In order to keep views consistent, this module contains views for
things like paginated content.
"""

from __future__ import annotations

import copy
import math
from typing import Self, override

import discord.ui
from discord.ui import Button, View


class DefaultView(View):
    """Base view class to send messages with UI interactions."""

    def __init__(
        self: DefaultView,
        text: str = "",
        embed: discord.Embed | None = None,
        timeout: int = 300,
    ) -> None:
        """
        Initializes a new DefaultView object.

        Parameters:
            text (str | None, optional): The text content of the view.
                Defaults to None.
            embed (discord.Embed, optional): The embed content of the
                view. Defaults to None.
            timeout (int, optional): The timeout duration for the view
                in seconds. Defaults to 300.

        Returns:
            None
        """
        self.text = text
        self.message = None
        self.embed = embed
        super().__init__(timeout=timeout)

    async def on_timeout(self: Self) -> None:
        """Disables all interaction buttons on view timeout."""
        if self.message is not None:
            for item in self.children:
                if isinstance(item, Button):
                    item.disabled = True
            await self.message.edit(view=self)

    async def send(self: Self, interaction: discord.Interaction) -> None:
        """
        Sends the view through the interaction response.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        if self.embed is not None:
            await interaction.response.send_message(self.text, view=self, embed=self.embed)
        else:
            await interaction.response.send_message(self.text, view=self)
        self.message = await interaction.original_response()


class PaginatedView(DefaultView):
    """View for displaying multi page list content."""

    def __init__(
        self: PaginatedView,
        base_embed: discord.Embed,
        items_header: str,
        items: list[str],
        items_per_page: int = 5,
        starting_page: int = 1,
    ) -> None:
        """
        Initializes a new PaginatedView object.

        Args:
            base_embed (discord.Embed): The base embed for the view.
            items_header (str): The header for the items in the view.
            items (list[str]): The list of items to be paginated.
            items_per_page (int, optional): The number of items per
                page. Defaults to 5.
            starting_page (int, optional): The starting page number.
                Defaults to 1.

        Returns:
            None
        """
        # Included data
        self.items_header = items_header
        self.items = items
        self.items_per_page = items_per_page
        self.base_embed = base_embed
        super().__init__(text="")

        # Current state
        self.current_page = min(starting_page, math.ceil(len(self.items) / self.items_per_page))

    @override
    async def send(self: Self, interaction: discord.Interaction) -> None:
        self.create_embed()
        await super().send(interaction)

    def create_embed(self: Self) -> None:
        """
        Creates an embed for the PaginatedView.

        This function utilises the available data to produce an embed
        page containing data that should be displayed on said page. It
        takes into account the current page number as well as the amount
        of items that should be displayed per page, providing an index
        value to each item in a list.
        """
        items_field = []
        last_item = self.current_page * self.items_per_page
        first_item = last_item - self.items_per_page
        items_to_add = self.items[first_item:last_item]
        for index, item in enumerate(items_to_add):
            items_field.append(
                f"{self.current_page * self.items_per_page - self.items_per_page + index+1}. "
                f"{item}"
            )
        if not items_field:
            items_field.append("\u200b")

        self.embed = copy.copy(self.base_embed)
        self.embed.add_field(name=self.items_header, value="\n".join(items_field), inline=False)

    async def update_message(self: Self, interaction: discord.Interaction) -> None:
        """
        Updates the message.

        Args:
            interaction (discord.Interaction): The interaction object.

        Returns:
            None
        """
        self.create_embed()
        await interaction.edit_original_response(embed=self.embed, view=self)

    def update_buttons(self: Self) -> None:
        """
        Updates button state based on available pages.

        Button should only be enabled if it is possible to naviagate to
        said page. Eg. if the current page is the last page, the next
        and last buttons should be disabled.

        Parameters:
            self (Self): The instance of the class.
        """
        is_page_count = self.current_page >= len(self.items) / self.items_per_page
        self.first_button.disabled = self.current_page == 1
        self.back_button.disabled = self.current_page == 1
        self.forward_button.disabled = is_page_count
        self.last_button.disabled = is_page_count
        self.pages_button.label = (
            f"Page {self.current_page} / {math.ceil(len(self.items) / self.items_per_page)}"
        )

    @discord.ui.button(label="|<", style=discord.ButtonStyle.green)
    async def first_button(self: Self, interaction: discord.Interaction, _: Button) -> None:
        """
        Moves the view back to the first page on first button press.

        Args:
            interaction (discord.Interaction): The user interaction.
            _ (Button): The clicked button.
        """
        await interaction.response.defer()
        self.current_page = 1
        await self.update_message(interaction)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self: Self, interaction: discord.Interaction, _: Button) -> None:
        """
        Moves the view back a page on back button press.

        Args:
            interaction (discord.Interaction): The user interaction.
            _ (Button): The clicked button.
        """
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pages_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """
        A view only button placeholder displaying the current page.

        Parameters:
            interaction (discord.Interaction): The user interaction.
            button (discord.ui.Button): The clicked button.
        """

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self: Self, interaction: discord.Interaction, _: Button) -> None:
        """
        Moves the view forward a page on foward button press.

        Args:
            interaction (discord.Interaction): The user interaction.
            _ (Button): The clicked button.
        """
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message(interaction)

    @discord.ui.button(label=">|", style=discord.ButtonStyle.green)
    async def last_button(self: Self, interaction: discord.Interaction, _: Button) -> None:
        """
        Moves the view to the last page on last button page.

        Args:
            interaction (discord.Interaction): The user interaction.
            _ (Button): The clicked button.
        """
        await interaction.response.defer()
        self.current_page = math.ceil(len(self.items) / self.items_per_page)
        await self.update_message(interaction)


class EmptyPaginatedView(DefaultView):
    """Dummy paginated view to display non functional page buttons."""

    def __init__(
        self: EmptyPaginatedView, base_embed: discord.Embed, items_header: str, text_content: str
    ) -> None:
        """
        Initializes a new EmptyPaginatedView object.

        Args:
            base_embed (discord.Embed): The base embed for the view.
            items_header (str): The header for the items in the view.
            text_content (str): The text content for the view.
        """
        # Included data
        self.embed = base_embed
        self.items_header = items_header
        self.text_content = text_content
        super().__init__(text="")

    @override
    async def send(self: Self, interaction: discord.Interaction) -> None:
        self.update_buttons()
        self.create_embed()
        await super().send(interaction)

    def create_embed(self: Self) -> None:
        """
        Creates an embed for the PaginatedView.

        This function simply adds the header and text content to the
        embed as is.
        """
        self.embed.add_field(name=self.items_header, value=self.text_content, inline=False)

    def update_buttons(self: Self) -> None:
        """Updates the state of the buttons to all be disabled."""
        self.back_button.disabled = True
        self.forward_button.disabled = True
        self.last_button.disabled = True
        self.pages_button.label = "Page 1 / 1"

    @discord.ui.button(label="|<", style=discord.ButtonStyle.green)
    async def first_button(self: Self, _: discord.Interaction, __: discord.ui.Button) -> None:
        """
        Dummy button. Doesn't do anything.

        Args:
            _ (discord.Interaction): The user interaction.
            __ (discord.ui.Button): The clicked button.
        """

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self: Self, _: discord.Interaction, __: discord.ui.Button) -> None:
        """
        Dummy button. Doesn't do anything.

        Args:
            _ (discord.Interaction): The user interaction.
            __ (discord.ui.Button): The clicked button.
        """

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pages_button(self: Self, _: discord.Interaction, __: discord.ui.Button) -> None:
        """
        Dummy button. Doesn't do anything.

        Args:
            _ (discord.Interaction): The user interaction.
            __ (discord.ui.Button): The clicked button.
        """

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self: Self, _: discord.Interaction, __: discord.ui.Button) -> None:
        """
        Dummy button. Doesn't do anything.

        Args:
            _ (discord.Interaction): The user interaction.
            __ (discord.ui.Button): The clicked button.
        """

    @discord.ui.button(label=">|", style=discord.ButtonStyle.green)
    async def last_button(self: Self, _: discord.Interaction, __: discord.ui.Button) -> None:
        """
        Dummy button. Doesn't do anything.

        Args:
            _ (discord.Interaction): The user interaction.
            __ (discord.ui.Button): The clicked button.
        """
