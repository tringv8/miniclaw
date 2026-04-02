from __future__ import annotations

import ipaddress
from typing import Iterable


def client_allowed(client_host: str | None, allowed_cidrs: Iterable[str]) -> bool:
    cidrs = [cidr for cidr in allowed_cidrs if cidr]
    if not cidrs:
        return True
    if not client_host:
        return False

    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False

    for cidr in cidrs:
        try:
            if client_ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False
