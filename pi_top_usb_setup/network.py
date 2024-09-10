import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from pitop.common.command_runner import run_command

from pi_top_usb_setup.utils import get_linux_distro

logger = logging.getLogger(__name__)


CERT_FOLDER = "/usr/local/share/ca-certificates"

#################################
# Enums
#################################


class WiFiSecurityEnum(Enum):
    LEAP = auto()
    OWE = auto()
    OPEN = auto()
    WPA_ENTERPRISE = auto()
    WPA_PERSONAL = auto()


class WpaEnterpriseAuthentication(Enum):
    PWD = auto()
    TLS = auto()
    TTLS = auto()
    PEAP = auto()


class TTLSInnerAuthentication(Enum):
    PAP = auto()
    MSCHAP = auto()
    MSCHAPv2 = auto()
    MSCHAPv2_no_EAP = auto()
    CHAP = auto()
    MD5 = auto()
    GTC = auto()


class PEAPVersion(Enum):
    AUTOMATIC = auto()
    VERSION0 = 0
    VERSION1 = 1


class PEAPInnerAuthentication(Enum):
    MSCHAPv2 = auto()
    MD5 = auto()
    GTC = auto()


#################################
# Helpers
#################################
@dataclass
class NetworkBase:

    def __post_init__(self):
        # Check type of dataclass fields
        for name, field_type in self.__annotations__.items():
            if not isinstance(self.__dict__[name], field_type):
                current_type = type(self.__dict__[name])
                raise TypeError(
                    f"Field '{name}' was provided as '{current_type}' but should be '{field_type}'"
                )

    @classmethod
    def cleanup(cls, **kwargs) -> dict:
        # Remove any keys from kwargs that are not part of the dataclass
        return {
            key: value for key, value in kwargs.items() if key in cls.__annotations__
        }


@dataclass
class File:
    filename: str
    content: str
    folder: str

    @classmethod
    def from_dict(cls, data: dict):
        return File(
            filename=data["filename"],
            content=data["content"],
            folder=data.get("folder", CERT_FOLDER),
        )

    @property
    def path(self):
        return f"{self.folder}/{self.filename}"

    def save(self):
        run_command(f"mkdir -p {self.folder}", timeout=10, check=True)
        logger.info(f"Saving content to file: '{self.path}', content: '{self.content}'")
        with open(f"{self.path}", "w") as f:
            f.write(self.content)


def runs_without_error(cmd):
    logger.info(f"Checking if command '{cmd}' runs without errors...")
    try:
        run_command(cmd, timeout=10, check=True)
        return True
    except Exception as e:
        logger.warning(f"Command '{cmd}' failed: {e}")
        return False


#################################
# Authentication classes
#################################
@dataclass
class PWDAuthentication(NetworkBase):
    username: str
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        logger.info(f"----------------> PWDAuthentication: {kwargs}")
        return PWDAuthentication(**cls.cleanup(**kwargs))

    def to_nmcli(self) -> str:
        response = f'key-mgmt wpa-eap \
802-1x.eap pwd \
802-1x.identity "{self.username}"'
        if self.password:
            response += f' 802-1x.password "{self.password}"'
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = []
        response.append("key_mgmt=WPA-EAP")
        response.append("eap=PWD")
        response.append(f'identity="{self.username}"')
        if self.password:
            response.append(f'password="{self.password}"')
        return response


@dataclass
class TLSAuthentication(NetworkBase):
    identity: str
    user_private_key: File
    domain: Optional[str] = None
    ca_cert: Optional[File] = None
    ca_cert_password: Optional[str] = None
    user_cert: Optional[File] = None
    user_cert_password: Optional[str] = None
    user_private_key_password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        logger.info(f"----------------> TLSAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)
        # 'user_cert', 'ca_cert' and 'user_private_key' contain keys; need to save them to files and pass the paths to the constructor
        args["user_private_key"] = File.from_dict(args["user_private_key"])
        args["user_private_key"].save()
        if "user_cert" in args:
            args["user_cert"] = File.from_dict(args["user_cert"])
            args["user_cert"].save()
        if "ca_cert" in args:
            args["ca_cert"] = File.from_dict(args["ca_cert"])
            args["ca_cert"].save()
        return TLSAuthentication(**cls.cleanup(**args))

    def to_nmcli(self) -> str:
        response = f'802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap tls \
802-1x.identity "{self.identity}" \
802-1x.private-key "{self.user_private_key.path}"'
        if self.domain:
            response += f' 802-1x.domain-suffix-match "{self.domain}"'
        if self.ca_cert:
            response += f' 802-1x.ca-cert "{self.ca_cert.path}"'
        if self.ca_cert_password:
            response += f' 802-1x.ca-cert-password "{self.ca_cert_password}"'
        if self.user_cert:
            response += f' 802-1x.client-cert "{self.user_cert.path}"'
        if self.user_cert_password:
            response += f' 802-1x.client-cert-password "{self.user_cert_password}"'
        if self.user_private_key_password:
            response += (
                f' 802-1x.private-key-password "{self.user_private_key_password}"'
            )
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = [
            "key_mgmt=WPA-EAP",
            "eap=TLS",
            f'identity="{self.identity}"',
            f'private_key="{self.user_private_key.path}"',
        ]
        if self.domain:
            response.append(f'domain_suffix_match="{self.domain}"')
        if self.ca_cert:
            response.append(f'ca_cert="{self.ca_cert.path}"')
        # if self.ca_cert_password:
        #     response.append(f"ca_cert_password=\"{self.ca_cert_password}\""
        if self.user_cert:
            response.append(f'client_cert="{self.user_cert.path}"')
        # if self.user_cert_password:
        #     response.append(f"client_cert_password=\"{self.user_cert_password}\""
        if self.user_private_key_password:
            response.append(f'private_key_passwd="{self.user_private_key_password}"')
        return response


@dataclass
class TTLSAuthentication(NetworkBase):
    username: str
    inner_authentication: TTLSInnerAuthentication
    anonymous_identity: str
    ca_cert: Optional[File] = None
    ca_cert_password: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        logger.info(f"----------------> TTLSAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)
        args["inner_authentication"] = TTLSInnerAuthentication[
            kwargs["inner_authentication"]
        ]
        if "ca_cert" in args:
            args["ca_cert"] = File.from_dict(args["ca_cert"])
            args["ca_cert"].save()
        if "anonymous_identity" not in args:
            args["anonymous_identity"] = ""
        return TTLSAuthentication(**args)

    def to_nmcli(self) -> str:
        response = f'802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap ttls \
802-1x.anonymous-identity "{self.anonymous_identity}" \
802-1x.identity "{self.username}" \
802-1x.phase2-auth {self.inner_authentication.name}'
        if self.ca_cert:
            response += f' 802-1x.ca-cert "{self.ca_cert.path}"'
        if self.ca_cert_password:
            response += f' 802-1x.ca-cert-password "{self.ca_cert_password}"'
        if self.password:
            response += f' 802-1x.password "{self.password}"'
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = [
            "key_mgmt=WPA-EAP",
            "eap=TTLS",
            f'anonymous_identity="{self.anonymous_identity}"',
            f'identity="{self.username}"',
            f'phase2="auth={self.inner_authentication.name}"',
        ]
        if self.ca_cert:
            response.append(f'ca_cert="{self.ca_cert.path}"')
        # if self.ca_cert_password:
        #     response.append(f"ca_cert_password=\"{self.ca_cert_password}\"")
        if self.password:
            response.append(f'password="{self.password}"')
        return response


@dataclass
class PEAPAuthentication(NetworkBase):
    username: str
    inner_authentication: PEAPInnerAuthentication = PEAPInnerAuthentication.MSCHAPv2
    peap_version: PEAPVersion = PEAPVersion.AUTOMATIC
    anonymous_identity: Optional[str] = None
    domain: Optional[str] = None
    ca_cert: Optional[File] = None
    ca_cert_password: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        logger.info(f"----------------> PEAPAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)

        args["inner_authentication"] = PEAPInnerAuthentication[
            kwargs.pop("inner_authentication", "MSCHAPv2")
        ]
        args["peap_version"] = PEAPVersion[kwargs.pop("peap_version", "AUTOMATIC")]
        if "ca_cert" in args:
            args["ca_cert"] = File.from_dict(args["ca_cert"])
            args["ca_cert"].save()
        return PEAPAuthentication(**args)

    def to_nmcli(self) -> str:
        response = f'802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap peap \
802-1x.identity "{self.username}" \
802-1x.phase2-auth {self.inner_authentication.name}'
        if self.anonymous_identity:
            response += f' 802-1x.anonymous-identity "{self.anonymous_identity}"'
        if self.peap_version != PEAPVersion.AUTOMATIC:
            response += f" 802-1x.phase1-peapver {self.peap_version.value}"
        if self.domain:
            response += f' 802-1x.domain-suffix-match "{self.domain}"'
        if self.ca_cert:
            response += f' 802-1x.ca-cert ”{self.ca_cert.path}"'
        if self.ca_cert_password:
            response += f' 802-1x.ca-cert-password "{self.ca_cert_password}"'
        if self.password:
            response += f' 802-1x.password "{self.password}"'
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = [
            "key_mgmt=WPA-EAP",
            'eap="PEAP"',
            f'anonymous_identity="{self.anonymous_identity}"',
            f'identity="{self.username}"',
            f'phase2="{self.inner_authentication.name}"',
        ]
        if self.peap_version != PEAPVersion.AUTOMATIC:
            response.append(f'phase1="{self.peap_version.value}"')
        if self.domain:
            response.append(f'domain_suffix_match="{self.domain}"')
        if self.ca_cert:
            response.append(f'ca_cert="{self.ca_cert.path}"')
        if self.ca_cert_password:
            response.append(f'ca_cert_password="{self.ca_cert_password}"')
        if self.password:
            response.append(f'password="{self.password}"')
        return response


#################################
# WiFi Security classes
#################################
@dataclass
class WpaPersonal(NetworkBase):
    password: str

    def to_nmcli(self) -> str:
        return f'mode infra \
802-11-wireless-security.key-mgmt wpa-psk \
802-11-wireless-security.psk "{self.password}"'

    def to_wpasupplicant_conf(self) -> List:
        return [
            "key-mgmt=WPA-PSK",
            f'psk="{self.password}"',
        ]


@dataclass
class LEAP(NetworkBase):
    username: str
    password: Optional[str] = None

    def to_nmcli(self) -> str:
        response = f'802-11-wireless-security.auth-alg leap \
802-11-wireless-security.key-mgmt ieee8021x \
802-11-wireless-security.leap-username "{self.username}"'
        if self.password:
            response += f'802-11-wireless-security.leap-password "{self.password}"'
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = [
            "auth_alg=LEAP",
            "key_mgmt=IEEE8021X",
            f'identity="{self.username}"',
        ]
        if self.password:
            response.append(f'password="{self.password}"')
        return response


class OWE:

    def to_nmcli(self) -> str:
        return "802-11-wireless-security.key-mgmt OWE"

    def to_wpasupplicant_conf(self) -> List:
        return ["key_mgmt=OWE"]


@dataclass
class Open(NetworkBase):

    def to_nmcli(self) -> str:
        return ""

    def to_wpasupplicant_conf(self) -> List:
        return []


@dataclass()
class WpaEnterprise(NetworkBase):
    authentication: (
        PWDAuthentication | TLSAuthentication | TTLSAuthentication | PEAPAuthentication
    )

    @classmethod
    def from_kwargs(cls, **kwargs):
        logger.info(f"--------> WpaEnterprise: {kwargs}")
        authentication_lookup = {
            WpaEnterpriseAuthentication.PWD: PWDAuthentication,
            WpaEnterpriseAuthentication.TLS: TLSAuthentication,
            WpaEnterpriseAuthentication.TTLS: TTLSAuthentication,
            WpaEnterpriseAuthentication.PEAP: PEAPAuthentication,
        }
        try:
            authentication_type = kwargs["authentication"]
            authentication_enum = WpaEnterpriseAuthentication[authentication_type]
            authentication_cls = authentication_lookup[authentication_enum]
        except KeyError:
            raise ValueError(f"Invalid authentication type '{authentication_type}'")

        return WpaEnterprise(authentication=authentication_cls.from_kwargs(**kwargs))

    def to_nmcli(self) -> str:
        return self.authentication.to_nmcli()

    def to_wpasupplicant_conf(self) -> List:
        return self.authentication.to_wpasupplicant_conf()


#################################
# Main class
#################################


@dataclass
class Network:
    ssid: str
    authentication: WpaPersonal | LEAP | OWE | WpaEnterprise
    hidden: bool = False

    @property
    def name(self) -> str:
        # A connection file is created in /etc/NetworkManager/system-connections/ with the name of the connection
        return "PT-USB-SETUP-" + self.ssid.replace(" ", "_").replace('"', "")

    def should_connect_with_raspi_config(self):
        return any(
            [
                isinstance(self.authentication, WpaPersonal),
                isinstance(self.authentication, OWE),
                isinstance(self.authentication, Open),
            ]
        )

    def connect(self):
        cmds = []
        if self.should_connect_with_raspi_config():
            # On simple networks, we'll connect using raspi-config
            # https://www.raspberrypi.com/documentation/computers/configuration.html#system-options36
            plain = 0
            password = (
                ""
                if isinstance(self.authentication, OWE)
                or isinstance(self.authentication, Open)
                else f'"{self.authentication.password}"'
            )
            cmds.append(
                f'raspi-config nonint do_wifi_ssid_passphrase "{self.ssid}" {password} {int(self.hidden)} {plain}'
            )
        elif get_linux_distro() == "bookworm":
            if self.exists():
                # disconnect and delete existing connection
                cmds.append(f'nmcli connection down "{self.name}"')
                cmds.append(f'nmcli connection delete "{self.name}"')

            cmds.append(self.to_nmcli())
            cmds.append(f'nmcli connection up "{self.name}"')
        else:
            cmd = self.to_wpasupplicant_conf()
            # append to wpa_supplicant.conf
            with open("/etc/wpa_supplicant/wpa_supplicant.conf", "a") as f:
                f.write("\n")
                f.write("\n".join(cmd))
            cmds.append("systemctl restart wpa_supplicant")

        logger.info("--> Connecting to network")
        for cmd in cmds:
            logger.info(f"--> Executing: {cmd}")
            try:
                run_command(cmd, timeout=30, check=True)
            except Exception as e:
                logger.error(f"Error connecting: {e}")

    def exists(self):
        if get_linux_distro() == "bookworm":
            return runs_without_error(f'nmcli connection show "{self.name}"')
        else:
            with open("/etc/wpa_supplicant/wpa_supplicant.conf", "r") as f:
                return f"ssid={self.ssid}" in f.read()

    @classmethod
    def from_dict(cls, data: dict):
        logger.info(f"--> Network: {data}")
        return Network(
            authentication=Network.get_authentication(data["authentication"]),
            ssid=data["ssid"],
            hidden=data.get("hidden", False),
        )

    @staticmethod
    def get_authentication(
        auth_dict: dict,
    ) -> WpaPersonal | LEAP | OWE | WpaEnterprise:
        lookup = {
            WiFiSecurityEnum.LEAP: LEAP,
            WiFiSecurityEnum.OPEN: Open,
            WiFiSecurityEnum.OWE: OWE,
            WiFiSecurityEnum.WPA_ENTERPRISE: lambda **kwargs: WpaEnterprise.from_kwargs(
                **kwargs
            ),
            WiFiSecurityEnum.WPA_PERSONAL: WpaPersonal,
        }
        wifi_security_enum = WiFiSecurityEnum[auth_dict["type"]]
        wifi_security_class = lookup[wifi_security_enum]

        assert callable(wifi_security_class)
        return wifi_security_class(**auth_dict.get("data", {}))

    def to_nmcli(self) -> str:
        interface = "wlan0"
        response = f'nmcli connection add type wifi ifname {interface} con-name "{self.name}" ssid "{self.ssid}"'
        if self.hidden:
            response += " 802-11-wireless.hidden yes"
        response += f" {self.authentication.to_nmcli()}"
        return response

    def to_wpasupplicant_conf(self) -> str:
        response = "network {"
        response += f'\n        ssid="{self.ssid}"'
        if self.hidden:
            response += "\n        scan_ssid=1"
        for line in self.authentication.to_wpasupplicant_conf():
            response += f"\n        {line}"
        response += "\n}"
        return response
