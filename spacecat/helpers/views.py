import copy
import math

import discord.ui
from discord.ui import View, Button


class DefaultView(View):
    def __init__(self, text: str = None, embed: discord.Embed = None, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.text = text
        self.embed = embed
        self.message = None

    async def on_timeout(self) -> None:
        if self.message is not None:
            for item in self.children:
                if isinstance(item, Button):
                    item.disabled = True
            await self.message.edit(view=self)

    async def send(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(self.text, view=self, embed=self.embed)
        self.message = await interaction.original_response()


class PaginatedView(DefaultView):
    def __init__(self, base_embed: discord.Embed, items_header: str, items: list[str],
                 items_per_page: int = 5, starting_page: int = 1):
        super().__init__(embed=base_embed)

        # Included data
        self.items_header = items_header
        self.items = items
        self.items_per_page = items_per_page
        self.base_embed = base_embed

        # Current state
        self.current_page = min(starting_page, math.ceil(len(self.items) / self.items_per_page))

    async def send(self, interaction):
        self.update_buttons()
        self.create_embed()
        await super().send(interaction)

    def create_embed(self):
        items_field = []
        last_item = self.current_page * self.items_per_page
        first_item = last_item - self.items_per_page
        items_to_add = self.items[first_item:last_item]
        for index, item in enumerate(items_to_add):
            items_field.append(f"{self.current_page * self.items_per_page - self.items_per_page + index+1}. {item}")
        if not items_field:
            items_field.append("\u200B")

        self.embed = copy.copy(self.base_embed)
        self.embed.add_field(
            name=self.items_header,
            value='\n'.join(items_field), inline=False)

    async def update_message(self, interaction):
        self.update_buttons()
        self.create_embed()
        await interaction.edit_original_response(embed=self.embed, view=self)

    def update_buttons(self):
        is_page_count = self.current_page >= len(self.items) / self.items_per_page
        self.first_button.disabled = self.current_page == 1
        self.back_button.disabled = self.current_page == 1
        self.forward_button.disabled = is_page_count
        self.last_button.disabled = is_page_count
        self.pages_button.label = f"Page {self.current_page} / {math.ceil(len(self.items) / self.items_per_page)}"

    @discord.ui.button(label="|<", style=discord.ButtonStyle.green)
    async def first_button(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.current_page = 1
        await self.update_message(interaction)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label=f"Page 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message(interaction)

    @discord.ui.button(label=">|", style=discord.ButtonStyle.green)
    async def last_button(self, interaction: discord.Interaction, _):
        await interaction.response.defer()
        self.current_page = math.ceil(len(self.items) / self.items_per_page)
        await self.update_message(interaction)


class EmptyPaginatedView(DefaultView):
    def __init__(self, base_embed: discord.Embed, items_header: str, text_content: str):
        super().__init__(embed=base_embed)

        # Included data
        self.items_header = items_header
        self.text_content = text_content

    async def send(self, interaction):
        self.update_buttons()
        self.create_embed()
        await super().send(interaction)

    def create_embed(self):
        self.embed = copy.copy(self.embed)
        self.embed.add_field(
            name=self.items_header,
            value=self.text_content, inline=False)

    def update_buttons(self):
        self.first_button.disabled = True
        self.back_button.disabled = True
        self.forward_button.disabled = True
        self.last_button.disabled = True
        self.pages_button.label = f"Page 1 / 1"

    @discord.ui.button(label="|<", style=discord.ButtonStyle.green)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=f"Page 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=">|", style=discord.ButtonStyle.green)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
