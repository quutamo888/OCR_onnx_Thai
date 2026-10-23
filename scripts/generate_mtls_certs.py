#!/usr/bin/env python3
"""Generate mTLS (Mutual TLS) Certificates for ThaiOCR System.

Generates:
1. Root CA (certs/ca.crt, certs/ca.key)
2. Windows Worker Server Cert (certs/server.crt, certs/server.key)
3. Ubuntu Web App Client Cert (certs/client.crt, certs/client.key)
"""

import os
import sys
import datetime
from pathlib import Path
from ipaddress import ip_address
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"


def generate_mtls_pair(worker_ip_or_host: str = "127.0.0.1"):
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Generating mTLS Certificates into: {CERTS_DIR}")

    # 1. Generate Root CA
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThaiOCR Organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "ThaiOCR mTLS CA"),
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

    # 2. Generate Server Key & Cert (Windows Worker)
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThaiOCR Organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "thai-ocr-worker"),
    ])

    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("thai-windows-worker"),
        x509.IPAddress(ip_address("127.0.0.1")),
    ]
    try:
        san_list.append(x509.IPAddress(ip_address(worker_ip_or_host)))
    except ValueError:
        san_list.append(x509.DNSName(worker_ip_or_host))

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

    # 3. Generate Client Key & Cert (Ubuntu App)
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThaiOCR Organization"),
        x509.NameAttribute(NameOID.COMMON_NAME, "thai-ocr-web-client"),
    ])
    client_cert = (
        x509.CertificateBuilder()
        .subject_name(client_name)
        .issuer_name(ca_name)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1825))
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # Write files
    def save_pem(path: Path, data: bytes):
        with open(path, "wb") as f:
            f.write(data)

    save_pem(CERTS_DIR / "ca.key", ca_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    ))
    save_pem(CERTS_DIR / "ca.crt", ca_cert.public_bytes(serialization.Encoding.PEM))

    save_pem(CERTS_DIR / "server.key", server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    ))
    save_pem(CERTS_DIR / "server.crt", server_cert.public_bytes(serialization.Encoding.PEM))

    save_pem(CERTS_DIR / "client.key", client_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    ))
    save_pem(CERTS_DIR / "client.crt", client_cert.public_bytes(serialization.Encoding.PEM))

    print("[OK] Generated mTLS files successfully:")
    print(f"  - CA Cert:     {CERTS_DIR / 'ca.crt'}")
    print(f"  - Server Cert: {CERTS_DIR / 'server.crt'} (Key: server.key)")
    print(f"  - Client Cert: {CERTS_DIR / 'client.crt'} (Key: client.key)")


if __name__ == "__main__":
    ip_or_host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    generate_mtls_pair(ip_or_host)
