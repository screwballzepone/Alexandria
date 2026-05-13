"""Utility helper functions for the application."""

from datetime import datetime

# Time constants (in seconds)
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400
SECONDS_PER_WEEK = 604800
# Approximate values for months and years
SECONDS_PER_MONTH = 2592000  # 30 days
SECONDS_PER_YEAR = 31536000  # 365 days


def format_timestamp(dt: datetime) -> str:
    """
    Convert a datetime object to a human-readable time difference string.

    Args:
        dt: A datetime object representing the time to format.

    Returns:
        A string representing the time difference from now, such as:
        "just now", "X seconds ago", "X minutes ago", etc.

    Notes:
        - Month calculations use an approximate value of 30 days.
        - Year calculations use an approximate value of 365 days.
        - Future dates return "in the future".
        - For naive datetime objects (without timezone info), the local
          system time is used as the reference.
        - For timezone-aware datetime objects, the original datetime's
          timezone is respected when calculating the difference.
    """
    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime.datetime instance, got {type(dt).__name__}")

    # Handle timezone-aware and naive datetime objects
    if dt.tzinfo is not None:
        now = datetime.now(dt.tzinfo)
    else:
        now = datetime.now()
    diff = now - dt

    # Handle future dates
    if diff.total_seconds() < 0:
        return "in the future"

    seconds = int(diff.total_seconds())

    if seconds < 5:
        return "just now"
    elif seconds < SECONDS_PER_MINUTE:
        return f"{seconds} seconds ago"
    elif seconds < SECONDS_PER_MINUTE * 2:
        return "1 minute ago"
    elif seconds < SECONDS_PER_HOUR:
        minutes = seconds // SECONDS_PER_MINUTE
        return f"{minutes} minutes ago"
    elif seconds < SECONDS_PER_HOUR * 2:
        return "1 hour ago"
    elif seconds < SECONDS_PER_DAY:
        hours = seconds // SECONDS_PER_HOUR
        return f"{hours} hours ago"
    elif seconds < SECONDS_PER_DAY * 2:
        return "1 day ago"
    elif seconds < SECONDS_PER_WEEK:
        days = seconds // SECONDS_PER_DAY
        return f"{days} days ago"
    elif seconds < SECONDS_PER_WEEK * 2:
        return "1 week ago"
    elif seconds < SECONDS_PER_MONTH:
        weeks = seconds // SECONDS_PER_WEEK
        return f"{weeks} weeks ago"
    elif seconds < SECONDS_PER_MONTH * 2:
        return "1 month ago"
    elif seconds < SECONDS_PER_YEAR:
        months = seconds // SECONDS_PER_MONTH
        return f"{months} months ago"
    elif seconds < SECONDS_PER_YEAR * 2:
        return "1 year ago"
    else:
        years = seconds // SECONDS_PER_YEAR
        return f"{years} years ago"
