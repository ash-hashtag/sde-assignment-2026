"""Per-workflow view of the world for one controller tick."""
from __future__ import annotations

from dataclasses import dataclass, field

from .simtime import MIN_PER_DAY
from .store import Store


@dataclass
class WorkflowCtx:
    wf: str
    spec: dict                      # GET /workflows/{id}
    config: dict                    # current config
    version: int
    now: int                        # sim minute
    store: Store
    supervisor_dims: dict = field(default_factory=dict)   # dim -> minute of the last supervisor edit
    end: int | None = None          # scenario end minute if known (production has none)

    @property
    def tenant(self) -> str:
        return self.spec["tenant_id"]

    @property
    def gov(self) -> dict:
        return self.spec["governance"]

    @property
    def options(self) -> dict:
        return self.spec["options"]

    @property
    def window(self) -> tuple[int, int]:
        lo, hi = self.spec["dialling_window"]
        return lo, hi

    @property
    def hour(self) -> int:
        return (self.now % MIN_PER_DAY) // 60

    @property
    def day(self) -> int:
        return self.now // MIN_PER_DAY

    @property
    def primary(self) -> str:
        return self.spec["objective"]["primary"]

    def in_window(self) -> bool:
        lo, hi = self.window
        return lo <= self.hour < hi

    def auto_allowed(self, dim: str) -> bool:
        aa = self.gov.get("auto_apply") or {}
        return bool(aa.get("enabled")) and dim in (aa.get("allowed_dims") or [])

    def locked_by_supervisor(self, dim: str, hours: float) -> bool:
        t = self.supervisor_dims.get(dim)
        return t is not None and self.now - t < hours * 60

    def active_leads(self) -> int:
        """Leads in campaigns still inside their cadence, minus those already concluded."""
        n_days = len(self.spec["cadence"])
        r = self.store.q1("SELECT COALESCE(SUM(leads - concluded), 0) FROM campaigns WHERE wf=? AND day > ?",
                          (self.wf, self.day - n_days))
        return int(r or 0)

    def hour_keys(self, hours_back: int) -> list[tuple[int, int]]:
        """(day, hour) buckets covering the last `hours_back` *complete* dialling hours plus the current, partial one,
        newest first. (At 13:00 the 13h bucket is empty, so "the last hour" must reach back to 12h.)"""
        lo, hi = self.window
        out = []
        h_abs = self.now // 60
        cur = divmod(h_abs, 24)
        want = hours_back + (1 if lo <= cur[1] < hi else 0)
        while len(out) < want and h_abs > self.now // 60 - 24 * 14:
            d, h = divmod(h_abs, 24)
            if lo <= h < hi:
                out.append((d, h))
            h_abs -= 1
        return out
