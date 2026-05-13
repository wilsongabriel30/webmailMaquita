"""Evidence Signer — GPG signing and timestamping for eDiscovery exports.

Provides immutable evidence chain:
1. SHA256 hash per EML file
2. SHA256 hash of manifest
3. GPG detached signature of manifest
4. Timestamp seal (RFC3161-inspired)
5. Append-only audit trail

Deployed to: /opt/maquita-webmail/backend/app/compliance/evidence_signer.py
"""

import hashlib
import json
import logging
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("compliance.signer")

GPG_KEY_EMAIL = "compliance@maquita.org"
GPG_KEY_NAME = "Maquita Compliance"
EVIDENCE_AUDIT_LOG = "/var/lib/maquita-compliance/audit.log"
AUDIT_DIR = "/var/lib/maquita-compliance"


def _ensure_audit_dir() -> None:
    """Create the audit log directory if it doesn't exist."""
    os.makedirs(AUDIT_DIR, mode=0o700, exist_ok=True)


def _get_gpg_fingerprint() -> Optional[str]:
    """Return the fingerprint of the compliance GPG key, or None if not found."""
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--with-colons", "--list-keys", GPG_KEY_EMAIL],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line.startswith("fpr:"):
                return line.split(":")[9]
        return None
    except FileNotFoundError:
        logger.error("gpg binary not found — GPG is required for evidence signing")
        raise RuntimeError("gpg binary not found. Install gnupg2.")
    except subprocess.TimeoutExpired:
        logger.error("gpg --list-keys timed out")
        return None


async def ensure_gpg_key() -> str:
    """Ensure GPG key exists, create if not. Returns key fingerprint.

    The key is RSA-4096, no passphrase, created for server automation.
    Generation is non-interactive using --batch --gen-key.
    """
    existing_fp = _get_gpg_fingerprint()
    if existing_fp:
        logger.info("GPG compliance key already exists: %s", existing_fp)
        return existing_fp

    logger.info("Generating new GPG compliance key for %s <%s>", GPG_KEY_NAME, GPG_KEY_EMAIL)

    key_params = (
        "%no-protection\n"
        "Key-Type: RSA\n"
        "Key-Length: 4096\n"
        "Subkey-Type: RSA\n"
        "Subkey-Length: 4096\n"
        f"Name-Real: {GPG_KEY_NAME}\n"
        f"Name-Email: {GPG_KEY_EMAIL}\n"
        "Expire-Date: 0\n"
        "%commit\n"
    )

    try:
        result = subprocess.run(
            ["gpg", "--batch", "--gen-key"],
            input=key_params,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("GPG key generation failed: %s", result.stderr)
            raise RuntimeError(f"GPG key generation failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GPG key generation timed out (120s)")

    fingerprint = _get_gpg_fingerprint()
    if not fingerprint:
        raise RuntimeError("GPG key was generated but fingerprint could not be retrieved")

    logger.info("GPG compliance key created: %s", fingerprint)
    return fingerprint


def sign_manifest(manifest_path: str) -> str:
    """Create detached GPG signature for manifest file.

    Uses the compliance key to produce a binary detached signature (.sig).
    Returns the absolute path to the .sig file.

    Raises:
        FileNotFoundError: if manifest_path does not exist.
        RuntimeError: if GPG signing fails.
    """
    manifest_path = os.path.abspath(manifest_path)
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    sig_path = manifest_path + ".sig"

    # Remove stale signature if present
    if os.path.exists(sig_path):
        os.remove(sig_path)

    try:
        result = subprocess.run(
            [
                "gpg",
                "--batch",
                "--yes",
                "--local-user", GPG_KEY_EMAIL,
                "--detach-sign",
                "--output", sig_path,
                manifest_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GPG signing failed: {result.stderr}")
    except FileNotFoundError:
        raise RuntimeError("gpg binary not found")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GPG signing timed out (30s)")

    if not os.path.isfile(sig_path):
        raise RuntimeError("GPG signature file was not created")

    logger.info("Manifest signed: %s -> %s", manifest_path, sig_path)
    return sig_path


def create_timestamp_seal(manifest_hash: str, export_id: int, exported_by: str) -> dict:
    """Create a timestamp seal for the export (RFC 3161-inspired).

    The seal binds the manifest hash to a point in time and the server identity.
    seal_hash = SHA256(manifest_hash + iso_timestamp + export_id + hostname)

    Returns dict with:
        - timestamp_utc: ISO 8601 UTC string
        - manifest_hash: the input hash
        - export_id: the export identifier
        - exported_by: user who triggered the export
        - server_hostname: machine that produced the seal
        - seal_hash: the binding hash
    """
    now = datetime.now(timezone.utc)
    iso_ts = now.isoformat()
    hostname = platform.node()

    seal_input = f"{manifest_hash}|{iso_ts}|{export_id}|{hostname}"
    seal_hash = hashlib.sha256(seal_input.encode("utf-8")).hexdigest()

    seal = {
        "timestamp_utc": iso_ts,
        "manifest_hash": manifest_hash,
        "export_id": export_id,
        "exported_by": exported_by,
        "server_hostname": hostname,
        "seal_hash": seal_hash,
    }

    logger.info("Timestamp seal created for export %d: %s", export_id, seal_hash[:16])
    return seal


def verify_manifest_signature(manifest_path: str, sig_path: str) -> bool:
    """Verify GPG detached signature of a manifest file.

    Returns True if signature is valid, False otherwise.
    """
    manifest_path = os.path.abspath(manifest_path)
    sig_path = os.path.abspath(sig_path)

    if not os.path.isfile(manifest_path):
        logger.error("Manifest not found for verification: %s", manifest_path)
        return False
    if not os.path.isfile(sig_path):
        logger.error("Signature not found for verification: %s", sig_path)
        return False

    try:
        result = subprocess.run(
            ["gpg", "--batch", "--verify", sig_path, manifest_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        valid = result.returncode == 0
        if valid:
            logger.info("Signature VALID for %s", manifest_path)
        else:
            logger.warning("Signature INVALID for %s: %s", manifest_path, result.stderr)
        return valid
    except FileNotFoundError:
        logger.error("gpg binary not found — cannot verify")
        return False
    except subprocess.TimeoutExpired:
        logger.error("GPG verify timed out")
        return False


def append_audit_entry(entry: dict) -> None:
    """Append an entry to the immutable audit log.

    The log file is opened in append-only mode. Each line is a JSON object
    with an added `_logged_at` field.
    """
    _ensure_audit_dir()

    entry_copy = dict(entry)
    entry_copy["_logged_at"] = datetime.now(timezone.utc).isoformat()

    line = json.dumps(entry_copy, ensure_ascii=False, separators=(",", ":")) + "\n"

    try:
        fd = os.open(EVIDENCE_AUDIT_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except PermissionError:
        logger.error("Permission denied writing audit log: %s", EVIDENCE_AUDIT_LOG)
        raise
    except OSError as exc:
        logger.error("Failed to write audit log: %s", exc)
        raise


def _sha256_file(path: str) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _verify_eml_hashes(export_path: str, manifest: dict) -> list:
    """Verify that all EML files in the manifest match their recorded hashes.

    Returns a list of mismatched files (empty list = all OK).
    """
    mismatches = []
    messages = manifest.get("messages", [])
    for msg in messages:
        eml_file = msg.get("eml_file")
        expected_hash = msg.get("sha256")
        if not eml_file or not expected_hash:
            continue
        eml_path = os.path.join(export_path, eml_file)
        if not os.path.isfile(eml_path):
            mismatches.append({"file": eml_file, "error": "file_missing"})
            continue
        actual_hash = _sha256_file(eml_path)
        if actual_hash != expected_hash:
            mismatches.append({
                "file": eml_file,
                "error": "hash_mismatch",
                "expected": expected_hash,
                "actual": actual_hash,
            })
    return mismatches


async def sign_export(
    export_path: str,
    manifest_path: str,
    export_id: int,
    exported_by: str,
    db_pool=None,
) -> dict:
    """Complete signing workflow for an eDiscovery export.

    Steps:
        1. Verify all EML hashes match manifest
        2. Sign manifest with GPG
        3. Create timestamp seal
        4. Append to audit log
        5. Update DB record with signature and timestamp (if db_pool provided)

    Returns:
        {
            gpg_signature_path: str,
            manifest_hash: str,
            timestamp_seal: dict,
            verified: bool,
            eml_mismatches: list  (empty if all OK)
        }

    Raises:
        FileNotFoundError: if manifest does not exist.
        RuntimeError: on GPG errors.
    """
    manifest_path = os.path.abspath(manifest_path)
    export_path = os.path.abspath(export_path)

    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    # 0. Ensure GPG key is available
    fingerprint = await ensure_gpg_key()

    # 1. Load manifest and verify EML hashes
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    mismatches = _verify_eml_hashes(export_path, manifest)
    if mismatches:
        logger.warning(
            "EML hash verification found %d mismatches for export %d",
            len(mismatches),
            export_id,
        )

    # 2. Compute manifest hash and sign
    manifest_hash = _sha256_file(manifest_path)
    sig_path = sign_manifest(manifest_path)

    # 3. Verify own signature immediately
    verified = verify_manifest_signature(manifest_path, sig_path)

    # 4. Create timestamp seal
    seal = create_timestamp_seal(manifest_hash, export_id, exported_by)

    # Save seal next to manifest
    seal_path = manifest_path.replace("manifest.json", "timestamp_seal.json")
    if seal_path == manifest_path:
        seal_path = manifest_path + ".seal.json"
    with open(seal_path, "w", encoding="utf-8") as f:
        json.dump(seal, f, indent=2, ensure_ascii=False)

    # 5. Append to audit log
    audit_entry = {
        "action": "export_signed",
        "export_id": export_id,
        "exported_by": exported_by,
        "manifest_hash": manifest_hash,
        "seal_hash": seal["seal_hash"],
        "gpg_fingerprint": fingerprint,
        "gpg_signature_path": sig_path,
        "eml_mismatches": len(mismatches),
        "verified": verified,
    }
    try:
        append_audit_entry(audit_entry)
    except OSError:
        logger.error("Audit log write failed — signing still completed")

    # 6. Update DB if pool available
    if db_pool is not None:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE compliance_exports
                    SET gpg_signature_path = $1,
                        manifest_hash = $2,
                        timestamp_seal = $3,
                        signed_at = NOW(),
                        gpg_fingerprint = $4,
                        verified = $5
                    WHERE id = $6
                    """,
                    sig_path,
                    manifest_hash,
                    json.dumps(seal),
                    fingerprint,
                    verified,
                    export_id,
                )
            logger.info("DB updated for export %d", export_id)
        except Exception:
            logger.exception("Failed to update DB for export %d", export_id)

    result = {
        "gpg_signature_path": sig_path,
        "manifest_hash": manifest_hash,
        "timestamp_seal": seal,
        "verified": verified,
        "eml_mismatches": mismatches,
    }
    logger.info("Export %d signed successfully (verified=%s)", export_id, verified)
    return result


def get_export_signing_info(export_path: str) -> dict:
    """Get signing info for an existing export (for verification).

    Looks for manifest.json, manifest.json.sig, and timestamp_seal.json
    in the export directory. Verifies the signature if all files are present.

    Returns:
        {
            signed: bool,
            manifest_path: str | None,
            signature_path: str | None,
            seal_path: str | None,
            manifest_hash: str | None,
            signature_valid: bool | None,
            timestamp_seal: dict | None,
        }
    """
    export_path = os.path.abspath(export_path)
    manifest_path = os.path.join(export_path, "manifest.json")
    sig_path = manifest_path + ".sig"
    seal_path = os.path.join(export_path, "timestamp_seal.json")

    info: dict = {
        "signed": False,
        "manifest_path": None,
        "signature_path": None,
        "seal_path": None,
        "manifest_hash": None,
        "signature_valid": None,
        "timestamp_seal": None,
    }

    if not os.path.isfile(manifest_path):
        logger.warning("No manifest.json in %s", export_path)
        return info

    info["manifest_path"] = manifest_path
    info["manifest_hash"] = _sha256_file(manifest_path)

    if os.path.isfile(sig_path):
        info["signature_path"] = sig_path
        info["signed"] = True
        info["signature_valid"] = verify_manifest_signature(manifest_path, sig_path)

    if os.path.isfile(seal_path):
        info["seal_path"] = seal_path
        try:
            with open(seal_path, "r", encoding="utf-8") as f:
                info["timestamp_seal"] = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read timestamp seal: %s", exc)

    return info
