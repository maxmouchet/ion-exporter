from collections.abc import Iterator
from typing import cast

import httpx
from more_itertools import map_reduce
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily

from ion_exporter.logger import logger
from ion_exporter.sso import SSOClient


class Collector:
    DEFAULT_BASE_URL = "https://nb.portal.arubainstanton.com/api"

    def __init__(
        self,
        username: str,
        password: str,
        otp: str | None,
        base_url: str = DEFAULT_BASE_URL,
        sso: SSOClient | None = None,
    ):
        self.username = username
        self.password = password
        self.otp = otp
        if not sso:
            sso = SSOClient()
        self.sso = sso
        self.client = httpx.Client(base_url=base_url)
        self.access_token = None
        self.refresh_token = None

    def reauthenticate(self) -> None:
        try:
            logger.info("Refreshing token...")
            tokens = self.sso.refresh_token(cast(str, self.refresh_token))
            self.access_token = tokens["access_token"]
        except httpx.HTTPStatusError:
            logger.info("Refresh failed, re-authenticating...")
            tokens = self.sso.fetch_tokens(self.username, self.password, self.otp)
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]

    def json(self, path: str) -> dict:
        logger.info("Fetching %s...", path)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-ION-API-VERSION": "10",
        }
        res = self.client.get(path, headers=headers)
        try:
            res.raise_for_status()
        except httpx.HTTPStatusError:
            self.reauthenticate()
            headers["Authorization"] = f"Bearer {self.access_token}"
            res = self.client.get(path, headers=headers)
            res.raise_for_status()
        data = res.json()
        return cast(dict, data["elements"])

    def collect(self) -> Iterator[CounterMetricFamily | GaugeMetricFamily]:
        logger.info("Starting collection")
        metrics = []
        sites = self.json("/sites")
        for site in sites:
            site_labels = {"site_id": site["id"]}
            metrics += [
                (
                    "site_meta",
                    1,
                    site_labels | {"site_name": site["name"]},
                )
            ]
            clients = self.json(f"/sites/{site['id']}/clientSummary")
            for client in clients:
                client_labels = site_labels | {
                    "client_id": client["id"],
                    "radio_id": client["radioId"],
                }
                metrics += [
                    (
                        "client_meta",
                        1,
                        client_labels
                        | {
                            "client_name": client["name"],
                            "client_ip": client["ipAddress"],
                            "client_protocol": client["wirelessProtocol"],
                            "client_security": client["wirelessSecurity"],
                        },
                    ),
                    (
                        "client_connection_duration_seconds_total",
                        client.get("connectionDurationInSeconds"),
                        client_labels,
                    ),
                    (
                        "client_downstream_data_transferred_bytes_24h",
                        client.get("downstreamDataTransferredInBytes"),
                        client_labels,
                    ),
                    (
                        "client_downstream_retry_percent",
                        client.get("downstreamRetryPercent"),
                        client_labels,
                    ),
                    (
                        "client_downstream_speed_mbps",
                        client.get("downstreamSpeedInMegabitsPerSecond"),
                        client_labels,
                    ),
                    (
                        "client_downstream_throughput_bps",
                        client.get("downstreamThroughputInBitsPerSecond"),
                        client_labels,
                    ),
                    (
                        "client_health_percent",
                        client.get("healthInPercent"),
                        client_labels,
                    ),
                    (
                        "client_noise_dbm",
                        client.get("noiseInDbm"),
                        client_labels,
                    ),
                    (
                        "client_signal_dbm",
                        client.get("signalInDbm"),
                        client_labels,
                    ),
                    (
                        "client_snr_db",
                        client.get("snrInDb"),
                        client_labels,
                    ),
                    (
                        "client_upstream_data_transferred_bytes_24h",
                        client.get("upstreamDataTransferredInBytes"),
                        client_labels,
                    ),
                    (
                        "client_upstream_retry_percent",
                        client.get("upstreamRetryPercent"),
                        client_labels,
                    ),
                    (
                        "client_upstream_speed_mbps",
                        client.get("upstreamSpeedInMegabitsPerSecond"),
                        client_labels,
                    ),
                    (
                        "client_upstream_throughput_bps",
                        client.get("upstreamThroughputInBitsPerSecond"),
                        client_labels,
                    ),
                ]
            devices = self.json(f"/sites/{site['id']}/inventory")
            for device in devices:
                device_labels = {"site_id": site["id"], "device_id": device["id"]}
                metrics += [
                    (
                        "device_meta",
                        1,
                        device_labels
                        | {
                            "device_name": device["name"],
                            "device_model": device["model"],
                            "device_version": device["currentFirmwareVersion"],
                        },
                    ),
                    (
                        "device_uptime_seconds_total",
                        device.get("uptimeInSeconds"),
                        device_labels,
                    ),
                ]
                for port in device["ethernetPorts"]:
                    port_labels = device_labels | {"port_id": str(port["portNumber"])}
                    metrics += [
                        (
                            "ethernet_downstream_data_transferred_bytes_total",
                            port.get("downstreamDataTransferredInBytes"),
                            port_labels,
                        ),
                        (
                            "ethernet_downstream_throughput_bps",
                            port.get("downstreamThroughputInBitsPerSecond"),
                            port_labels,
                        ),
                        (
                            "ethernet_upstream_data_transferred_bytes_total",
                            port.get("upstreamDataTransferredInBytes"),
                            port_labels,
                        ),
                        (
                            "ethernet_upstream_throughput_bps",
                            port.get("upstreamThroughputInBitsPerSecond"),
                            port_labels,
                        ),
                    ]
                for radio in (device.get("radios") or []):
                    radio_labels = device_labels | {"radio_id": radio["id"]}
                    metrics += [
                        (
                            "radio_meta",
                            1,
                            radio_labels | {"radio_band": radio["band"]},
                        ),
                        (
                            "radio_regulatory_max_tx_power_eirp_dbm",
                            radio.get("regulatoryMaxTxPowerEirpInDbm"),
                            radio_labels,
                        ),
                        (
                            "radio_tx_power_eirp_dbm",
                            radio.get("txPowerEirpInDbm"),
                            radio_labels,
                        ),
                        (
                            "radio_utilization_percent",
                            radio.get("utilizationPercent"),
                            radio_labels,
                        ),
                        (
                            "radio_wireless_clients_count",
                            radio.get("wirelessClientsCount"),
                            radio_labels,
                        ),
                    ]
        metrics_by_name = map_reduce(metrics, lambda x: x[0])
        for name, values in metrics_by_name.items():
            cls = CounterMetricFamily if name.endswith("_total") else GaugeMetricFamily
            label_names = list(values[0][2].keys())
            family = cls(name=name, documentation=name, labels=label_names)
            for _, value, labels in values:
                if value:
                    family.add_metric(list(labels.values()), value)
            yield family
        logger.info("Finishing collection")
