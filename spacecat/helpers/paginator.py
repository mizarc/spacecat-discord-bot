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
        self.current_page = 1

    async def send(self, ctx):
        self.message = await ctx.send(view=self)

    async def create_embed(self, data):
        embed = discord.Embed(title="Example")

        items_field = []
        for index, item in enumerate(data):
            items_field.append(f"{self.current_page * index}. {item}")

        embed.add_field(
            name=self.items_header,
            value=items_field, inline=False)

    async def update_message(self, data):
        await self.message.edit(embed=self.create_embed(data), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def forward_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page += 1
        last_item = self.current_page * self.items_per_page
        first_item = last_item - self.items_per_page
        await self.update_message(self.items[first_item:last_item])

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_page -= 1
        last_item = self.current_page * self.items_per_page
        first_item = last_item - self.items_per_page
        await self.update_message(self.items[first_item:last_item])

