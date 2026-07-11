"""Offline comparison of WorkflowX's packaged contracts with GemMobi.

Usage:
    python remote_image_api/validate_contract_drift.py [canonical_models.json]

The GemMobi checkout is optional and is never imported by node runtime code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_GEMMOBI = Path.home() / "Desktop" / "GemMobi" / "docs" / "model_contracts" / "canonical_models.json"


def relevant(source: dict) -> dict:
    providers = {}
    for provider in ("kie", "atlas"):
        data = json.loads(json.dumps(source["providers"][provider]))
        if provider == "kie":
            data["models"].pop("topaz-upscale", None)
        providers[provider] = data
    return {
        "schema_version": source.get("schema_version"),
        "version_date": source.get("version_date"),
        "notes": source.get("notes", []),
        "providers": providers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canonical", nargs="?", type=Path, default=DEFAULT_GEMMOBI)
    args = parser.parse_args()
    packaged = json.loads((HERE / "model_contracts.json").read_text(encoding="utf-8"))
    if not args.canonical.is_file():
        print(f"GemMobi canonical contract not found: {args.canonical}")
        return 2
    source = json.loads(args.canonical.read_text(encoding="utf-8"))
    if packaged != relevant(source):
        print("WorkflowX Kie/Atlas contracts have drifted from GemMobi.")
        return 1
    print(f"WorkflowX Kie/Atlas contracts match GemMobi {source.get('version_date', 'unknown')}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
