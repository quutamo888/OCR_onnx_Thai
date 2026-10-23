#!/usr/bin/env python3
"""Generate Self-Signed Root CA and Web Server Certificates for TLS 1.3.

Outputs in certs/:
- certs/ca.key, certs/ca.crt (ThaiOCR Internal Root CA)
- certs/web_server.key, certs/web_server.crt (TLS 1.3 Server Certificate)
"""

import datetime
from pathlib import Path
from ipaddress import ip_address
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"


def generate_tls_certificates(domain_or_ip: str = "localhost"):
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Generating Self-Signed TLS 1.3 Certificates into: {CERTS_DIR}")

    # 1. Generate Root CA
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThaiOCR Organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ThaiOCR Internal Root CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # 2. Generate Web Server Certificate
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThaiOCR Organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "thai-ocr-gateway"),
    ])

    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("thai-ocr-web"),
        x509.IPAddress(ip_address("127.0.0.1")),
    ]
    if domain_or_ip and domain_or_ip not in ("localhost", "127.0.0.1"):
        try:
            san_list.append(x509.IPAddress(ip_address(domain_or_ip)))
        except ValueError:
            san_list.append(x509.DNSName(domain_or_ip))

    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1825))
        .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    def save_pem(path: Path, data: bytes):
        with open(path, "wb") as f:
            f.write(data)

    save_pem(CERTS_DIR / "ca.key", ca_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    ))
    save_pem(CERTS_DIR / "ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM))

    save_pem(CERTS_DIR / "web_server.key", server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    ))
    save_pem(CERTS_DIR / "web_server.crt", server_cert.public_bytes(serialization.Encoding.PEM))

    print("[OK] TLS 1.3 Certificates generated successfully:")
    print(f"  - CA Certificate:     {CERTS_DIR / 'ca.crt'}")
    print(f"  - Server Certificate: {CERTS_DIR / 'web_server.crt'}")
    print(f"  - Server Key:         {CERTS_DIR / 'web_server.key'}")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    generate_tls_certificates(target)
