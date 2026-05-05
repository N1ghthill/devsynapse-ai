"""Tests for core.metrics."""
from __future__ import annotations

from core.metrics import MetricsCollector


class TestMetricsCollector:
    def setup_method(self):
        self.collector = MetricsCollector()

    def test_increment_counter(self):
        self.collector.increment("requests")
        self.collector.increment("requests")
        assert self.collector.get_counter("requests") == 2

    def test_increment_with_value(self):
        self.collector.increment("tokens", value=100)
        assert self.collector.get_counter("tokens") == 100

    def test_record_timing(self):
        self.collector.record_timing("latency", 0.5)
        self.collector.record_timing("latency", 1.0)

        stats = self.collector.get_timing_stats("latency")
        assert stats["count"] == 2
        assert stats["avg"] == 0.75
        assert stats["min"] == 0.5
        assert stats["max"] == 1.0
        assert stats["total"] == 1.5

    def test_record_gauge(self):
        self.collector.record_gauge("memory_usage", 1024.0)
        points = [p for p in self.collector._points if p.name == "memory_usage"]
        assert len(points) == 1
        assert points[0].value == 1024.0

    def test_get_success_rate(self):
        self.collector.increment("llm.success", 3)
        self.collector.increment("llm.failure", 1)

        rate = self.collector.get_success_rate("llm")
        assert rate == 0.75

    def test_get_success_rate_no_data(self):
        rate = self.collector.get_success_rate("unknown")
        assert rate == 0.0

    def test_get_timing_stats_no_data(self):
        stats = self.collector.get_timing_stats("unknown")
        assert stats["count"] == 0
        assert stats["avg"] == 0.0

    def test_reset(self):
        self.collector.increment("counter")
        self.collector.record_timing("timing", 0.1)
        self.collector.reset()

        assert self.collector.get_counter("counter") == 0
        assert self.collector.get_timing_stats("timing")["count"] == 0

    def test_summary(self):
        self.collector.increment("llm.success", 2)
        self.collector.increment("llm.failure", 1)
        self.collector.record_timing("llm.latency", 0.5)

        summary = self.collector.summary()
        assert summary["counters"]["llm.success"] == 2
        assert summary["counters"]["llm.failure"] == 1
        assert summary["timings"]["llm.latency"]["count"] == 1
        assert summary["success_rates"]["llm"] == 2 / 3
        assert summary["success_rates"]["command"] == 0.0
