"""Pipeline errors."""


class AgentContractError(Exception):
    """Raised when structured agent output fails schema/contract validation."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.details = details
