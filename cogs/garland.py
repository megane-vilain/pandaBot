from discord.ext import commands
from discord import app_commands
from models import GatheringItemConfig
from garlandtools import GarlandTools
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from utils.et_time import convert
from utils.garland_tools import get_gathering_item
import requests
import discord
import os


def ffxiv_to_pixels(x, y, map_size=2048):

    scale = map_size / 45

    pixel_x = (x * scale) - 8.0
    pixel_y = (y * scale) + 18.0

    return int(pixel_x), int(pixel_y)

class MyView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Remind me", style=discord.ButtonStyle.secondary)# noqa
    async def remind_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(# noqa
            "Reminder registered (logic not implemented yet)",
            ephemeral=True
        )

class Garland(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = GarlandTools()
        self.GATHERING_ITEMS = [
            GatheringItemConfig(item_id=43923, name="Rarefied Ash Soil", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=43932, name="Brightwind Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=46247, name="Levin Quartz", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44845, name="Alexandrian Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44135, name="Harmonite Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=49212, name="Windspath Water", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44138, name="Blackseed Cotton Boll", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=49210, name="Carnauba Leaf", zone_map="Yok Tural/Kozama'uka")


        ]
        self.BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    async def gathering_node_autocomplete(
            self, interaction: discord.Interaction, current: str):
        user_input = current.lower()

        # if len(user_input) < 3:
        #     return [
        #         app_commands.Choice(
        #             name="Keep typing...",
        #             value="0"
        #         )
        #     ]

        results = []
        for node in self.GATHERING_ITEMS:
            if node.name_lower.startswith(user_input):
                results.append(
                    app_commands.Choice(
                        name=node.name,  # displayed to user
                        value=str(node.id)  # actual returned value
                    )
                )
                if len(results) >= 25:
                    break

        return results

    @app_commands.autocomplete(resource=gathering_node_autocomplete)
    @app_commands.command(name="gather")
    async def gather(self, interaction: discord.Interaction, resource: str):

        await interaction.response.defer()

        selected_id = int(resource)

        gathering_item = next(
            n for n in self.GATHERING_ITEMS
            if n.id == selected_id
        )

        gathering_item = get_gathering_item(self.api, selected_id, gathering_item.map)
        gathering_node = gathering_item.node

        node_type = "Mining" if gathering_node.type == 0 or gathering_node.type == 1 else "Botany"
        next_occurrence, remaining = convert(gathering_node.time, gathering_node.node_duration)
        coordinates = gathering_node.coordinates
        icon_url= f"https://www.garlandtools.org/files/icons/item/{gathering_item.icon}.png"

        map_url = "https://www.garlandtools.org/files/maps/"f"{quote(gathering_item.map)}.png"
        response = requests.get(map_url)

        map_image = Image.open(
            BytesIO(response.content)
        ).convert("RGBA")

        draw = ImageDraw.Draw(map_image)

        # -----------------------------
        # Convert coordinates
        # -----------------------------
        x, y = ffxiv_to_pixels(coordinates[0], coordinates[1])

        # -----------------------------
        # Font (safe fallback)
        # -----------------------------
        scale = 3.0
        try:
            font = ImageFont.truetype(
                os.path.join(self.BASE_DIR, "assets", "Roboto-Black.ttf"),
                int(28 * scale)
            )
        except OSError:
            print("font not found")
            font = ImageFont.load_default()

        zone_name = gathering_item.zone
        text_coord = f"{coordinates[0]},{coordinates[1]}"

        # -----------------------------
        # Text size calculation (correct font!)
        # -----------------------------
        bbox = draw.textbbox((0, 0), zone_name, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        bbox_coord = draw.textbbox((0,0), text_coord, font=font)
        text_width_coord = bbox_coord[2] - bbox_coord[0]
        text_height_coord = bbox_coord[3] - bbox_coord[1]

        img_width, img_height = map_image.size

        padding = int(10 * scale)

        box_x1 = 10
        box_y1 = 10
        box_x2 = box_x1 + text_width + padding * 2
        box_y2 = box_y1 + text_height + padding

        box_x2_coord = img_width -10
        box_y1_coord = 10
        box_x1_coord = box_x2_coord - text_width_coord - padding * 2
        box_y2_coord = box_y1_coord + text_height_coord + padding

        # -----------------------------
        # Background box (once)
        # -----------------------------
        draw.rounded_rectangle(
            (box_x1, box_y1, box_x2, box_y2),
            radius=10,
            fill=(0, 0, 0, 200)
        )

        draw.rounded_rectangle(
            (box_x1_coord, box_y1_coord, box_x2_coord, box_y2_coord),
            radius=10,
            fill=(0, 0, 0, 200)
        )

        draw.text(
            (box_x1_coord + padding, box_y1_coord),
            f"{coordinates[0]},{coordinates[1]}",
            font=font,
            fill=(255, 255, 255, 255)
        )

        # -----------------------------
        # Text
        # -----------------------------
        draw.text(
            (box_x1 + padding, box_y1),
            zone_name,
            font=font,
            fill=(255, 255, 255, 255)
        )

        # -----------------------------
        # Node marker (dot)
        # -----------------------------
        radius = 35

        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill=(255, 0, 0, 255),
            outline=(255, 255, 255, 255),
            width=10
        )

        output = BytesIO()
        map_image.thumbnail((1200, 1200))
        rgb_image = map_image.convert("RGB")
        rgb_image.save(output, format="JPEG", output=True)

        output.seek(0)

        view = discord.ui.LayoutView()

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content=(
                        f"# [{gathering_item.name}]"
                        f"(https://garlandtools.org/db/#item/{selected_id})"
                    )
                ),
                discord.ui.TextDisplay(content=f"{gathering_item.description}"),
                accessory=discord.ui.Thumbnail(
                    media=icon_url
                )
            ),
            discord.ui.TextDisplay(
                content=f"**Eorzean time**: {gathering_node.time_formatted}"
            ),
            discord.ui.TextDisplay(
                content=f"**Next Occurrence**: {next_occurrence}"
            ),
            discord.ui.TextDisplay(
                content=f"**Remaining Time**: {remaining}"
            ),
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="attachment://map.jpg"
                )
            ),
            discord.ui.ActionRow(
                discord.ui.Button(
                    label="Remind me",
                    emoji="🔔",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"reminder_{selected_id}"
                )
            ),
            accent_colour=discord.Colour.orange()
        )

        view.add_item(container)

        await interaction.followup.send(
            view=view,
            file=discord.File(output, filename="map.jpg")
        )

    @app_commands.autocomplete(resource=gathering_node_autocomplete)
    @app_commands.command(name="notify")
    async def notify(self, interaction: discord.Interaction, resource: str):
        await interaction.response.defer()
        await interaction.followup.send("test")

# This is required so the bot can load the cog
async def setup(bot):
    await bot.add_cog(Garland(bot))