"""Non-UI critical alert state management.

Keeps alert lifecycle rules independent from Tkinter so they can be tested
without starting the GUI.
"""
from __future__ import annotations


class CriticalAlertManager:
    """Track critical wells and acknowledgement state.

    A well creates an alert when it enters CRITICAL. Acknowledging it suppresses
    repeats while the well remains critical. If risk falls below CRITICAL and
    later returns to CRITICAL, a new alert is generated.
    """

    def __init__(self) -> None:
        self.active: dict[str, dict] = {}
        self._critical_wells: set[str] = set()

    def update(self, predictions: list[dict]) -> list[dict]:
        """Update state from predictions and return newly raised alerts."""
        current_critical = {
            item["well_id"]: item
            for item in predictions
            if item.get("level") == "CRITICAL"
        }

        # Wells that left CRITICAL can alert again if they return later.
        for well_id in list(self._critical_wells):
            if well_id not in current_critical:
                self._critical_wells.remove(well_id)
                self.active.pop(well_id, None)

        new_alerts = []
        for well_id, item in current_critical.items():
            if well_id not in self._critical_wells:
                alert = dict(item)
                alert["acknowledged"] = False
                self.active[well_id] = alert
                new_alerts.append(alert)
                self._critical_wells.add(well_id)
            elif well_id in self.active:
                # Keep the alert current if the score changes while unacknowledged.
                self.active[well_id].update(item)

        return new_alerts

    def observe(self, item: dict) -> list[dict]:
        """Observe one prediction without changing other wells' lifecycle state."""
        well_id = item["well_id"]
        if item.get("level") != "CRITICAL":
            self._critical_wells.discard(well_id)
            self.active.pop(well_id, None)
            return []
        if well_id in self._critical_wells:
            if well_id in self.active:
                self.active[well_id].update(item)
            return []
        alert = dict(item)
        alert["acknowledged"] = False
        self.active[well_id] = alert
        self._critical_wells.add(well_id)
        return [alert]

    def acknowledge(self, well_id: str) -> bool:
        """Acknowledge an active alert without clearing the critical condition."""
        alert = self.active.get(well_id)
        if not alert:
            return False
        alert["acknowledged"] = True
        self.active.pop(well_id, None)
        return True

    def pending(self) -> list[dict]:
        """Return unacknowledged active alerts ordered by highest risk."""
        return sorted(self.active.values(), key=lambda x: x.get("score", 0), reverse=True)

    def clear(self) -> None:
        self.active.clear()
        self._critical_wells.clear()
