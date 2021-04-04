from unittest.mock import patch

import pytest

from ...manager import get_plugins_manager
from ..plugin import VatlayerPlugin


@pytest.fixture
def vatlayer_plugin(settings, vatlayer):
    def fun(
        active=True,
        access_key="key",
        source_country=None,
        countries_to_calculate_taxes_from_source=None,
        excluded_countries=None,
    ):
        settings.PLUGINS = ["saleor.plugins.vatlayer.plugin.VatlayerPlugin"]
        manager = get_plugins_manager()
        with patch("saleor.plugins.vatlayer.plugin.fetch_rate_types"):
            manager.save_plugin_configuration(
                VatlayerPlugin.PLUGIN_ID,
                {
                    "active": active,
                    "configuration": [
                        {"name": "Access key", "value": access_key},
                        {"name": "source_country", "value": source_country},
                        {
                            "name": "countries_to_calculate_taxes_from_source",
                            "value": countries_to_calculate_taxes_from_source,
                        },
                        {"name": "excluded_countries", "value": excluded_countries},
                    ],
                },
            )
        manager = get_plugins_manager()
        return manager.plugins[0]

    return fun
