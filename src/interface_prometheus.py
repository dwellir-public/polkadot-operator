#!/usr/bin/python3
"""prometheus scrape interface (provides side)."""

from ops.framework import Object
import json
import socket
from uuid import uuid4

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
        uuid = str(uuid4())
        self.job = {
            "job_name": f"{socket.gethostname()}-{relation_name}",
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
            "request_id": uuid,
            "port": str(port),
        }
        # NOTE
        # request_id must be unique for every relation and unit in the current model, hence the use of UUID.
        # job_name in Prometheus will become (job_name + "-" + request_id). Note the dash between those two variables that will be automatically added by the Prometheus charm.
        # Example of a resulting job_name in Prometheus: juju-a4c6ea-0-node-prometheus-14242306-4fd0-49aa-b979-7d94c7fd680c
        
        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )

    def _on_relation_joined(self, event):
        """We use this event for passing on hostname and port and metrics_path.

        :param event:
        :return:
        """
        ingress_address = event.relation.data.get(self.model.unit)['ingress-address']
        if "static_configs" not in self.job["job_data"]:
            self.job["job_data"]["static_configs"] = [{"targets": [f"{ingress_address}:{self.job['port']}"]}]
        event.relation.data[self.model.unit][f'request_{self.job["request_id"]}'] = json.dumps(self.job, sort_keys=True)
