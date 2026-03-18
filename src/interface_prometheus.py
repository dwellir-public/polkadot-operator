#!/usr/bin/python3
"""prometheus scrape interface (provides side)."""

import hashlib
import json

from ops.framework import Object


class PrometheusProvider(Object):
    """Prometheus  provider interface."""

    def __init__(self, charm, relation_name, port, path, **job_data):
        """
        Attaches a dictionary containing job data. If you wish to overwrite
        individual fields like "honor_timestamps", you can add your own value
        for it as a keyword argument. Just make sure all keyword arguments are
        valid keys in the prometheus configuration files.
        """
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        request_id = hashlib.sha256(
            f"{self.model.uuid}:{relation_name}:{self.model.unit.name}".encode()
        ).hexdigest()
        self.job = {
            "job_name": f"{relation_name}",
            "job_data": {
                "honor_timestamps": True,
                "scrape_interval": "15s",
                "scrape_timeout": "15s",
                "metrics_path": path,
                "scheme": "http",
                "follow_redirects": True,
                "enable_http2": True,
                **job_data,
                },
            "request_id": request_id,
            "port": str(port),
        }
        # NOTE
        # request_id must be unique for every relation and unit in the current model.
        # job_name in Prometheus will become (job_name + "-" + request_id). Note the dash between those two variables that will be automatically added by the Prometheus charm.
        # Example of a resulting job_name in Prometheus: polkadot-prometheus-<request-id>

        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )

    def _on_relation_joined(self, event):
        """We use this event for passing on hostname and port and metrics_path.

        :param event:
        :return:
        """
        bind_address = getattr(
            self.model.get_binding(self._relation_name).network,
            "bind_address",
            None,
        )
        if not bind_address:
            event.defer()
            return

        self.job["job_data"]["static_configs"] = [
            {"targets": [f"{bind_address}:{self.job['port']}"]}
        ]
        event.relation.data[self.model.unit][
            f'request_{self.job["request_id"]}'
        ] = json.dumps(self.job, sort_keys=True)
