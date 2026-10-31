from __future__ import annotations

from ..config import ProviderConfig
from .base import PriceProvider, ProviderError


def create_provider(cfg: ProviderConfig) -> PriceProvider:
    if cfg.type == "mkm_api":
        from .mkm_api import MkmApiProvider

        assert cfg.mkm_api is not None
        return MkmApiProvider(cfg.mkm_api)
    if cfg.type == "scraper":
        from .scraper import ScraperProvider

        return ScraperProvider(cfg.scraper)
    from .demo import DemoProvider

    return DemoProvider(cfg.demo)


__all__ = ["PriceProvider", "ProviderError", "create_provider"]
