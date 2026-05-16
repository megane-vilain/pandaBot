from zoneinfo import ZoneInfo
from discord.ext import commands, tasks
from discord import app_commands
from models import GatheringItemConfig, GatheringReminder
from garlandtools import GarlandTools
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from services.gt_reminder_service import GtAlertService
from services.timezone_service import TimezoneService
from utils.et_time import convert, format_et_hours, build_reminder_text, should_notify
from utils.garland_tools import get_gathering_item
import requests
import discord
import os


def ffxiv_to_pixels(x, y, map_size=2048):

    scale = map_size / 45

    pixel_x = (x * scale) - 8.0
    pixel_y = (y * scale) + 18.0

    return int(pixel_x), int(pixel_y)


def _build_alert_text(reminder: GatheringReminder) -> str:
    et_str = format_et_hours(reminder.et_hours)
    item_label = f"{reminder.item_name}"

    lines = [
        f"### {item_label}",
        f"Spawns at **{et_str}** · Reminder **{reminder.alert_before_minutes} min** before",
    ]

    return "\n".join(lines)

class ToggleButton(discord.ui.Button["AlertsView"]):
    def __init__(self, doc_id: int, is_enabled: bool) -> None:
        super().__init__(
            label="⏸ Pause" if is_enabled else "▶ Resume",
            style=discord.ButtonStyle.secondary,# noqa
            custom_id=f"alert_toggle:{doc_id}",
        )
        self.doc_id = doc_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.gt_alert_service.toggle_reminder(self.doc_id)
        await self.view._refresh(interaction)# noqa


class RemoveButton(discord.ui.Button["AlertsView"]):
    def __init__(self, doc_id: int) -> None:
        super().__init__(
            label="🗑 Remove",
            style=discord.ButtonStyle.danger,# noqa
            custom_id=f"alert_remove:{doc_id}",
        )
        self.doc_id = doc_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.gt_alert_service.delete_reminder(self.doc_id)
        await self.view._refresh(interaction)# noqa


class AlertActionRow(discord.ui.ActionRow["AlertsView"]):
    def __init__(self, doc_id: int, is_enabled: bool) -> None:
        super().__init__(
            ToggleButton(doc_id, is_enabled),
            RemoveButton(doc_id),
        )



class AlertsView(discord.ui.LayoutView):
    def __init__(
        self,
        reminders: list,
        user: discord.User | discord.Member,
        gt_alert_service: GtAlertService,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.user = user
        self.gt_alert_service = gt_alert_service
        self._build(reminders)

    def _build(self, reminders: list) -> None:
        self.clear_items()

        if not reminders:
            self.add_item(discord.ui.TextDisplay(
                "You have no gathering alerts set up.\nUse `/notify` to create one!"
            ))
            return

        self.add_item(discord.ui.TextDisplay("## Your Gathering Alerts"))
        self.add_item(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))# noqa

        for i, reminder in enumerate(reminders):
            self.add_item(discord.ui.TextDisplay(_build_alert_text(reminder)))
            self.add_item(AlertActionRow(reminder.doc_id, reminder.enable))

            if i < len(reminders) - 1:
                self.add_item(discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large))# noqa

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("These are not your alerts.", ephemeral=True)# noqa
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction) -> None:
        updated = await self.gt_alert_service.get_user_alerts(self.user.id)
        self._build(updated)
        await interaction.response.edit_message(view=self)# noqa

class GarlandCog(commands.Cog):
    def __init__(self, bot, gt_reminder_service: GtAlertService, timezone_service: TimezoneService):
        self.bot = bot
        self.gt_reminder_service = gt_reminder_service
        self.timezone_service = timezone_service
        self.api = GarlandTools()
        self.reminder_loop.start()
        self.GATHERING_ITEMS = [
            GatheringItemConfig(item_id=43923, name="Rarefied Ash Soil", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=43932, name="Brightwind Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=46247, name="Levin Quartz", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44845, name="Alexandrian Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44135, name="Harmonite Ore", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=49212, name="Windspath Water", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=44138, name="Blackseed Cotton Boll", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=43930, name="Rarefied Windsbalm Bay Leaf", zone_map="Unlost World/Living Memory"),
            GatheringItemConfig(item_id=49210, name="Carnauba Leaf", zone_map="Yok Tural/Kozama'uka")


        ]
        self.BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    def cog_unload(self) -> None:
        self.reminder_loop.cancel()


    @tasks.loop(seconds=30)
    async def reminder_loop(self) -> None:
        alerts = self.gt_reminder_service.get_all_enabled()


        for alert in alerts:
            user_timezone = self.timezone_service.get_user_timezone(alert.user_id)
            user_zone_info = ZoneInfo(user_timezone)
            if not should_notify(alert, user_zone_info):
                continue

            channel = self.bot.get_channel(alert.channel_id)
            if channel is None:
                continue

            await channel.send(
                f"<@{alert.user_id}> ⏰ Your node is spawning soon!\n"
                f"{build_reminder_text(alert)}"
            )

            self.gt_reminder_service.update_last_notification(alert.doc_id, user_zone_info)

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()



    async def gathering_node_autocomplete(
            self, interaction: discord.Interaction, current: str):
        user_input = current.lower()

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

        await interaction.response.defer()# noqa

        selected_id = int(resource)

        gathering_item = next(
            n for n in self.GATHERING_ITEMS
            if n.id == selected_id
        )

        gathering_item = get_gathering_item(self.api, selected_id, gathering_item.map)
        gathering_node = gathering_item.node

        node_type = "Mining" if gathering_node.type == 0 or gathering_node.type == 1 else "Botany"

        user_timezone = self.timezone_service.get_user_timezone(interaction.user.id)
        next_occurrence, remaining = convert(gathering_node.time, gathering_node.node_duration, ZoneInfo(user_timezone))
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
                    ),
                ),
                discord.ui.TextDisplay(content=f"{gathering_item.description}"),
                discord.ui.TextDisplay(
                    f"**Eorzean time**: {gathering_node.time_formatted}\n"
                    f"**Next Occurrence**: {next_occurrence}\n"
                    f"**Remaining Time**: {remaining}"
                ),
                accessory=discord.ui.Thumbnail(
                    media=icon_url
                )
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
                    style=discord.ButtonStyle.secondary,# noqa
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
        await interaction.response.defer()# noqa

        selected_id = int(resource)

        gathering_item = next(
            n for n in self.GATHERING_ITEMS
            if n.id == selected_id
        )

        gathering_item = get_gathering_item(self.api, selected_id, gathering_item.map)

        gathering_item_reminder = GatheringReminder(
            user_id=interaction.user.id,
            channel_id=interaction.channel_id,
            item_id=selected_id,
            item_name=gathering_item.name,
            et_hours=gathering_item.node.time,
            duration_et_hours=gathering_item.node.node_duration,
            alert_before_minutes=5,
            enable=True,
            last_notification_ts=""
        )

        self.gt_reminder_service.create_alert(gathering_item_reminder)

        await interaction.followup.send(f"🔔 Alerts on for {gathering_item.name}")

    @app_commands.command(name="alerts")
    async def alerts(self, interaction: discord.Interaction):  # noqa
        alerts = await self.gt_reminder_service.get_user_alerts(interaction.user.id)

        async def handle_toggle(inter: discord.Interaction, doc_id: int) -> None:
            await self.gt_reminder_service.toggle_reminder(doc_id)# noqa
            updated = await self.gt_reminder_service.get_user_alerts(inter.user.id)
            new_view = AlertsView(updated, handle_toggle, handle_remove, inter.user)# noqa
            await inter.response.edit_message(view=new_view)# noqa

        async def handle_remove(inter: discord.Interaction, doc_id: int) -> None:
            await self.gt_reminder_service.delete_reminder(doc_id)
            updated = await self.gt_reminder_service.get_user_alerts(inter.user.id)
            new_view = AlertsView(updated, handle_toggle, handle_remove, inter.user)# noqa
            await inter.response.edit_message(view=new_view)# noqa

        view = AlertsView(alerts, interaction.user, self.gt_reminder_service)# noqa
        await interaction.response.send_message(view=view, ephemeral=True)# noqa