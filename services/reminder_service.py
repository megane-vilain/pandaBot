from datetime import datetime, UTC, timedelta

from tinydb import Query
from models import Reminder
from utils.db_utils import document_to_dataclass, dataclass_to_document


class ReminderService:
    def __init__(self, table):
        self.table = table
        self.query = Query()

    def get_user_reminders(self, user_id: int):
        reminders = self.table.search(self.query.user_id == user_id)
        return [document_to_dataclass(reminder, Reminder) for reminder in reminders]

    def get_due_reminders(self):
        now_date = datetime.now(UTC).isoformat()
        due_reminders = self.table.search(self.query.remind_at <= now_date)

        return [document_to_dataclass(reminder, Reminder) for reminder in due_reminders]

    def delete_reminder(self, reminder_id: int):
        self.table.remove(doc_ids=[reminder_id])

    def repeat_reminder(self, reminder_id: int):
        future_date = datetime.now(UTC) + timedelta(days=1)
        self.table.update({"remind_at": future_date.isoformat()}, doc_ids=[reminder_id])

    def create_reminder(self, reminder: Reminder):
        self.table.insert(dataclass_to_document(reminder))