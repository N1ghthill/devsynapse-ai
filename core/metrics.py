"""Metrics collection for DevSynapse AI."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MetricPoint:
    """Single metric observation."""
    name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Collects and aggregates runtime metrics."""

    def __init__(self) -> None:
        self._points: List[MetricPoint] = []
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, List[float]] = {}

    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + value

    def record_timing(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing measurement."""
        self._timers.setdefault(name, []).append(duration)
        self._points.append(MetricPoint(name, duration, tags or {}))

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a gauge value."""
        self._points.append(MetricPoint(name, value, tags or {}))

    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        return self._counters.get(name, 0)

    def get_timing_stats(self, name: str) -> Dict[str, float]:
        """Get timing statistics for a metric."""
        values = self._timers.get(name, [])
        if not values:
            return {"count": 0, "avg": 0.0, "min": 0.0, "max": 0.0, "total": 0.0}
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "total": sum(values),
        }

    def get_success_rate(self, operation: str) -> float:
        """Calculate success rate for an operation."""
        success = self._counters.get(f"{operation}.success", 0)
        failure = self._counters.get(f"{operation}.failure", 0)
        total = success + failure
        return success / total if total > 0 else 0.0

    def reset(self) -> None:
        """Reset all metrics."""
        self._points.clear()
        self._counters.clear()
        self._timers.clear()

    def summary(self) -> Dict:
        """Get a summary of all collected metrics."""
        return {
            "counters": dict(self._counters),
            "timings": {name: self.get_timing_stats(name) for name in self._timers},
            "success_rates": {
                "llm": self.get_success_rate("llm"),
                "command": self.get_success_rate("command"),
            },
        }


metrics = MetricsCollector()
