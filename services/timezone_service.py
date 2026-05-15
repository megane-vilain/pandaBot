from tinydb import Query
from models import Timezone
from utils.db_utils import document_to_dataclass, dataclass_to_document

TIMEZONES = [
    "Europe/London",
    "Europe/Paris"
]

class TimezoneService:
    def __init__(self, table):
        self.table = table
        self.query = Query()

    def get_user_timezone(self, user_id: int):
        record = self.table.get(self.query.user_id == user_id)
        if not record:
            return None

        timezone = document_to_dataclass(record, Timezone)
        return timezone.timezone

    def set_user_timezone(self, user_id: int, timezone_str: str):
        timezone = Timezone(user_id=user_id, timezone=timezone_str)
        self.table.upsert(
            dataclass_to_document(timezone),
            self.query.user_id == user_id
        )