from __future__ import annotations

import hashlib
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .domains import _sanitize_hostname, _try_sanitize_hostname
from .macos_helper import _run_with_macos_elevation
from .models import CertificateInfo, CommandResult
from .paths import paths
from .subprocess_security import _find_allowed_executable, _run_blocking


def _certificate_paths(domain: str) -> Tuple[Path, Path, Path]:
    cert_dir = paths()["certs"]
    cert_dir.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_hostname(domain)
    safe_hash = hashlib.sha256(safe.encode("utf-8")).hexdigest()
    cert = cert_dir / f"{safe_hash}.crt"
    key = cert_dir / f"{safe_hash}.key"
    conf = cert_dir / f"{safe_hash}.cnf"
    return cert, key, conf


def _root_ca_paths() -> Tuple[Path, Path]:
    ca_dir = paths()["ca"]
    ca_dir.mkdir(parents=True, exist_ok=True)
    return ca_dir / "djamp-pro-root-ca.crt", ca_dir / "djamp-pro-root-ca.key"


def _tighten_cert_permissions(directory: Path, key: Path, cert: Path) -> None:
    """Best-effort: private keys must not be world-readable (no-op on Windows)."""
    if platform.system() == "Windows":
        return
    for path, mode in ((directory, 0o700), (key, 0o600), (cert, 0o644)):
        try:
            path.chmod(mode)
        except Exception:
            pass


def _ensure_root_ca() -> CommandResult:
    openssl = _find_allowed_executable("openssl", paths()["home"])
    if not openssl:
        return CommandResult(success=False, error="`openssl` was not found in PATH")

    ca_cert, ca_key = _root_ca_paths()
    if ca_cert.exists() and ca_key.exists():
        # Tighten permissions even when the CA already exists.
        _tighten_cert_permissions(paths()["ca"], ca_key, ca_cert)
        return CommandResult(success=True, output="Root CA already exists")

    ca_conf = paths()["ca"] / "root-ca.cnf"
    ca_conf.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = dn",
                "x509_extensions = v3_ca",
                "prompt = no",
                "",
                "[dn]",
                "C = US",
                "ST = Local",
                "L = Local",
                "O = DJAMP PRO",
                "OU = Development",
                "CN = DJAMP PRO Root CA",
                "",
                "[v3_ca]",
                "basicConstraints = critical,CA:TRUE,pathlen:0",
                "keyUsage = critical,keyCertSign,cRLSign",
                "subjectKeyIdentifier = hash",
                "authorityKeyIdentifier = keyid:always,issuer",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = [
        openssl,
        "req",
        "-x509",
        "-newkey",
        "rsa:4096",
        "-keyout",
        str(ca_key),
        "-out",
        str(ca_cert),
        "-days",
        "3650",
        "-nodes",
        "-config",
        str(ca_conf),
        "-extensions",
        "v3_ca",
    ]
    result = _run_blocking(cmd, paths()["home"])
    if result.success:
        # Protect the CA private key (it can sign certs for any hostname).
        _tighten_cert_permissions(paths()["ca"], ca_key, ca_cert)
    return result


def _generate_certificate(domain: str, alt_domains: Optional[List[str]] = None) -> CertificateInfo:
    ensure = _ensure_root_ca()
    if not ensure.success:
        raise RuntimeError(ensure.error)

    openssl = _find_allowed_executable("openssl", paths()["home"])
    if not openssl:
        raise RuntimeError("`openssl` was not found in PATH")

    primary = _sanitize_hostname(domain)
    cert, key, conf = _certificate_paths(primary)
    ca_cert, ca_key = _root_ca_paths()

    sans = [primary]
    if alt_domains:
        for d in alt_domains:
            cleaned = _try_sanitize_hostname(d)
            if cleaned and cleaned not in sans:
                sans.append(cleaned)

    alt_lines = [f"DNS.{idx + 1} = {value}" for idx, value in enumerate(sans)]
    conf.write_text(
        "\n".join(
            [
                "[req]",
                "distinguished_name = req_distinguished_name",
                "req_extensions = v3_req",
                "prompt = no",
                "",
                "[req_distinguished_name]",
                f"CN = {primary}",
                "",
                "[v3_req]",
                "basicConstraints = critical,CA:FALSE",
                "keyUsage = critical,digitalSignature,keyEncipherment",
                "extendedKeyUsage = serverAuth",
                "subjectAltName = @alt_names",
                "",
                "[alt_names]",
                *alt_lines,
            ]
        ),
        encoding="utf-8",
    )

    csr = cert.with_suffix(".csr")

    run_key = _run_blocking([openssl, "genrsa", "-out", str(key), "2048"], paths()["home"])
    if not run_key.success:
        raise RuntimeError(run_key.error)

    run_csr = _run_blocking(
        [openssl, "req", "-new", "-key", str(key), "-out", str(csr), "-config", str(conf)],
        paths()["home"],
    )
    if not run_csr.success:
        raise RuntimeError(run_csr.error)

    run_sign = _run_blocking(
        [
            openssl,
            "x509",
            "-req",
            "-in",
            str(csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(cert),
            "-days",
            "365",
            "-sha256",
            "-extensions",
            "v3_req",
            "-extfile",
            str(conf),
        ],
        paths()["home"],
    )
    try:
        csr.unlink(missing_ok=True)
        conf.unlink(missing_ok=True)
    except Exception:
        pass

    if not run_sign.success:
        raise RuntimeError(run_sign.error)

    _tighten_cert_permissions(paths()["certs"], key, cert)

    expires = _get_cert_expiration(cert)
    return CertificateInfo(
        domain=primary,
        certificatePath=str(cert),
        keyPath=str(key),
        expiresAt=expires,
        isValid=True,
    )


def _get_cert_expiration(cert_path: Path) -> str:
    openssl = _find_allowed_executable("openssl", paths()["home"])
    if not openssl:
        return ""
    result = _run_blocking(
        [openssl, "x509", "-enddate", "-noout", "-in", str(cert_path)],
        paths()["home"],
    )
    if not result.success:
        return ""
    return result.output.replace("notAfter=", "").strip()


def _check_certificate(domain: str) -> CertificateInfo:
    safe_domain = _sanitize_hostname(domain)
    cert, key, _ = _certificate_paths(safe_domain)
    if not cert.exists() or not key.exists():
        return CertificateInfo(domain=safe_domain, certificatePath=str(cert), keyPath=str(key), isValid=False)

    openssl = _find_allowed_executable("openssl", paths()["home"])
    if not openssl:
        return CertificateInfo(
            domain=safe_domain,
            certificatePath=str(cert),
            keyPath=str(key),
            expiresAt="",
            isValid=False,
        )

    validity = _run_blocking([openssl, "x509", "-checkend", "0", "-in", str(cert)], paths()["home"])
    return CertificateInfo(
        domain=safe_domain,
        certificatePath=str(cert),
        keyPath=str(key),
        expiresAt=_get_cert_expiration(cert),
        isValid=validity.success,
    )


def _install_root_ca() -> CommandResult:
    ensure = _ensure_root_ca()
    if not ensure.success:
        return ensure

    ca_cert, _ = _root_ca_paths()
    system = platform.system()

    if system == "Darwin":
        login_keychain = str(Path.home() / "Library" / "Keychains" / "login.keychain-db")
        # Prefer the user keychain to avoid admin prompts (sufficient for local dev trust).
        command = [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            login_keychain,
            str(ca_cert),
        ]
        result = _run_blocking(command, paths()["home"])
        if result.success:
            return result

        # Fallback: install into System keychain (requires admin).
        command = [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            "/Library/Keychains/System.keychain",
            str(ca_cert),
        ]
        result = _run_blocking(command, paths()["home"])
        if result.success:
            return result
        elevated = _run_with_macos_elevation(command, cwd=paths()["home"])
        if elevated.success:
            return elevated
        return CommandResult(
            success=False,
            output=result.output,
            error=elevated.error or result.error,
        )

    if system == "Windows":
        return _run_blocking(["certutil", "-addstore", "-f", "Root", str(ca_cert)], paths()["home"])

    return CommandResult(success=False, error="Automatic trust install is only implemented for macOS and Windows")


def _uninstall_root_ca() -> CommandResult:
    """Remove the DJAMP Root CA from macOS keychains (best-effort)."""
    ca_cert, ca_key = _root_ca_paths()
    if not ca_cert.exists() or not ca_key.exists():
        return CommandResult(success=True, output="Root CA files not found; nothing to uninstall")

    system = platform.system()
    if system != "Darwin":
        return CommandResult(success=False, error="Automatic trust removal is only implemented for macOS")

    security = _find_allowed_executable("security", paths()["home"])
    if not security:
        return CommandResult(success=False, error="`security` CLI not found")

    common_name = "DJAMP PRO Root CA"
    login_keychain = str(Path.home() / "Library" / "Keychains" / "login.keychain-db")
    system_keychain = "/Library/Keychains/System.keychain"

    def _not_found(text: str) -> bool:
        t = (text or "").lower()
        return "could not be found" in t or "could not be found in the keychain" in t

    ok_login = True
    if Path(login_keychain).exists():
        res = _run_blocking([security, "delete-certificate", "-c", common_name, login_keychain], paths()["home"])
        ok_login = res.success or _not_found(f"{res.output}\n{res.error}")

    ok_system = True
    if Path(system_keychain).exists():
        res = _run_blocking([security, "delete-certificate", "-c", common_name, system_keychain], paths()["home"])
        if res.success or _not_found(f"{res.output}\n{res.error}"):
            ok_system = True
        else:
            elevated = _run_with_macos_elevation([security, "delete-certificate", "-c", common_name, system_keychain])
            ok_system = elevated.success or _not_found(f"{elevated.output}\n{elevated.error}")

    if ok_login and ok_system:
        return CommandResult(success=True, output="Root CA removed from keychains")
    return CommandResult(success=False, error="Failed to remove Root CA from one or more keychains")


def _check_root_ca_status() -> Dict[str, bool]:
    ca_cert, ca_key = _root_ca_paths()
    if not ca_cert.exists() or not ca_key.exists():
        return {"installed": False, "valid": False}

    openssl = _find_allowed_executable("openssl", paths()["home"])
    valid = True
    if openssl:
        # `openssl x509 -checkend` returns 0 when the cert is NOT expired.
        valid = _run_blocking([openssl, "x509", "-checkend", "0", "-in", str(ca_cert)], paths()["home"]).success

    system = platform.system()
    if system == "Darwin":
        installed = _is_root_ca_trusted_macos(ca_cert)
        return {"installed": installed, "valid": valid}
    if system == "Windows":
        # MVP: we only auto-install on Windows; trust-status detection is best-effort.
        return {"installed": True, "valid": valid}
    return {"installed": True, "valid": valid}


def _normalize_hex(value: str) -> str:
    return "".join([ch for ch in (value or "").upper() if ch in "0123456789ABCDEF"])


def _openssl_sha1_fingerprint(cert_path: Path) -> str:
    openssl = _find_allowed_executable("openssl", paths()["home"])
    if not openssl or not cert_path.exists():
        return ""
    result = _run_blocking([openssl, "x509", "-noout", "-fingerprint", "-sha1", "-in", str(cert_path)], paths()["home"])
    if not result.success:
        return ""
    # Example: "SHA1 Fingerprint=AA:BB:...".
    for line in (result.output or "").splitlines():
        if "Fingerprint=" in line:
            return _normalize_hex(line.split("Fingerprint=", 1)[1])
    return _normalize_hex(result.output)


def _security_keychain_sha1_hashes(common_name: str, keychain: str) -> List[str]:
    security = _find_allowed_executable("security", paths()["home"])
    if not security:
        return []
    result = _run_blocking([security, "find-certificate", "-a", "-Z", "-c", common_name, keychain], paths()["home"])
    text = f"{result.output}\n{result.error}".strip()
    hashes: List[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if raw.startswith("SHA-1 hash:"):
            hashes.append(_normalize_hex(raw.split(":", 1)[1]))
    return hashes


def _is_root_ca_trusted_macos(ca_cert: Path) -> bool:
    """Return True when the DJAMP Root CA is present in a macOS keychain (trusted by the OS)."""
    sha1 = _openssl_sha1_fingerprint(ca_cert)
    if not sha1:
        return False

    keychains = [
        "/Library/Keychains/System.keychain",
        str(Path.home() / "Library" / "Keychains" / "login.keychain-db"),
    ]
    for keychain in keychains:
        if not Path(keychain).exists():
            continue
        hashes = _security_keychain_sha1_hashes("DJAMP PRO Root CA", keychain)
        if sha1 in hashes:
            return True
    return False
