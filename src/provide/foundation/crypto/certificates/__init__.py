"""X.509 certificate generation and management."""

from datetime import UTC, datetime, timedelta
from functools import cached_property
import os
from pathlib import Path
import traceback
from typing import Self

from attrs import Factory, define, field

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, rsa
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.x509 import Certificate as X509Certificate

    _HAS_CRYPTO = True
except ImportError:
    # Stub out cryptography types for type hints
    x509 = None
    serialization = None
    ec = None
    rsa = None
    load_pem_private_key = None
    X509Certificate = None
    _HAS_CRYPTO = False

from provide.foundation import logger
from provide.foundation.crypto.constants import (
    DEFAULT_CERTIFICATE_CURVE,
    DEFAULT_CERTIFICATE_KEY_TYPE,
    DEFAULT_CERTIFICATE_VALIDITY_DAYS,
    DEFAULT_RSA_KEY_SIZE,
)

# Import from submodules
from .base import (
    CertificateBase,
    CertificateConfig,
    CertificateError,
    CurveType,
    KeyPair,
    KeyType,
    PublicKey,
    _require_crypto,
)
from .operations import create_x509_certificate, validate_signature

# Re-export public types
__all__ = [
    "Certificate",
    "CertificateBase",
    "CertificateConfig",
    "CertificateError",
    "CurveType",
    "KeyType",
    "create_self_signed",
    "create_ca",
]


@define(slots=True, eq=False, hash=False, repr=False)
class Certificate:
    """X.509 certificate management using attrs."""

    cert_pem_or_uri: str | None = field(default=None, kw_only=True)
    key_pem_or_uri: str | None = field(default=None, kw_only=True)
    generate_keypair: bool = field(default=False, kw_only=True)
    key_type: str = field(default=DEFAULT_CERTIFICATE_KEY_TYPE, kw_only=True)
    key_size: int = field(default=DEFAULT_RSA_KEY_SIZE, kw_only=True)
    ecdsa_curve: str = field(default=DEFAULT_CERTIFICATE_CURVE, kw_only=True)
    common_name: str = field(default="localhost", kw_only=True)
    alt_names: list[str] | None = field(
        default=Factory(lambda: ["localhost"]), kw_only=True
    )
    organization_name: str = field(default="Default Organization", kw_only=True)
    validity_days: int = field(default=DEFAULT_CERTIFICATE_VALIDITY_DAYS, kw_only=True)

    _base: CertificateBase = field(init=False, repr=False)
    _private_key: "KeyPair | None" = field(init=False, default=None, repr=False)
    _cert: "X509Certificate" = field(init=False, repr=False)
    _trust_chain: list["Certificate"] = field(init=False, factory=list, repr=False)

    cert: str = field(init=False, default="", repr=True)
    key: str | None = field(init=False, default=None, repr=False)

    def __attrs_post_init__(self) -> None:
        """Handle loading or generation logic after attrs initialization."""
        try:
            if self.generate_keypair:
                logger.debug(
                    "📜🔑🚀 Certificate.__attrs_post_init__: Generating new keypair"
                )

                now = datetime.now(UTC)
                not_valid_before = now - timedelta(days=1)
                not_valid_after = now + timedelta(days=self.validity_days)

                normalized_key_type_str = self.key_type.lower()
                match normalized_key_type_str:
                    case "rsa":
                        gen_key_type = KeyType.RSA
                    case "ecdsa":
                        gen_key_type = KeyType.ECDSA
                    case _:
                        raise ValueError(
                            f"Unsupported key_type string: '{self.key_type}'. "
                            "Must be 'rsa' or 'ecdsa'."
                        )

                gen_curve: CurveType | None = None
                gen_key_size = None

                if gen_key_type == KeyType.ECDSA:
                    try:
                        gen_curve = CurveType[self.ecdsa_curve.upper()]
                    except KeyError as e_curve:
                        raise ValueError(
                            f"Unsupported ECDSA curve: {self.ecdsa_curve}"
                        ) from e_curve
                else:  # RSA
                    gen_key_size = self.key_size

                conf: CertificateConfig = {
                    "common_name": self.common_name,
                    "organization": self.organization_name,
                    "alt_names": self.alt_names or ["localhost"],
                    "key_type": gen_key_type,
                    "not_valid_before": not_valid_before,
                    "not_valid_after": not_valid_after,
                }
                if gen_curve is not None:
                    conf["curve"] = gen_curve
                if gen_key_size is not None:
                    conf["key_size"] = gen_key_size
                logger.debug(f"📜🔑🚀 Generation config: {conf}")

                self._base, self._private_key = CertificateBase.create(conf)

                self._cert = create_x509_certificate(
                    base=self._base,
                    private_key=self._private_key,
                    alt_names=self.alt_names,
                    is_ca=False,
                    is_client_cert=True,
                )

                if self._cert is None:
                    raise CertificateError(
                        "Certificate object (_cert) is None after creation"
                    )

                self.cert = self._cert.public_bytes(serialization.Encoding.PEM).decode(
                    "utf-8"
                )
                if self._private_key:
                    self.key = self._private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    ).decode("utf-8")
                else:
                    self.key = None

                logger.debug(
                    "📜🔑✅ Certificate.__attrs_post_init__: Generated cert and key"
                )

            else:
                if not self.cert_pem_or_uri:
                    raise CertificateError(
                        "cert_pem_or_uri required when not generating"
                    )

                logger.debug("📜🔑🚀 Loading certificate from provided data")
                cert_data = self._load_from_uri_or_pem(self.cert_pem_or_uri)
                self.cert = cert_data

                logger.debug("📜🔑🔍 Loading X.509 certificate from PEM data")
                self._cert = x509.load_pem_x509_certificate(cert_data.encode("utf-8"))
                logger.debug("📜🔑✅ X.509 certificate object loaded from PEM")

                if self.key_pem_or_uri:
                    logger.debug("📜🔑🚀 Loading private key")
                    key_data = self._load_from_uri_or_pem(self.key_pem_or_uri)
                    self.key = key_data

                    loaded_priv_key = load_pem_private_key(
                        key_data.encode("utf-8"), password=None
                    )
                    if not isinstance(
                        loaded_priv_key,
                        rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey,
                    ):
                        raise CertificateError(
                            f"Loaded private key is of unsupported type: {type(loaded_priv_key)}. "
                            "Expected RSA or ECDSA private key."
                        )
                    self._private_key = loaded_priv_key
                    logger.debug("📜🔑✅ Private key object loaded and type validated")
                else:
                    self.key = None

                loaded_not_valid_before = self._cert.not_valid_before_utc
                loaded_not_valid_after = self._cert.not_valid_after_utc
                if loaded_not_valid_before.tzinfo is None:
                    loaded_not_valid_before = loaded_not_valid_before.replace(
                        tzinfo=UTC
                    )
                if loaded_not_valid_after.tzinfo is None:
                    loaded_not_valid_after = loaded_not_valid_after.replace(tzinfo=UTC)

                cert_public_key = self._cert.public_key()
                if not isinstance(
                    cert_public_key, rsa.RSAPublicKey | ec.EllipticCurvePublicKey
                ):
                    raise CertificateError(
                        f"Certificate's public key is of unsupported type: {type(cert_public_key)}. "
                        "Expected RSA or ECDSA public key."
                    )

                self._base = CertificateBase(
                    subject=self._cert.subject,
                    issuer=self._cert.issuer,
                    public_key=cert_public_key,
                    not_valid_before=loaded_not_valid_before,
                    not_valid_after=loaded_not_valid_after,
                    serial_number=self._cert.serial_number,
                )
                logger.debug("📜🔑✅ Reconstructed CertificateBase from loaded cert")

        except Exception as e:
            logger.error(
                f"📜❌ Certificate.__attrs_post_init__: Failed. Error: {type(e).__name__}: {e}",
                extra={"error": str(e), "trace": traceback.format_exc()},
            )
            raise CertificateError(
                f"Failed to initialize certificate. Original error: {type(e).__name__}"
            ) from e

    @staticmethod
    def _load_from_uri_or_pem(data: str) -> str:
        """Load PEM data either directly from a string or from a file URI."""
        try:
            if data.startswith("file://"):
                path_str = data.removeprefix("file://")
                if os.name == "nt" and path_str.startswith("//"):
                    path = Path(path_str)
                else:
                    path_str = path_str.lstrip("/")
                    if os.name != "nt" and data.startswith("file:///"):
                        path_str = "/" + path_str
                    path = Path(path_str)

                logger.debug(f"📜📂🚀 Loading data from file: {path}")
                with path.open("r", encoding="utf-8") as f:
                    loaded_data = f.read().strip()
                logger.debug("📜📂✅ Loaded data from file")
                return loaded_data

            loaded_data = data.strip()
            if not loaded_data.startswith("-----BEGIN"):
                logger.warning("📜📂⚠️ Data doesn't look like PEM format")
            return loaded_data
        except Exception as e:
            logger.error(f"📜📂❌ Failed to load data: {e}", extra={"error": str(e)})
            raise CertificateError(f"Failed to load data: {e}") from e

    # Properties
    @property
    def trust_chain(self) -> list["Certificate"]:
        """Returns the list of trusted certificates associated with this one."""
        return self._trust_chain

    @trust_chain.setter
    def trust_chain(self, value: list["Certificate"]) -> None:
        """Sets the list of trusted certificates."""
        self._trust_chain = value

    @cached_property
    def is_valid(self) -> bool:
        """Checks if the certificate is currently valid based on its dates."""
        if not hasattr(self, "_base"):
            return False
        now = datetime.now(UTC)
        valid = self._base.not_valid_before <= now <= self._base.not_valid_after
        return valid

    @property
    def is_ca(self) -> bool:
        """Checks if the certificate has the Basic Constraints CA flag set to True."""
        if not hasattr(self, "_cert"):
            return False
        try:
            ext = self._cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.BASIC_CONSTRAINTS
            )
            if isinstance(ext.value, x509.BasicConstraints):
                return ext.value.ca
            return False
        except x509.ExtensionNotFound:
            logger.debug("📜🔍⚠️ is_ca: Basic Constraints extension not found")
            return False

    @property
    def subject(self) -> str:
        """Returns the certificate subject as an RFC4514 string."""
        if not hasattr(self, "_base"):
            return "SubjectNotInitialized"
        return self._base.subject.rfc4514_string()

    @property
    def issuer(self) -> str:
        """Returns the certificate issuer as an RFC4514 string."""
        if not hasattr(self, "_base"):
            return "IssuerNotInitialized"
        return self._base.issuer.rfc4514_string()

    @property
    def public_key(self) -> "PublicKey | None":
        """Returns the public key object from the certificate."""
        if not hasattr(self, "_base"):
            return None
        return self._base.public_key

    @property
    def serial_number(self) -> int | None:
        """Returns the certificate serial number."""
        if not hasattr(self, "_base"):
            return None
        return self._base.serial_number

    @classmethod
    def create_ca(
        cls,
        common_name: str,
        organization_name: str,
        validity_days: int,
        key_type: str = DEFAULT_CERTIFICATE_KEY_TYPE,
        key_size: int = DEFAULT_RSA_KEY_SIZE,
        ecdsa_curve: str = DEFAULT_CERTIFICATE_CURVE,
    ) -> "Certificate":
        """Creates a new self-signed CA certificate."""
        logger.info(
            f"📜🔑🏭 Creating new CA certificate: CN={common_name}, Org={organization_name}"
        )
        ca_cert_obj = cls(
            generate_keypair=True,
            common_name=common_name,
            organization_name=organization_name,
            validity_days=validity_days,
            key_type=key_type,
            key_size=key_size,
            ecdsa_curve=ecdsa_curve,
            alt_names=[common_name],
        )
        # Re-sign to ensure CA flags are correctly set for a CA
        logger.info("📜🔑🏭 Re-signing generated CA certificate to ensure is_ca=True")
        actual_ca_x509_cert = create_x509_certificate(
            base=ca_cert_obj._base,
            private_key=ca_cert_obj._private_key,
            alt_names=ca_cert_obj.alt_names,
            is_ca=True,
            is_client_cert=False,
        )
        ca_cert_obj._cert = actual_ca_x509_cert
        ca_cert_obj.cert = actual_ca_x509_cert.public_bytes(
            serialization.Encoding.PEM
        ).decode("utf-8")
        return ca_cert_obj

    @classmethod
    def create_signed_certificate(
        cls,
        ca_certificate: "Certificate",
        common_name: str,
        organization_name: str,
        validity_days: int,
        alt_names: list[str] | None = None,
        key_type: str = DEFAULT_CERTIFICATE_KEY_TYPE,
        key_size: int = DEFAULT_RSA_KEY_SIZE,
        ecdsa_curve: str = DEFAULT_CERTIFICATE_CURVE,
        is_client_cert: bool = False,
    ) -> "Certificate":
        """Creates a new certificate signed by the provided CA certificate."""
        logger.info(
            f"📜🔑🏭 Creating new certificate signed by CA '{ca_certificate.subject}': "
            f"CN={common_name}, Org={organization_name}, ClientCert={is_client_cert}"
        )
        if not ca_certificate._private_key:
            raise CertificateError(
                message="CA certificate's private key is not available for signing.",
                hint="Ensure the CA certificate object was loaded or created with its private key.",
            )
        if not ca_certificate.is_ca:
            logger.warning(
                f"📜🔑⚠️ Signing certificate (Subject: {ca_certificate.subject}) "
                "is not marked as a CA. This might lead to validation issues."
            )

        new_cert_obj = cls(
            generate_keypair=True,
            common_name=common_name,
            organization_name=organization_name,
            validity_days=validity_days,
            alt_names=alt_names or [common_name],
            key_type=key_type,
            key_size=key_size,
            ecdsa_curve=ecdsa_curve,
        )

        signed_x509_cert = create_x509_certificate(
            base=new_cert_obj._base,
            private_key=new_cert_obj._private_key,
            alt_names=new_cert_obj.alt_names,
            issuer_name_override=ca_certificate._base.subject,
            signing_key_override=ca_certificate._private_key,
            is_ca=False,
            is_client_cert=is_client_cert,
        )

        new_cert_obj._cert = signed_x509_cert
        new_cert_obj.cert = signed_x509_cert.public_bytes(
            serialization.Encoding.PEM
        ).decode("utf-8")

        logger.info(
            f"📜🔑✅ Successfully created and signed certificate for "
            f"CN={common_name} by CA='{ca_certificate.subject}'"
        )
        return new_cert_obj

    @classmethod
    def create_self_signed_server_cert(
        cls,
        common_name: str,
        organization_name: str,
        validity_days: int,
        alt_names: list[str] | None = None,
        key_type: str = DEFAULT_CERTIFICATE_KEY_TYPE,
        key_size: int = DEFAULT_RSA_KEY_SIZE,
        ecdsa_curve: str = DEFAULT_CERTIFICATE_CURVE,
    ) -> "Certificate":
        """Creates a new self-signed end-entity certificate suitable for a server."""
        logger.info(
            f"📜🔑🏭 Creating new self-signed SERVER certificate: "
            f"CN={common_name}, Org={organization_name}"
        )

        cert_obj = cls(
            generate_keypair=True,
            common_name=common_name,
            organization_name=organization_name,
            validity_days=validity_days,
            alt_names=alt_names or [common_name],
            key_type=key_type,
            key_size=key_size,
            ecdsa_curve=ecdsa_curve,
        )

        if not cert_obj._private_key:
            raise CertificateError(
                "Private key not generated for self-signed server certificate"
            )

        actual_x509_cert = create_x509_certificate(
            base=cert_obj._base,
            private_key=cert_obj._private_key,
            alt_names=cert_obj.alt_names,
            is_ca=False,
            is_client_cert=False,
        )

        cert_obj._cert = actual_x509_cert
        cert_obj.cert = actual_x509_cert.public_bytes(
            serialization.Encoding.PEM
        ).decode("utf-8")

        logger.info(
            f"📜🔑✅ Successfully created self-signed SERVER certificate for CN={common_name}"
        )
        return cert_obj

    def verify_trust(self, other_cert: Self) -> bool:
        """Verifies if the `other_cert` is trusted based on this certificate's trust chain."""
        if other_cert is None:
            raise CertificateError("Cannot verify trust: other_cert is None")

        logger.debug(
            f"📜🔍🚀 Verifying trust for cert S/N {other_cert.serial_number} "
            f"against chain of S/N {self.serial_number}"
        )

        if not other_cert.is_valid:
            logger.debug(
                "📜🔍⚠️ Trust verification failed: Other certificate is not valid"
            )
            return False
        if not other_cert.public_key:
            raise CertificateError(
                "Cannot verify trust: Other certificate has no public key"
            )

        if self == other_cert:
            logger.debug(
                "📜🔍✅ Trust verified: Certificates are identical (based on subject/serial)"
            )
            return True

        if other_cert in self._trust_chain:
            logger.debug(
                "📜🔍✅ Trust verified: Other certificate found in trust chain"
            )
            return True

        for trusted_cert in self._trust_chain:
            logger.debug(
                f"📜🔍🔁 Checking signature against trusted cert S/N {trusted_cert.serial_number}"
            )
            if self._validate_signature(
                signed_cert=other_cert, signing_cert=trusted_cert
            ):
                logger.debug(
                    f"📜🔍✅ Trust verified: Other cert signed by trusted cert S/N "
                    f"{trusted_cert.serial_number}"
                )
                return True

        logger.debug(
            "📜🔍❌ Trust verification failed: Other certificate not identical, "
            "not in chain, and not signed by any cert in chain"
        )
        return False

    def _validate_signature(
        self, signed_cert: "Certificate", signing_cert: "Certificate"
    ) -> bool:
        """Internal helper: Validates signature and issuer/subject match."""
        if not hasattr(signed_cert, "_cert") or not hasattr(signing_cert, "_cert"):
            logger.error(
                "📜🔍❌ Cannot validate signature: Certificate object(s) not initialized"
            )
            return False

        return validate_signature(
            signed_cert._cert, signing_cert._cert, signing_cert.public_key
        )

    def __eq__(self, other: object) -> bool:
        """Custom equality based on subject and serial number."""
        if not isinstance(other, Certificate):
            return NotImplemented
        if not hasattr(self, "_base") or not hasattr(other, "_base"):
            return False
        eq = (
            self._base.subject == other._base.subject
            and self._base.serial_number == other._base.serial_number
        )
        return eq

    def __hash__(self) -> int:
        """Custom hash based on subject and serial number."""
        if not hasattr(self, "_base"):
            logger.warning("📜🔍⚠️ __hash__ called before _base initialized")
            return hash((None, None))

        h = hash((self._base.subject, self._base.serial_number))
        return h

    def __repr__(self) -> str:
        try:
            subject_str = self.subject
            issuer_str = self.issuer
            valid_str = str(self.is_valid)
            ca_str = str(self.is_ca)
        except AttributeError:
            subject_str = "PartiallyInitialized"
            issuer_str = "PartiallyInitialized"
            valid_str = "Unknown"
            ca_str = "Unknown"

        return (
            f"Certificate(subject='{subject_str}', issuer='{issuer_str}', "
            f"common_name='{self.common_name}', valid={valid_str}, ca={ca_str}, "
            f"key_type='{self.key_type}')"
        )


# Convenience functions for common use cases
def create_self_signed(
    common_name: str = "localhost",
    alt_names: list[str] | None = None,
    organization: str = "Default Organization",
    validity_days: int = DEFAULT_CERTIFICATE_VALIDITY_DAYS,
    key_type: str = DEFAULT_CERTIFICATE_KEY_TYPE,
) -> "Certificate":
    """Create a self-signed certificate (convenience function)."""
    _require_crypto()
    return Certificate.create_self_signed_server_cert(
        common_name=common_name,
        organization_name=organization,
        validity_days=validity_days,
        alt_names=alt_names or [common_name],
        key_type=key_type,
    )


def create_ca(
    common_name: str,
    organization: str = "Default CA Organization",
    validity_days: int = DEFAULT_CERTIFICATE_VALIDITY_DAYS * 2,  # CAs live longer
    key_type: str = DEFAULT_CERTIFICATE_KEY_TYPE,
) -> "Certificate":
    """Create a CA certificate (convenience function)."""
    _require_crypto()
    return Certificate.create_ca(
        common_name=common_name,
        organization_name=organization,
        validity_days=validity_days,
        key_type=key_type,
    )