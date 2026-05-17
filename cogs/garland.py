from zoneinfo import ZoneInfo
from discord.ext import commands, tasks
from discord import app_commands
from models import GatheringReminder, GatheringItem
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from services.gt_reminder_service import GtAlertService
from services.timezone_service import TimezoneService
from utils.et_time import convert, format_et_hours, should_notify
from utils.garland_tools import load_gathering_items
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

class RemoveButton(discord.ui.Button):
    def __init__(self, doc_id: int) -> None:
        super().__init__(
            label="🗑 Remove",
            style=discord.ButtonStyle.danger,# noqa
            custom_id=f"alert_remove:{doc_id}",
        )
        self.doc_id = doc_id

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.gathering_item.alert = await self.view.gt_alert_service.delete_reminder(self.doc_id)
        await self.view._refresh(interaction)# noqa

class NotifyButton(discord.ui.Button):
    def __init__(self, item_id: int) -> None:
        super().__init__(
            label="🔔 Notify",
            style=discord.ButtonStyle.secondary,# noqa
            custom_id=f"alert_add:{item_id}",
        )
        self.doc_id = item_id

    async def callback(self, interaction: discord.Interaction) -> None:
        gathering_item_reminder = GatheringReminder(
            user_id=interaction.user.id,
            channel_id=interaction.channel_id,
            item_id=self.view.gathering_item.id,
            item_name=self.view.gathering_item.name,
            et_hours=self.view.gathering_item.node.time,
            duration_et_hours=self.view.gathering_item.node.node_duration,
            alert_before_minutes=5,
            enable=True,
            last_notification_ts=""
        )

        self.view.gathering_item.alert = self.view.gt_alert_service.create_alert(gathering_item_reminder)
        await self.view._refresh(interaction)# noqa

class AlertActionRow(discord.ui.ActionRow["AlertsView"]):
    def __init__(self, doc_id: int, is_enabled: bool) -> None:
        super().__init__(
            ToggleButton(doc_id, is_enabled),
            RemoveButton(doc_id),
        )

class ReminderView(discord.ui.LayoutView):
    def __init__(
            self,
            user_id: int,
            user_timezone: str,
            gathering_item: GatheringItem,
            gt_alert_service: GtAlertService,
            alert_mode: bool,
            timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.gathering_item = gathering_item
        self.user_timezone = user_timezone
        self.gt_alert_service = gt_alert_service
        self.alert_mode = alert_mode
        self._build(gathering_item, user_id, user_timezone, alert_mode)

    def _build(
            self,
            gathering_item: GatheringItem,
            user_id,
            user_timezone,
            alert_mode) -> None:
        self.clear_items()

        icon_url = f"https://www.garlandtools.org/files/icons/item/{gathering_item.icon_id}.png"
        gathering_node = gathering_item.node
        alert = gathering_item.alert
        next_occurrence, remaining = convert(gathering_node.time, gathering_node.node_duration, ZoneInfo(user_timezone))

        if next_occurrence == "Currently active":
            spawn_text = f"**Status**: 🟢 Active — closes in {remaining}"
        else:
            spawn_text = (
                f"**Next Occurrence**: {next_occurrence} ({remaining})\n"
            )

        title_section = discord.ui.Section(
            accessory=discord.ui.Thumbnail(
                media=icon_url
            )
        )
        title_section.add_item(
            discord.ui.TextDisplay(
                content=(f"# [{gathering_item.name}]"
                            f"(https://garlandtools.org/db/#item/{gathering_item.id})")
            )
        )
        if not alert_mode:
            title_section.add_item(
                discord.ui.TextDisplay(content=f"{gathering_item.description}")
            )

        title_section.add_item(
            discord.ui.TextDisplay(spawn_text)
        )

        if alert_mode:
            title_section.add_item(
                discord.ui.TextDisplay(
                    content=f"<@{user_id}> ⏰ Your node is spawning soon!"
                )
            )

        container = discord.ui.Container(
            title_section,
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="attachment://map.jpg"
                )
            ),
            accent_colour=discord.Colour.orange()
        )
        action_row = discord.ui.ActionRow()

        if alert:
            action_row.add_item(
                ToggleButton(alert.doc_id, alert.enable)
            )
            action_row.add_item(
                RemoveButton(alert.doc_id)
            )
        else:
            action_row.add_item(
                NotifyButton(gathering_item.id)
            )

        container.add_item(action_row)

        self.add_item(container)

    async def _refresh(self, interaction: discord.Interaction) -> None:
        alert = self.gt_alert_service.get_item_alert_for_user(self.user_id, self.gathering_item.id)
        self.gathering_item.alert = alert
        self._build(self.gathering_item, self.user_id, self.user_timezone, self.alert_mode)
        await interaction.response.edit_message(view=self)# noqa

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
        self.reminder_loop.start()
        self.gathering_items, self.gathering_items_by_id = load_gathering_items()
        self.BASE_DIR = os.path.dirname(os.path.dirname(__file__))

    def cog_unload(self) -> None:
        self.reminder_loop.cancel()


    async def gathering_node_autocomplete(
            self, interaction: discord.Interaction, current: str):
        user_input = current.lower()

        results = []
        for node in self.gathering_items:
            if user_input in node.name_lower:
                results.append(
                    app_commands.Choice(
                        name=node.name,  # displayed to user
                        value=str(node.id)  # actual returned value
                    )
                )
                if len(results) >= 25:
                    break

        return results


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

            gathering_item = self.gathering_items_by_id[alert.item_id]
            gathering_item.alert = alert

            map_output = await self.get_zone_map(gathering_item)
            view = ReminderView(alert.user_id, user_timezone, gathering_item, self.gt_reminder_service, True)  # noqa

            await channel.send(
                view=view,
                file=discord.File(map_output, filename="map.jpg")
            )

            self.gt_reminder_service.update_last_notification(alert.doc_id, user_zone_info)

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.autocomplete(resource=gathering_node_autocomplete)
    @app_commands.command(name="gather", description="Give information on a resource")
    async def gather(self, interaction: discord.Interaction, resource: str):

        await interaction.response.defer()# noqa

        selected_id = int(resource)
        gathering_item = self.gathering_items_by_id[selected_id]
        gathering_item.alert =  self.gt_reminder_service.get_item_alert_for_user(interaction.user.id, selected_id)
        user_timezone = self.timezone_service.get_user_timezone(interaction.user.id)

        map_output = await self.get_zone_map(gathering_item)
        view = ReminderView(interaction.user.id, user_timezone, gathering_item, self.gt_reminder_service, False)  # noqa

        await interaction.followup.send(
            view=view,
            file=discord.File(map_output, filename="map.jpg")
        )

    async def get_zone_map(self, gathering_item: GatheringItem) -> BytesIO:
        gathering_node = gathering_item.node
        coordinates = gathering_node.coordinates
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

        bbox_coord = draw.textbbox((0, 0), text_coord, font=font)
        text_width_coord = bbox_coord[2] - bbox_coord[0]
        text_height_coord = bbox_coord[3] - bbox_coord[1]

        img_width, img_height = map_image.size

        padding = int(10 * scale)

        box_x1 = 10
        box_y1 = 10
        box_x2 = box_x1 + text_width + padding * 2
        box_y2 = box_y1 + text_height + padding

        box_x2_coord = img_width - 10
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
        return output

    @app_commands.autocomplete(resource=gathering_node_autocomplete)
    @app_commands.command(name="notify", description="Enable or disable notification for a resource")
    async def notify(self, interaction: discord.Interaction, resource: str):
        await interaction.response.defer()# noqa

        selected_id = int(resource)

        gathering_item = self.gathering_items_by_id[selected_id]

        gathering_item = self.gathering_items_by_id[selected_id]

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

        reminder = self.gt_reminder_service.get_item_alert_for_user(interaction.user.id,selected_id)
        if reminder:
            await self.gt_reminder_service.delete_reminder(reminder.doc_id)
            await interaction.followup.send(f":no_bell:  Alerts off for {gathering_item.name}")
        else:
            self.gt_reminder_service.create_alert(gathering_item_reminder)
            await interaction.followup.send(f"🔔 Alerts on for {gathering_item.name}")

    @app_commands.command(name="alerts", description="List all alerts")
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