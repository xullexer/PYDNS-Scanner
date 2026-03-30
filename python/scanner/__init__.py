"""Scanner package — modularised DNS scanner components.

Provides mixins, standalone classes, widgets and utility functions used by
the main ``DNSScannerTUI`` application.
"""

from .constants import (
    _copy_to_clipboard,
    _read_from_clipboard,
    logger,
    re,
)
from .widgets import (
    Checkbox,
    PlainDirectoryTree,
    StatsWidget,
    VersionedFooter,
)
from .slipstream import SlipstreamManager
from .slipnet import SlipNetManager
from .config_mixin import ConfigMixin
from .proxy_testing import ProxyTestingMixin
from .extra_tests import ExtraTestsMixin
from .results import ResultsMixin
from .isp_cache import ISPCacheMixin
from .ip_streaming import IPStreamingMixin

__all__ = [
    # Constants / platform
    "_copy_to_clipboard",
    "_read_from_clipboard",
    "logger",
    "re",
    # Widgets
    "Checkbox",
    "PlainDirectoryTree",
    "StatsWidget",
    "VersionedFooter",
    # Standalone classes
    "SlipstreamManager",
    "SlipNetManager",
    # Mixins
    "ConfigMixin",
    "ProxyTestingMixin",
    "ExtraTestsMixin",
    "ResultsMixin",
    "ISPCacheMixin",
    "IPStreamingMixin",
]
