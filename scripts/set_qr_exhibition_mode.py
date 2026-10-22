#!/usr/bin/env python3
"""Legacy four-item QR filter. Default invocation is read-only.

The seven QR items in the approved Windows exhibition must remain intact.
This historical maintenance utility is not used by the exhibition launcher.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "data" / "qr_scenarios.json"
APPROVED_QR_SHA256 = "f1cd458c03fd62ef10f1063075806a42c335375f43d18f0d09b0135ce8d983f2"
APPROVED_IDS = {
    "traffic_fine_qr",
    "email_delivery_qr",
    "email_bank_verification_qr",
    "email_invoice_payment_qr",
    "email_eopyy_refund_qr",
    "email_europol_judicial_order_qr",
    "email_aade_tax_refund_qr",
}
LEGACY_IDS = {
    "email_delivery_qr",
    "email_bank_verification_qr",
    "email_invoice_payment_qr",
    "traffic_fine_qr",
}


def inspect_source() -> tuple[bytes, dict, list]:
    if SCENARIOS.is_symlink() or not SCENARIOS.is_file():
        raise ValueError("QR scenarios missing or symlinked")
    raw = SCENARIOS.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("QR data must contain a list named items")
    items = data["items"]
    ids = [item.get("id") for item in items if isinstance(item, dict)]
    if len(items) != len(ids) or len(ids) != len(set(ids)):
        raise ValueError("QR scenario items must have distinct IDs")
    return raw, data, ids


def apply_legacy_four(raw: bytes, data: dict, ids: list) -> None:
    if hashlib.sha256(raw).hexdigest() != APPROVED_QR_SHA256 or len(ids) != 7 or set(ids) != APPROVED_IDS:
        raise ValueError("QR data differs from the approved seven-scenario release; refusing mutation")
    filtered = [item for item in data["items"] if item["id"] in LEGACY_IDS]
    if len(filtered) != 4 or {item["id"] for item in filtered} != LEGACY_IDS:
        raise ValueError("Legacy four-item selection failed validation")
    backup_root = ROOT / ".fraudlab_backups"
    if backup_root.is_symlink():
        raise ValueError("Unsafe symlinked backup folder")
    backup_root.mkdir(exist_ok=True)
    backup = backup_root / ("legacy_qr_four_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + secrets.token_hex(3))
    backup.mkdir(exist_ok=False)
    (backup / "qr_scenarios.json").write_bytes(raw)
    metadata = {
        "schema": 1,
        "operation": "intentional_legacy_four_qr_reduction",
        "original_sha256": APPROVED_QR_SHA256,
        "original_scenario_count": 7,
        "backup_filename": "qr_scenarios.json",
    }
    (backup / "backup.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hashlib.sha256((backup / "qr_scenarios.json").read_bytes()).hexdigest() != APPROVED_QR_SHA256:
        raise ValueError("QR backup verification failed; no scenario changes")
    data["items"] = filtered
    replacement = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=SCENARIOS.parent, prefix=".qr_legacy_", suffix=".tmp", delete=False) as stream:
            tmp_path = Path(stream.name)
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        # Refuse to overwrite any content changed while the backup was created.
        if hashlib.sha256(SCENARIOS.read_bytes()).hexdigest() != APPROVED_QR_SHA256:
            raise ValueError("QR data changed during operation; refusing mutation")
        os.replace(tmp_path, SCENARIOS)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    print("LEGACY QR CHANGE APPLIED: 7 -> 4 (explicitly confirmed)")
    print("RESTORE SOURCE: " + str(backup / "qr_scenarios.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-legacy-four", action="store_true", help="Explicitly request the historical four-item QR mode")
    parser.add_argument("--confirm-remove-three", action="store_true", help="Acknowledge removal of three approved QR scenarios")
    args = parser.parse_args()
    if not args.apply_legacy_four:
        if args.confirm_remove_three:
            parser.error("--confirm-remove-three requires --apply-legacy-four")
        raw, _, ids = inspect_source()
        print("SAFE READ-ONLY: QR scenarios unchanged; " + str(len(ids)) + " items")
        print("APPROVED SEVEN PRESENT: " + str(set(ids) == APPROVED_IDS and len(ids) == 7))
        print("SOURCE SHA256: " + hashlib.sha256(raw).hexdigest())
        return 0
    if not args.confirm_remove_three:
        parser.error("Intentional legacy change requires BOTH --apply-legacy-four and --confirm-remove-three")
    raw, data, ids = inspect_source()
    apply_legacy_four(raw, data, ids)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("QR LEGACY HELPER STOP: " + str(exc), file=sys.stderr)
        sys.exit(1)
