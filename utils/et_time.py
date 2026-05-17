from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models import GatheringReminder

ET_MULTIPLIER = 3600 / 175

def format_et_hours(et_hours: set[int]) -> str:
    return " & ".join(f"{h} ET" for h in et_hours)

def _current_et_datetime():
    now_real_ts = datetime.now(timezone.utc).timestamp()
    current_et_ts = now_real_ts * ET_MULTIPLIER

    return datetime.fromtimestamp(
        current_et_ts,
        tz=timezone.utc
    )

def _min_spawn_gap_real(et_hours: list[int]) -> float:
    """
    Returns the smallest gap between spawns in real seconds.
    Used to detect when a new spawn window has opened.
    """
    if len(et_hours) == 1:
        # Only one spawn per ET day
        return 86400 / ET_MULTIPLIER

    gaps_et = []
    sorted_hours = sorted(et_hours)
    for i in range(len(sorted_hours)):
        next_hour = sorted_hours[(i + 1) % len(sorted_hours)]
        current_hour = sorted_hours[i]
        gap = (next_hour - current_hour) % 24
        gaps_et.append(gap * 3600)

    min_gap_et = min(gaps_et)
    return min_gap_et / ET_MULTIPLIER

def should_notify(reminder, user_timezone) -> bool:
    now_real = datetime.now(user_timezone)
    now_ts = now_real.timestamp()

    # Don't fire if we already notified within the last ET day
    # (prevents double-firing on the same spawn)
    if reminder.last_notification_ts:
        last_dt = datetime.fromisoformat(reminder.last_notification_ts)
        last_ts = last_dt.timestamp()
        et_day_in_real_seconds = 86400 / ET_MULTIPLIER
        if now_ts - last_ts < et_day_in_real_seconds:
            # Still within the same ET day — check it's a different spawn
            # by seeing if enough real time has passed for a new window
            min_gap = _min_spawn_gap_real(reminder.et_hours)
            if now_ts - last_ts < min_gap * 0.9:
                return False

    # Check if any spawn is within alert_before_minutes (real time)
    for et_hour in reminder.et_hours:
        next_spawn = _et_to_datetime(et_hour, user_timezone)
        seconds_until = (next_spawn - now_real).total_seconds()

        alert_window_real = reminder.alert_before_minutes * 60

        if 0 <= seconds_until <= alert_window_real:
            return True

    return False

def build_reminder_text(alert: GatheringReminder) -> str:
    et_str = format_et_hours(alert.et_hours)
    duration_et_minutes = _et_hours_real_minutes(alert.duration_et_hours)
    return (
        f"**{alert.item_name}** spawns at **{et_str}**\n"
        f"Window: **{alert.duration_et_hours}h ET** - Last for {format_real_minutes(duration_et_minutes)}"
    )

def _discord_timestamp(timestamp: int) -> str:
    return f"<t:{timestamp}:R>"

def _et_hours_to_real_seconds(duration_et_hours: float) -> float:
    duration_et_seconds = duration_et_hours * 3600
    return duration_et_seconds / ET_MULTIPLIER

def _et_hours_real_minutes(duration_et_hours: float) -> float:
    return _et_hours_to_real_seconds(duration_et_hours) / 60

def format_real_minutes(minutes_float: float) -> str:

    total_seconds = int(minutes_float * 60)

    minutes, seconds = divmod(
        total_seconds,
        60
    )

    return f"{minutes}min and {seconds:02}sec"

def _et_to_datetime(target_hour, user_timezone: ZoneInfo):
    now_real = datetime.now(user_timezone)
    now_real_ts = now_real.timestamp()

    current_et = _current_et_datetime()

    target_et = current_et.replace(
        hour=target_hour,
        minute=0,
        second=0,
        microsecond=0
    )

    # If already passed today, move to next ET day
    if target_et <= current_et:
        target_et = datetime.fromtimestamp(
            target_et.timestamp() + 86400,
            tz=timezone.utc
        )

    # ET delta
    et_delta_seconds = target_et.timestamp() - current_et.timestamp()

    # Convert ET delta to real delta
    real_delta_seconds = et_delta_seconds / ET_MULTIPLIER

    # Next real timestamp
    next_real_ts = now_real_ts + real_delta_seconds

    return datetime.fromtimestamp(next_real_ts,tz=user_timezone)

def _check_active(et_times: list[int], duration_et_hours: int):
    """
    Check whether any spawn window is currently active.

    Returns a tuple of (is_active, remaining_real_timedelta | None).
    """
    current_et = _current_et_datetime()
    duration_real_seconds = _et_hours_to_real_seconds(duration_et_hours)

    for hour in et_times:
        # Build the ET datetime for this spawn on the current ET day
        spawn_et = current_et.replace(
            hour=hour,
            minute=0,
            second=0,
            microsecond=0
        )

        # Also consider the spawn from the *previous* ET day,
        # in case we're inside a window that started before ET midnight
        for candidate in (spawn_et, datetime.fromtimestamp(
            spawn_et.timestamp() - 86400, tz=timezone.utc
        )):
            spawn_real_ts = candidate.timestamp() / ET_MULTIPLIER
            end_real_ts = spawn_real_ts + duration_real_seconds
            now_real_ts = datetime.now(timezone.utc).timestamp()

            if spawn_real_ts <= now_real_ts < end_real_ts:
                return True, int(end_real_ts)

    return False, None

def convert(et_times, duration_et_hours, user_timezone: ZoneInfo):
    if not isinstance(et_times, list):
        raise TypeError("et_times must be a list")
    if len(et_times) < 1 or len(et_times) > 2:
        raise ValueError("et_times must contain 1 or 2 ET hours")
    if duration_et_hours not in (2, 4):
        raise ValueError("duration_et_hours must be 2 or 4")

    is_active, end_time = _check_active(et_times, duration_et_hours)

    if is_active:
        return "Currently active", f"{_discord_timestamp(end_time)}"

    occurrences = [_et_to_datetime(hour, user_timezone) for hour in et_times]
    next_occurrence = min(occurrences)


    return (
        next_occurrence.strftime("%H:%M:%S %Z"),
        f"Spawns {_discord_timestamp(int(next_occurrence.timestamp()))}"
    )
