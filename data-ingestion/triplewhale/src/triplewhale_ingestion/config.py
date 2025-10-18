from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    """Runtime configuration for the growth reporting pipeline."""

    triple_whale_api_key: str
    triple_whale_workspace_id: Optional[str] = None
    triple_whale_account_id: Optional[str] = None
    triple_whale_api_base: str = "https://api.triplewhale.com/api/v2"
    triple_whale_shop_domain: Optional[str] = None
    triple_whale_account_region_map: Dict[str, str] | None = None
    http_timeout: int = 30
    default_start_date: Optional[date] = None
    default_end_date: Optional[date] = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables."""

        api_key = os.getenv("TRIPLE_WHALE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TRIPLE_WHALE_API_KEY is required but was not found in the environment."
            )

        workspace_id = os.getenv("TRIPLE_WHALE_WORKSPACE_ID")
        account_id = os.getenv("TRIPLE_WHALE_ACCOUNT_ID")
        api_base = os.getenv("TRIPLE_WHALE_API_BASE", "https://api.triplewhale.com/api/v2")
        timeout = int(os.getenv("HTTP_TIMEOUT", "30"))
        shop_domain = (
            os.getenv("TRIPLE_WHALE_SHOP_DOMAIN")
            or os.getenv("SHOP_DOMAIN")
            or os.getenv("SHOPIFY_DOMAIN")
        )
        account_region_map = None
        account_region_env = os.getenv("TRIPLE_WHALE_ACCOUNT_REGION_MAP")
        if account_region_env:
            try:
                import json

                account_region_map = json.loads(account_region_env)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "TRIPLE_WHALE_ACCOUNT_REGION_MAP must be valid JSON"
                ) from exc

        start_date_env = os.getenv("DEFAULT_START_DATE")
        end_date_env = os.getenv("DEFAULT_END_DATE")
        start_date = date.fromisoformat(start_date_env) if start_date_env else None
        end_date = date.fromisoformat(end_date_env) if end_date_env else None

        return cls(
            triple_whale_api_key=api_key,
            triple_whale_workspace_id=workspace_id,
            triple_whale_account_id=account_id,
            triple_whale_api_base=api_base.rstrip("/"),
            triple_whale_shop_domain=shop_domain,
            triple_whale_account_region_map=account_region_map or {},
            http_timeout=timeout,
            default_start_date=start_date,
            default_end_date=end_date,
        )
