from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET_MULTIPLIER = 3600 / 175

LOCAL_TZ = ZoneInfo("Europe/Paris")



def _format_remaining(delta):
    total_seconds = int(delta.total_seconds())

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"


def _current_et_datetime():
    now_real_ts = datetime.now(timezone.utc).timestamp()
    current_et_ts = now_real_ts * ET_MULTIPLIER

    return datetime.fromtimestamp(
        current_et_ts,
        tz=timezone.utc
    )

def _discord_timestamp(timestamp: int) -> str:
    return f"<t:{timestamp}:R>"

def _et_hours_to_real_seconds(et_seconds: float) -> float:
    return et_seconds / ET_MULTIPLIER

def _et_to_local(target_hour):
    now_real = datetime.now(timezone.utc)
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

    return datetime.fromtimestamp(next_real_ts,tz=LOCAL_TZ)

def _check_active(et_times: list[int], duration_et_hours: int):
    """
    Check whether any spawn window is currently active.

    Returns a tuple of (is_active, remaining_real_timedelta | None).
    """
    current_et = _current_et_datetime()
    duration_et_seconds = duration_et_hours * 3600
    duration_real_seconds = _et_hours_to_real_seconds(duration_et_seconds)

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

def convert(et_times, duration_et_hours):
    """
    Convert ET spawn times to the next local occurrence,
    or report if the node is currently active.

    Args:
        et_times (list[int]):
            One or two ET hours. Example: [0] or [0, 12]
        duration_et_hours (int):
            How long the node stays active in ET hours (2 or 4).

    Returns:
        If active:
            ("active", remaining_formatted: str)
            e.g. ("active", "01:23:45")
        If not active:
            (formatted_local_datetime: str, discord_timestamp: str)
            e.g. ("18:42:00 CEST", "<t:1234567890:R>")
    """

    if not isinstance(et_times, list):
        raise TypeError("et_times must be a list")
    if len(et_times) < 1 or len(et_times) > 2:
        raise ValueError("et_times must contain 1 or 2 ET hours")
    if duration_et_hours not in (2, 4):
        raise ValueError("duration_et_hours must be 2 or 4")

    is_active, end_time = _check_active(et_times, duration_et_hours)

    if is_active:
        return "Currently active", f"End {_discord_timestamp(end_time)}"

    occurrences = [_et_to_local(hour) for hour in et_times]
    next_occurrence = min(occurrences)


    return (
        next_occurrence.strftime("%H:%M:%S %Z"),
        f"Available {_discord_timestamp(int(next_occurrence.timestamp()))}"
    )
