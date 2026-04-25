#!/usr/bin/python3
"""Prometheus manual jobs provider."""

import hashlib
import json
import socket

from ops.framework import Object


class PrometheusProvider(Object):
    """Publish manual scrape jobs to prometheus2."""

    def __init__(self, charm, relation_name, port, path, job_name=None, **job_data):
        """
        Configure a prometheus-manual job publisher.

        If you wish to overwrite individual fields like
        "honor_timestamps", you can add your own value for it as a keyword
        argument. Just make sure all keyword arguments are valid keys in the
        Prometheus configuration files.
        """
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self._job_name = job_name or relation_name
        self._path = path
        self._port = str(port)
        self._job_data = job_data
        self._request_id = hashlib.sha1(
            f"{self.model.uuid}:{relation_name}:{self.model.unit.name}".encode()
        ).hexdigest()[:8]

        self.framework.observe(
            charm.on[relation_name].relation_joined, self._on_relation_joined
        )

    def _on_relation_joined(self, event):
        """Publish the manual scrape job when related."""
        self.set_job(event)

    def _job(self, bind_address):
        """Build the manual scrape job payload."""
        job_name_prefix = "-".join(
            part
            for part in (
                self.model.name,
                self.model.app.name,
                self.model.unit.name.replace("/", "-"),
                self._job_name,
            )
            if part
        )
        labels = {
            "juju_model": self.model.name,
            "juju_model_uuid": self.model.uuid,
            "juju_application": self.model.app.name,
            "juju_unit": self.model.unit.name,
            "hostname": socket.gethostname(),
        }

        # prometheus2 strips the last five dash-delimited segments when
        # deduplicating manual jobs, so keep the meaningful identifier before
        # this short suffix.
        dedupe_suffix = "x-x-x-x"
        return {
            "job_name": f"{job_name_prefix}-{dedupe_suffix}",
            "job_data": {
                "honor_timestamps": True,
                "scrape_interval": "15s",
                "scrape_timeout": "15s",
                "metrics_path": self._path,
                "scheme": "http",
                "follow_redirects": True,
                "enable_http2": True,
                "static_configs": [
                    {
                        "targets": [f"{bind_address}:{self._port}"],
                        "labels": labels,
                    }
                ],
                **self._job_data,
            },
            "request_id": self._request_id,
            "port": self._port,
        }

    def set_job(self, event=None):
        """Publish the current scrape job to all related consumers."""
        bind_address = getattr(
            self.model.get_binding(self._relation_name).network,
            "bind_address",
            None,
        )
        if not bind_address:
            if event:
                event.defer()
            return

        job = json.dumps(self._job(str(bind_address)), sort_keys=True)
        for relation in self.model.relations[self._relation_name]:
            relation.data[self.model.unit][f"request_{self._request_id}"] = job
