from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from dateutil import tz


@dataclass(frozen=True, slots=True)
class RegionTimeConfig:
    region: str
    tz_name: str
    description: str

    @property
    def zone(self) -> tz.tzinfo:
        return tz.gettz(self.tz_name)


REGION_TIMEZONES: Dict[str, RegionTimeConfig] = {
    "US": RegionTimeConfig("US", "America/Chicago", "Central Time (CST/CDT)"),
    "CA": RegionTimeConfig("CA", "America/Regina", "Central Standard Time (no DST)"),
    "UK": RegionTimeConfig("UK", "Europe/London", "United Kingdom local time (GMT/BST)"),
    "AU": RegionTimeConfig("AU", "Australia/Sydney", "Australian Eastern Daylight Time"),
}


def to_local_date(timestamp_utc: datetime, region: str) -> datetime.date:
    """Convert a UTC timestamp to the local-date for the given region."""
    config = REGION_TIMEZONES.get(region)
    if not config:
        raise KeyError(f"Unsupported region '{region}'. Known regions: {list(REGION_TIMEZONES)}")

    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=tz.UTC)

    localized = timestamp_utc.astimezone(config.zone)
    return localized.date()


def to_local_datetime(timestamp_utc: datetime, region: str) -> datetime:
    """Convert a UTC timestamp to a timezone-aware local datetime for the region."""
    config = REGION_TIMEZONES.get(region)
    if not config:
        raise KeyError(f"Unsupported region '{region}'. Known regions: {list(REGION_TIMEZONES)}")

    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=tz.UTC)

    return timestamp_utc.astimezone(config.zone)
