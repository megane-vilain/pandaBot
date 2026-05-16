from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tinydb import Query, where

from models import GatheringReminder
from utils.db_utils import dataclass_to_document, document_to_dataclass


class GtAlertService:
    def __init__(self, table):
        self.table = table
        self.query = Query()

    async def get_user_alerts(self, user_id: int):
        alerts = self.table.search(self.query.user_id == user_id)
        return [document_to_dataclass(alert, GatheringReminder) for alert in alerts]

    def get_all_enabled(self) -> list[GatheringReminder]:
        alerts = self.table.search(where("enable") == True)
        return [document_to_dataclass(alert, GatheringReminder) for alert in alerts]
    def update_last_notification(self, doc_id: int, user_zone_info: ZoneInfo) -> None:
        now_ts = str(datetime.now(user_zone_info).isoformat())
        self.table.update({"last_notification_ts": now_ts}, doc_ids=[doc_id])

    def create_alert(self, reminder: GatheringReminder):
        self.table.insert(dataclass_to_document(reminder))

    async def toggle_reminder(self, doc_id:int):
        reminder = self.table.get(doc_id=doc_id)
        if reminder is None:
            return
        self.table.update({"enable": not reminder["enable"]}, doc_ids=[doc_id])

    async def delete_reminder(self, reminder_id: int):
        self.table.remove(doc_ids=[reminder_id])