from collections.abc import Iterator

from more_itertools import map_reduce
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily

from ion_exporter.logger import logger
from ion_client.client import Client


class Collector:
    def __init__(
        self,
        username: str,
        password: str,
        otp: str | None,
    ):
        self.client = Client(
            username=username, password=password, otp=otp, api_version=10
        )

    def json(self, path: str) -> dict:
        return self.client.json(path).get("elements", [])

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
                radios = device.get("radios") or []
                for radio in radios:
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
