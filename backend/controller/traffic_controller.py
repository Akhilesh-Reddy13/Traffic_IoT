"""
Traffic signal controller for a 2-direction intersection.
Allocates green time proportionally based on vehicle density per lane.
"""
import time
import threading


class TrafficSignal:
    """State of a single traffic signal."""

    def __init__(self, lane_id, name):
        self.lane_id = lane_id
        self.name = name
        self.state = "red"            # "green" | "yellow" | "red"
        self.green_time = 10          # allocated green seconds
        self.time_remaining = 0.0


class TrafficController:
    """
    Two-phase controller: Direction A green → yellow → all-red → Direction B green → …
    Green time per phase is proportional to that lane's vehicle count.
    """

    def __init__(self, lane_ids, min_green=10, max_green=60,
                 yellow_time=3, all_red_time=2):
        self.signals = {}
        for lid in lane_ids:
            self.signals[lid] = TrafficSignal(lid, lid)

        self.min_green = min_green
        self.max_green = max_green
        self.yellow_time = yellow_time
        self.all_red_time = all_red_time

        self.phase_order = list(lane_ids)
        self.current_phase_idx = 0
        self.phase_state = "green"     # "green" | "yellow" | "all_red"
        self.phase_start = time.time()
        self.lock = threading.Lock()

        # Start first phase
        self._apply_phase(0, "green")

    # ── Internal ────────────────────────────────────────────────

    def _apply_phase(self, idx, state):
        with self.lock:
            self.current_phase_idx = idx
            self.phase_state = state
            self.phase_start = time.time()
            active_lane = self.phase_order[idx]

            for lid, sig in self.signals.items():
                if lid == active_lane:
                    sig.state = state if state != "all_red" else "red"
                else:
                    sig.state = "red"

    # ── Public API ──────────────────────────────────────────────

    def update_green_times(self, vehicle_counts):
        """Recalculate green durations from latest vehicle counts."""
        total = sum(vehicle_counts.values())
        n = len(self.phase_order)

        if total == 0:
            for sig in self.signals.values():
                sig.green_time = self.min_green
            return

        # Dynamic cycle length scales with density
        clearance = (self.yellow_time + self.all_red_time) * n
        base_cycle = max(30, min(120, total * 5 + 20))
        total_green = base_cycle - clearance

        for lid, sig in self.signals.items():
            ratio = vehicle_counts.get(lid, 0) / total
            g = ratio * total_green
            sig.green_time = round(max(self.min_green, min(self.max_green, g)), 1)

    def tick(self):
        """Advance the state machine. Call this every processing loop iteration."""
        elapsed = time.time() - self.phase_start
        active_lane = self.phase_order[self.current_phase_idx]
        sig = self.signals[active_lane]

        if self.phase_state == "green":
            sig.time_remaining = max(0, sig.green_time - elapsed)
            if elapsed >= sig.green_time:
                self._apply_phase(self.current_phase_idx, "yellow")

        elif self.phase_state == "yellow":
            sig.time_remaining = max(0, self.yellow_time - elapsed)
            if elapsed >= self.yellow_time:
                self._apply_phase(self.current_phase_idx, "all_red")

        elif self.phase_state == "all_red":
            if elapsed >= self.all_red_time:
                nxt = (self.current_phase_idx + 1) % len(self.phase_order)
                self._apply_phase(nxt, "green")

        return self.get_state()

    def get_state(self):
        """Snapshot of all signals for the dashboard."""
        with self.lock:
            return {
                "current_phase": self.phase_order[self.current_phase_idx],
                "phase_state": self.phase_state,
                "signals": {
                    lid: {
                        "name": sig.name,
                        "state": sig.state,
                        "green_time": sig.green_time,
                        "time_remaining": round(
                            max(0, sig.green_time - (time.time() - self.phase_start))
                            if sig.state == "green" else
                            max(0, self.yellow_time - (time.time() - self.phase_start))
                            if sig.state == "yellow" else 0,
                            1,
                        ),
                    }
                    for lid, sig in self.signals.items()
                },
            }
