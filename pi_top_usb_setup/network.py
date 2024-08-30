from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional
from uuid import uuid4

CERT_FOLDER = "/usr/local/share/ca-certificates/"

#################################
# Enums
#################################


class WiFiSecurityEnum(Enum):
    LEAP = auto()
    OWE = auto()
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
        return {
            key: value for key, value in kwargs.items() if key in cls.__annotations__
        }

    @classmethod
    def handle_filesystem_path_arg(cls, key: str, args: dict) -> None:
        if key in args:
            filename = generate_filename()
            save_to_file(filename, args[key])
            args[key] = filename


def save_to_file(filename: str, content: str):
    # mkdir -p /usr/local/share/ca-certificates/
    print(f"Saving content to file: {filename}, content: {content}")
    with open(filename, "w") as f:
        f.write(content)


def generate_filename():
    return f"{CERT_FOLDER}/pt_usb_network_{uuid4()}.crt"


#################################
# Authentication classes
#################################
@dataclass
class PWDAuthentication(NetworkBase):
    username: str
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        print(f"----------------> PWDAuthentication: {kwargs}")
        return PWDAuthentication(**cls.cleanup(**kwargs))

    def to_nmcli(self) -> str:
        response = f"key-mgmt wpa-eap \
802-1x.eap pwd \
802-1x.identity {self.username}"
        if self.password:
            response += f" 802-1x.password {self.password}"
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
    user_private_key: str
    domain: Optional[str] = None
    ca_cert: Optional[str] = None
    ca_cert_password: Optional[str] = None
    user_cert: Optional[str] = None
    user_cert_password: Optional[str] = None
    user_private_key_password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        print(f"----------------> TLSAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)
        # 'ca_cert' and 'user_private_key' contain keys; need to save them to files and pass the paths to the constructor
        TLSAuthentication.handle_filesystem_path_arg("user_private_key", args)
        if "ca_cert" in args:
            TLSAuthentication.handle_filesystem_path_arg("ca_cert", args)
        return TLSAuthentication(**cls.cleanup(**args))

    def to_nmcli(self) -> str:
        response = f"802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap tls \
802-1x.identity {self.identity} \
802-1x.private-key {self.user_private_key}"
        if self.domain:
            response += f" 802-1x.domain-suffix-match {self.domain}"
        if self.ca_cert:
            response += f" 802-1x.ca-cert {self.ca_cert}"
        if self.ca_cert_password:
            response += f" 802-1x.ca-cert-password {self.ca_cert_password}"
        if self.user_cert:
            response += f" 802-1x.client-cert {self.user_cert}"
        if self.user_cert_password:
            response += f" 802-1x.client-cert-password {self.user_cert_password}"
        if self.user_private_key_password:
            response += f" 802-1x.private-key-password {self.user_private_key_password}"
        return response

    def to_wpasupplicant_conf(self) -> List:
        response = [
            "key_mgmt=WPA-EAP",
            "eap=TLS",
            f'identity="{self.identity}"',
            f'private_key="{self.user_private_key}"',
        ]
        if self.domain:
            response.append(f'domain_suffix_match="{self.domain}"')
        if self.ca_cert:
            response.append(f'ca_cert="{self.ca_cert}"')
        # if self.ca_cert_password:
        #     response.append(f"ca_cert_password=\"{self.ca_cert_password}\""
        if self.user_cert:
            response.append(f'client_cert="{self.user_cert}"')
        # if self.user_cert_password:
        #     response.append(f"client_cert_password=\"{self.user_cert_password}\""
        if self.user_private_key_password:
            response.append(f'private_key_passwd="{self.user_private_key_password}"')
        return response


@dataclass
class TTLSAuthentication(NetworkBase):
    anonymous_identity: str
    username: str
    inner_authentication: TTLSInnerAuthentication
    ca_cert: Optional[str] = None
    ca_cert_password: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        print(f"----------------> TTLSAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)
        args["inner_authentication"] = TTLSInnerAuthentication[
            kwargs["inner_authentication"]
        ]
        if "ca_cert" in args:
            TTLSAuthentication.handle_filesystem_path_arg("ca_cert", args)
        return TTLSAuthentication(**args)

    def to_nmcli(self) -> str:
        response = f"802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap ttls \
802-1x.anonymous-identity {self.anonymous_identity} \
802-1x.identity {self.username} \
802-1x.phase2-auth {self.inner_authentication.name}"
        if self.ca_cert:
            response += f" 802-1x.ca-cert {self.ca_cert}"
        if self.ca_cert_password:
            response += f" 802-1x.ca-cert-password {self.ca_cert_password}"
        if self.password:
            response += f" 802-1x.password {self.password}"
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
            response.append(f'ca_cert="{self.ca_cert}"')
        # if self.ca_cert_password:
        #     response.append(f"ca_cert_password=\"{self.ca_cert_password}\"")
        if self.password:
            response.append(f'password="{self.password}"')
        return response


@dataclass
class PEAPAuthentication(NetworkBase):
    anonymous_identity: str
    username: str
    inner_authentication: PEAPInnerAuthentication
    peap_version: PEAPVersion = PEAPVersion.AUTOMATIC
    domain: Optional[str] = None
    ca_cert: Optional[str] = None
    ca_cert_password: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_kwargs(cls, **kwargs):
        print(f"----------------> PEAPAuthentication: {kwargs}")
        args = cls.cleanup(**kwargs)
        args["inner_authentication"] = PEAPInnerAuthentication[
            kwargs.pop("inner_authentication")
        ]
        peap_version = kwargs.pop("peap_version", "AUTOMATIC")
        args["peap_version"] = PEAPVersion[peap_version]
        if "ca_cert" in args:
            PEAPAuthentication.handle_filesystem_path_arg("ca_cert", args)
        return PEAPAuthentication(**args)

    def to_nmcli(self) -> str:
        response = f"802-11-wireless-security.key-mgmt wpa-eap \
802-1x.eap peap \
802-1x.anonymous-identity {self.anonymous_identity} \
802-1x.identity {self.username} \
802-1x.phase2-auth {self.inner_authentication.name}"
        if self.peap_version != PEAPVersion.AUTOMATIC:
            response += f"802-1x.phase1-peapver {self.peap_version.value}"
        if self.domain:
            response += f" 802-1x.domain-suffix-match {self.domain}"
        if self.ca_cert:
            response += f" 802-1x.ca-cert {self.ca_cert}"
        if self.ca_cert_password:
            response += f" 802-1x.ca-cert-password {self.ca_cert_password}"
        if self.password:
            response += f" 802-1x.password {self.password}"
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
            response.append(f'ca_cert="{self.ca_cert}"')
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
        return f"mode infa \
802-11-wireless-security.key-mgmt wpa-psk \
802-11-wireless-security.psk {self.password}"

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
        response = f"802-11-wireless-security.auth-alg leap \
802-11-wireless-security.key-mgmt ieee8021x \
802-11-wireless-security.leap-username {self.username}"
        if self.password:
            response += f"802-11-wireless-security.leap-password {self.password}"
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


@dataclass
class OWE:
    def to_nmcli(self) -> str:
        return "802-11-wireless-security.key-mgmt OWE"

    def to_wpasupplicant_conf(self) -> List:
        return ["key_mgmt=OWE"]


@dataclass()
class WpaEnterprise(NetworkBase):
    authentication: (
        PWDAuthentication | TLSAuthentication | TTLSAuthentication | PEAPAuthentication
    )

    @classmethod
    def from_kwargs(cls, **kwargs):
        print(f"--------> WpaEnterprise: {kwargs}")
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

    def connect(self):
        if not (
            isinstance(self.authentication, WpaPersonal)
            or isinstance(self.authentication, OWE)
        ):
            raise NotImplementedError(
                f"Connection type '{self.authentication}' not supported"
            )

        from pitop.common.command_runner import run_command

        # On simple networks, we'll connect using raspi-config
        # https://www.raspberrypi.com/documentation/computers/configuration.html#system-options36
        plain = 0
        password = (
            ""
            if isinstance(self.authentication, OWE)
            else f'"{self.authentication.password}"'
        )
        cmd = f'raspi-config nonint do_wifi_ssid_passphrase "{self.ssid}" {password} {int(self.hidden)} {plain}'
        print(f"--> Connecting to network: {cmd}")
        run_command(cmd, timeout=30, check=True)

    @classmethod
    def from_dict(cls, data: dict):
        print(f"--> Network: {data}")
        return Network(
            authentication=Network.auth_from_dict(data["authentication"]),
            ssid=data["ssid"],
            hidden=data.get("hidden", False),
        )

    @staticmethod
    def auth_from_dict(
        authentication_data: dict,
    ) -> WpaPersonal | LEAP | OWE | WpaEnterprise:
        lookup = {
            WiFiSecurityEnum.LEAP: LEAP,
            WiFiSecurityEnum.OWE: OWE,
            WiFiSecurityEnum.WPA_ENTERPRISE: lambda **kwargs: WpaEnterprise.from_kwargs(
                **kwargs
            ),
            WiFiSecurityEnum.WPA_PERSONAL: WpaPersonal,
        }
        wifi_security_enum = WiFiSecurityEnum[authentication_data.get("type", "")]
        wifi_security_class = lookup[wifi_security_enum]
        args = authentication_data.get("data", {})
        print(f"----> {wifi_security_enum} with {args}")
        assert callable(wifi_security_class)
        return wifi_security_class(**args)

    def to_nmcli(self) -> str:
        response = (
            f"nmcli connection add type wifi con-name {self.ssid} ssid {self.ssid}"
        )
        if self.hidden:
            response += " 802-11-wireless.hidden yes"
        response += f" {self.authentication.to_nmcli()}"
        return response

    def to_wpasupplicant_conf(self) -> str:
        response = "network {"
        for line in self.authentication.to_wpasupplicant_conf():
            response += f"\n        {line}"
        response += "\n}"
        return response
