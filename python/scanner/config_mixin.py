"""Configuration loading / saving mixin."""

from __future__ import annotations

import json
from pathlib import Path

from .constants import logger


class ConfigMixin:
    """Mixin that adds config persistence to DNSScannerTUI."""

    # Attributes expected on *self* (set by DNSScannerTUI.__init__):
    #   config_dir: Path
    #   config_file: Path

    def _load_config(self) -> dict:
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"Config file corrupted or invalid, ignoring: {e}")
        except (OSError, IOError) as e:
            logger.debug(f"Failed to read config file: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error loading config: {e}")
        return {}

    def _save_config(self, config: dict) -> None:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except (OSError, IOError) as e:
            logger.debug(f"Failed to save config (permission/IO error): {e}")
        except Exception as e:
            logger.warning(f"Unexpected error saving config: {e}")
