from dataclasses import dataclass


class XhsConnectorNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class XhsConnectorStatus:
    mode: str
    configured: bool
    message: str


class XhsConnector:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def status(self) -> XhsConnectorStatus:
        if self.mode == "manual":
            return XhsConnectorStatus(
                mode=self.mode,
                configured=False,
                message=(
                    "Real Xiaohongshu data sync is not configured. Use CSV/XLSX import or "
                    "plug an approved API/provider into this adapter."
                ),
            )
        return XhsConnectorStatus(
            mode=self.mode,
            configured=True,
            message="Connector mode is configured; implement provider-specific sync here.",
        )

    def sync_account(self, platform_uid: str) -> dict[str, str]:
        status = self.status()
        if not status.configured:
            raise XhsConnectorNotConfigured(status.message)
        return {"platform_uid": platform_uid, "status": "queued"}
