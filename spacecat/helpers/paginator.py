import copy
import math

import discord.ui


class PaginatedView(discord.ui.View):
    def __init__(self, base_embed: discord.Embed, items_header: str, items: list[str], items_per_page: int = 5):
        super().__init__()
        # Included data
        self.base_embed = base_embed
        self.items_header = items_header
        self.items = items
        self.items_per_page = items_per_page

        # Current state
        self.message = None
        self.current_embed = None
        self.current_page = 1

        self.create_embed()

    async def send(self, interaction):
        self.update_buttons()
        self.message = await interaction.response.send_message(embed=self.current_embed, view=self)

    def create_embed(self):
        items_field = []
        last_item = self.current_page * self.items_per_page
        first_item = last_item - self.items_per_page
        items_to_add = self.items[first_item:last_item]
        for index, item in enumerate(items_to_add):
            items_field.append(f"{self.current_page * self.items_per_page - self.items_per_page + index+1}. {item}")

        self.current_embed = copy.copy(self.base_embed)
        self.current_embed.add_field(
            name=self.items_header,
            value='\n'.join(items_field), inline=False)

    async def update_message(self, interaction):
        self.update_buttons()
        self.create_embed()
        await interaction.edit_original_response(embed=self.current_embed, view=self)

    def update_buttons(self):
        if self.current_page == 1:
            self.back_button.disabled = True

        if self.current_page > len(self.items) / self.items_per_page:
            self.forward_button.disabled = True

        self.pages_button.label = f"Page {self.current_page} / {math.ceil(len(self.items) / self.items_per_page)}"

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label=f"Page 1/1", style=discord.ButtonStyle.gray, disabled=True)
    async def pages_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message(interaction)

