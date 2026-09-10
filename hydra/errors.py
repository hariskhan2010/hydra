"""hydra error types. All user-facing failures raise HydraError so the CLI can
print one clean line and exit non-zero — principle B5 (no silent failures)."""


class HydraError(Exception):
    """A problem the user needs to fix (bad task file, dependency cycle, …)."""
