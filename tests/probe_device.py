#!/usr/bin/env python3
"""Probe all known Climate Connect API endpoints for a device.

Dumps the raw JSON response of every known endpoint so support for new
boiler types (e.g. GRB Smartboilers) can be mapped out. Run:

    python3 probe_device.py <serial_number> <access_token> [output.json]

Get the access token the same way as for the integration setup (the JWT
starting with "eyJ" from the Climate Connect login flow). Only GET
endpoints are called; nothing on the boiler is changed.
"""
import json
import sys
from datetime import datetime, timedelta

import requests

API_BASE_URL = "https://wifi-api.id-c.net/api"
TIMEOUT = 120  # the API is very slow (~16s per call)

# All known GET endpoints. Format: (endpoint, extra_params)
ENDPOINTS = [
    ("GetEanCode", {}),
    ("GetDeviceStatus", {}),
    ("GetDeviceMode", {}),
    ("GetDevicePVSettings", {}),
    ("GetSmartGridStatus", {}),
    ("GetFault", {}),
    ("GetFaultHistory", {}),
]


def probe(serial_number: str, token: str) -> dict:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )

    results = {
        "serial_number": serial_number,
        "probed_at": datetime.now().isoformat(),
        "endpoints": {},
    }

    calls = list(ENDPOINTS)

    # GetEnergyConsumption needs a date range
    now = datetime.now()
    calls.append(
        (
            "GetEnergyConsumption",
            {
                "startDate": int((now - timedelta(days=7)).timestamp() * 1000),
                "endDate": int(now.timestamp() * 1000),
                "interval": "Day",
                "includePreviousPeriod": False,
                "refreshCache": False,
            },
        )
    )

    for endpoint, extra_params in calls:
        params = {"serialNumber": serial_number, **extra_params}
        print(f"→ {endpoint} ...", end=" ", flush=True)
        try:
            response = session.get(
                f"{API_BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT
            )
            print(f"HTTP {response.status_code}")
            try:
                body = response.json()
            except ValueError:
                body = response.text[:1000]
            results["endpoints"][endpoint] = {
                "status": response.status_code,
                "response": body,
            }
        except requests.RequestException as err:
            print(f"error: {err}")
            results["endpoints"][endpoint] = {"error": str(err)}

    return results


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    serial_number = sys.argv[1].strip().upper()
    token = sys.argv[2].strip()
    output = sys.argv[3] if len(sys.argv) > 3 else f"probe_{serial_number}.json"

    results = probe(serial_number, token)

    with open(output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults written to {output}")
    print("Note: the file contains no credentials, safe to share in an issue.")


if __name__ == "__main__":
    main()
