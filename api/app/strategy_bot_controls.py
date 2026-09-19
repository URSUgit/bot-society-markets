"""State transitions for operator-controlled strategy deployments.

Blocked and killed deployments require a fresh deployment and its validations.
Operator controls must never clear a safety block, including through pause.
"""

from __future__ import annotations


def strategy_bot_control_updates(
    *,
    current_status: str,
    kill_switch_active: bool,
    action: str,
    reason: str,
    now: str,
) -> dict[str, object | None]:
    if action not in {"pause", "resume", "kill"}:
        raise ValueError("Unsupported strategy bot control action")

    if action != "kill":
        verb = "paused" if action == "pause" else "resumed"
        if current_status == "killed":
            raise ValueError(f"Killed strategy bots cannot be {verb}. Deploy the strategy again.")
        if current_status == "blocked" or kill_switch_active:
            raise ValueError(
                f"Blocked strategy bots cannot be {verb}. Resolve the blockers and deploy "
                "the strategy again to repeat the deployment validations."
            )
        if current_status not in {"active", "paused", "stopped"}:
            raise ValueError("Unknown strategy bot status. Deploy the strategy again.")

    status, message = {
        "pause": ("paused", "Paused"),
        "resume": ("active", "Resumed"),
        "kill": ("killed", "Kill switch active"),
    }[action]
    return {
        "status": status,
        "kill_switch_active": action == "kill",
        "message": f"{message}: {reason}",
        "updated_at": now,
        "stopped_at": now if action == "kill" else None,
    }
