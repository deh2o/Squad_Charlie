from alert_manager import CriticalAlertManager


def _critical(well="WELL-01", score=0.91):
    return {"well_id": well, "score": score, "level": "CRITICAL"}


def _normal(well="WELL-01", score=0.30):
    return {"well_id": well, "score": score, "level": "NORMAL"}


def test_alert_is_raised_only_when_entering_critical():
    manager = CriticalAlertManager()
    assert len(manager.update([_critical()])) == 1
    assert len(manager.update([_critical(score=0.95)])) == 0
    assert len(manager.pending()) == 1


def test_acknowledge_suppresses_repeated_alert_until_condition_clears():
    manager = CriticalAlertManager()
    manager.update([_critical()])
    assert manager.acknowledge("WELL-01") is True
    assert manager.pending() == []
    assert manager.update([_critical(score=0.96)]) == []
    assert manager.update([_normal()]) == []
    assert len(manager.update([_critical(score=0.97)])) == 1


def test_multiple_alerts_are_sorted_by_risk():
    manager = CriticalAlertManager()
    manager.update([_critical("WELL-01", 0.81), _critical("WELL-02", 0.95)])
    assert [x["well_id"] for x in manager.pending()] == ["WELL-02", "WELL-01"]
