from dataclasses import dataclass


class XhsConnectorNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class XhsConnectorStatus:
    mode: str
    configured: bool
    message: str


class XhsConnector:
    """Xiaohongshu data connector.

    STUB: real third-party API integration (Pugongying / official OAuth / scrape-protected
    endpoints) is intentionally out of scope for the MVP. The class exists so the rest of
    the system has a stable adapter to call once a provider is plugged in. Do not advertise
    sync behavior to end-users until a real provider is implemented.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def status(self) -> XhsConnectorStatus:
        if self.mode == "manual":
            return XhsConnectorStatus(
                mode=self.mode,
                configured=False,
                message=(
                    "Xiaohongshu data sync is a stub in MVP. Use CSV/XLSX import or "
                    "plug an approved provider into XhsConnector."
                ),
            )
        return XhsConnectorStatus(
            mode=self.mode,
            configured=False,
            message="Connector mode is set but no provider is implemented yet (MVP stub).",
        )

    def sync_account(self, platform_uid: str) -> dict[str, str]:
        # Always raises in MVP — no real provider implemented.
        raise XhsConnectorNotConfigured(self.status().message)

