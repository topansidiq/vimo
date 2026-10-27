"""
Heuristic maintenance hints from live machine state (v2 foundation).

Rule-based signals for dashboard and work planning; not a replacement for CMMS or ML models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.models import MachineState


@dataclass
class MaintenanceInsight:
    machine_id: str
    name: str
    priority: str
    summary: str
    suggested_action: str

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "priority": self.priority,
            "summary": self.summary,
            "suggested_action": self.suggested_action,
        }


def build_insights(machines: List[MachineState]) -> List[MaintenanceInsight]:
    """Derive a short ranked list of maintenance-oriented hints."""
    insights: List[MaintenanceInsight] = []

    for m in machines:
        st = m.status
        if st == "Critical":
            insights.append(
                MaintenanceInsight(
                    machine_id=m.machine_id,
                    name=m.name or m.machine_id,
                    priority="high",
                    summary="Status operasi kritis; getaran atau gyro di luar batas aman.",
                    suggested_action="Jadwalkan inspeksi segera; catat work order dan verifikasi mekanikal.",
                )
            )
        elif st == "Warning":
            insights.append(
                MaintenanceInsight(
                    machine_id=m.machine_id,
                    name=m.name or m.machine_id,
                    priority="medium",
                    summary="Pola sensor menunjukkan degradasi atau aktivitas di atas baseline.",
                    suggested_action="Rencanakan pemeriksaan preventif; tinjau riwayat alarm dan suku cadang.",
                )
            )
        elif m.alert_count >= 8 and st in ("Normal", "Idle"):
            insights.append(
                MaintenanceInsight(
                    machine_id=m.machine_id,
                    name=m.name or m.machine_id,
                    priority="low",
                    summary=f"Banyak event alarm terkumpul ({m.alert_count}) meski status saat ini stabil.",
                    suggested_action="Tinjau akar masalah historis; pertimbangkan kalibrasi ulang atau jadwal servis.",
                )
            )

    order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: order.get(x.priority, 9))
    return insights[:8]
