"""
Certificate management module for DJANGOForge
Handles Root CA and SSL certificate generation
"""

from pathlib import Path
from typing import Dict, Optional
import subprocess
from datetime import datetime


class CertificateManager:
    """Manages SSL certificates for local development"""

    def __init__(self):
        self.djamp_home = Path.home() / ".djamp"
        self.ca_dir = self.djamp_home / "ca"
        self.cert_dir = self.djamp_home / "certs"
        self.ca_cert_path = self.ca_dir / "djangoforge-root-ca.crt"
        self.ca_key_path = self.ca_dir / "djangoforge-root-ca.key"

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        self.ca_dir.mkdir(parents=True, exist_ok=True)
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    async def generate_root_ca(self) -> Dict[str, any]:
        """Generate Root CA certificate"""
        try:
            self._ensure_directories()

            # Check if CA already exists
            if self.ca_cert_path.exists() and self.ca_key_path.exists():
                return {"success": True, "message": "Root CA already exists"}

            # Generate Root CA
            process = await asyncio.create_subprocess_exec(
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-keyout",
                str(self.ca_key_path),
                "-out",
                str(self.ca_cert_path),
                "-days",
                "3650",
                "-nodes",
                "-subj",
                "/C=US/ST=State/L=City/O=DJANGOForge/OU=Development/CN=DJANGOForge Root CA",
                "-addext",
                "basicConstraints=critical,CA:TRUE,pathlen:0",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return {"success": False, "error": stderr.decode()}

            return {"success": True, "certificate_path": str(self.ca_cert_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def generate_certificate(self, domain: str) -> Dict[str, any]:
        """Generate SSL certificate for a domain"""
        try:
            self._ensure_directories()

            # Check if Root CA exists
            if not self.ca_cert_path.exists() or not self.ca_key_path.exists():
                return {"success": False, "error": "Root CA not found. Generate Root CA first."}

            cert_key_path = self.cert_dir / f"{domain}.key"
            cert_crt_path = self.cert_dir / f"{domain}.crt"
            config_path = self.cert_dir / f"{domain}.conf"

            # Create config file
            config_content = f"""
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = {domain}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = {domain}
DNS.2 = www.{domain}
"""
            config_path.write_text(config_content)

            # Generate private key
            process = await asyncio.create_subprocess_exec(
                "openssl",
                "genrsa",
                "-out",
                str(cert_key_path),
                "2048",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if process.returncode != 0:
                return {"success": False, "error": "Failed to generate private key"}

            # Generate CSR
            csr_path = self.cert_dir / f"{domain}.csr"
            process = await asyncio.create_subprocess_exec(
                "openssl",
                "req",
                "-new",
                "-key",
                str(cert_key_path),
                "-out",
                str(csr_path),
                "-config",
                str(config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            if process.returncode != 0:
                return {"success": False, "error": "Failed to generate CSR"}

            # Sign certificate
            process = await asyncio.create_subprocess_exec(
                "openssl",
                "x509",
                "-req",
                "-in",
                str(csr_path),
                "-CA",
                str(self.ca_cert_path),
                "-CAkey",
                str(self.ca_key_path),
                "-CAcreateserial",
                "-out",
                str(cert_crt_path),
                "-days",
                "365",
                "-sha256",
                "-extensions",
                "v3_req",
                "-extfile",
                str(config_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            # Clean up
            csr_path.unlink(missing_ok=True)
            config_path.unlink(missing_ok=True)

            if process.returncode != 0:
                return {"success": False, "error": stderr.decode()}

            # Get expiration date
            expiration = await self._get_certificate_expiration(cert_crt_path)

            return {
                "success": True,
                "domain": domain,
                "certificate_path": str(cert_crt_path),
                "key_path": str(cert_key_path),
                "expires_at": expiration,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_certificate_expiration(self, cert_path: Path) -> str:
        """Get certificate expiration date"""
        process = await asyncio.create_subprocess_exec(
            "openssl",
            "x509",
            "-enddate",
            "-noout",
            "-in",
            str(cert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout.decode().replace("notAfter=", "").strip()
        return ""

    async def check_certificate_status(self, domain: str) -> Dict[str, any]:
        """Check if certificate exists and is valid"""
        cert_path = self.cert_dir / f"{domain}.crt"
        key_path = self.cert_dir / f"{domain}.key"

        if not cert_path.exists() or not key_path.exists():
            return {
                "domain": domain,
                "certificate_path": str(cert_path),
                "key_path": str(key_path),
                "is_valid": False,
            }

        # Check validity
        process = await asyncio.create_subprocess_exec(
            "openssl",
            "x509",
            "-checkend",
            "0",
            "-in",
            str(cert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        is_valid = process.returncode == 0

        expiration = await self._get_certificate_expiration(cert_path)

        return {
            "domain": domain,
            "certificate_path": str(cert_path),
            "key_path": str(key_path),
            "expires_at": expiration,
            "is_valid": is_valid,
        }

    async def install_root_ca(self) -> Dict[str, any]:
        """Install Root CA to system trust store"""
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            return await self._install_ca_macos()
        elif system == "Windows":
            return await self._install_ca_windows()
        elif system == "Linux":
            return await self._install_ca_linux()
        else:
            return {"success": False, "error": f"Unsupported platform: {system}"}

    async def _install_ca_macos(self) -> Dict[str, any]:
        """Install Root CA on macOS"""
        process = await asyncio.create_subprocess_exec(
            "sudo",
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            "/Library/Keychains/System.keychain",
            str(self.ca_cert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"success": False, "error": stderr.decode()}

        return {"success": True}

    async def _install_ca_windows(self) -> Dict[str, any]:
        """Install Root CA on Windows"""
        process = await asyncio.create_subprocess_exec(
            "certutil",
            "-addstore",
            "-f",
            "Root",
            str(self.ca_cert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"success": False, "error": stderr.decode()}

        return {"success": True}

    async def _install_ca_linux(self) -> Dict[str, any]:
        """Install Root CA on Linux"""
        # This would vary by distribution
        return {"success": False, "error": "Linux installation not implemented yet"}

    async def check_root_ca_status(self) -> Dict[str, any]:
        """Check if Root CA is installed and trusted"""
        import platform

        system = platform.system()

        if not self.ca_cert_path.exists():
            return {"installed": False, "valid": False}

        if system == "Darwin":  # macOS
            return await self._check_ca_status_macos()
        elif system == "Windows":
            return await self._check_ca_status_windows()
        elif system == "Linux":
            return await self._check_ca_status_linux()
        else:
            return {"installed": False, "valid": False}

    async def _check_ca_status_macos(self) -> Dict[str, any]:
        """Check Root CA status on macOS"""
        process = await asyncio.create_subprocess_exec(
            "security",
            "find-certificate",
            "-c",
            "DJANGOForge",
            "/Library/Keychains/System.keychain",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        installed = process.returncode == 0

        # Check if trusted
        process = await asyncio.create_subprocess_exec(
            "security",
            "verify-cert",
            "-c",
            str(self.ca_cert_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        valid = process.returncode == 0

        return {"installed": installed, "valid": valid}

    async def _check_ca_status_windows(self) -> Dict[str, any]:
        """Check Root CA status on Windows"""
        process = await asyncio.create_subprocess_exec(
            "certutil",
            "-store",
            "Root",
            "DJANGOForge",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        installed = process.returncode == 0

        return {"installed": installed, "valid": installed}

    async def _check_ca_status_linux(self) -> Dict[str, any]:
        """Check Root CA status on Linux"""
        return {"installed": False, "valid": False}
