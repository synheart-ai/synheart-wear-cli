"""Tests for Flux integration (wear.raw_event.v1 schema conversion)."""

import json
import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from server.flux_integration import (
    SCHEMA_VERSION,
    _emit_signal,
    _emit_session,
    _emit_score,
    _emit_summary,
    _make_source,
    _utc_iso,
    _whoop_to_wear_raw_events,
    _garmin_to_wear_raw_events,
    whoop_to_raw_events_ndjson,
    garmin_to_raw_events_ndjson,
)


class TestSchemaVersion:
    """Tests for schema version constant."""

    def test_schema_version_format(self):
        """Schema version should follow wear.*.v1 format."""
        assert SCHEMA_VERSION == "wear.raw_event.v1"
        assert SCHEMA_VERSION.startswith("wear.")
        assert SCHEMA_VERSION.endswith(".v1")


class TestTimestampNormalization:
    """Tests for timestamp normalization."""

    def test_iso_string_passthrough(self):
        """ISO strings should be normalized to UTC."""
        result = _utc_iso("2024-01-15T06:30:00Z")
        assert result == "2024-01-15T06:30:00Z"

    def test_iso_with_offset(self):
        """ISO strings with offset should be converted to UTC."""
        result = _utc_iso("2024-01-15T01:30:00-05:00")
        assert result == "2024-01-15T06:30:00Z"

    def test_missing_timestamp_raises(self):
        """Missing timestamp should raise ValueError."""
        with pytest.raises(ValueError):
            _utc_iso(None)


class TestMakeSource:
    """Tests for source object creation."""

    def test_minimal_source(self):
        """Minimal source should have provider and device_id."""
        source = _make_source("whoop", "device-123")
        assert source["provider"] == "whoop"
        assert source["device_id"] == "device-123"
        assert "device_model" not in source

    def test_source_with_model(self):
        """Source with model should include device_model."""
        source = _make_source("whoop", "device-123", "WHOOP 4.0")
        assert source["provider"] == "whoop"
        assert source["device_id"] == "device-123"
        assert source["device_model"] == "WHOOP 4.0"


class TestEmitSignal:
    """Tests for signal event emission."""

    def test_signal_structure(self):
        """Signal should have correct structure."""
        source = _make_source("whoop", "device-123")
        evt = _emit_signal(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            signal_type="heart_rate_variability",
            value=65,
            unit="ms",
        )
        assert evt["schema_version"] == SCHEMA_VERSION
        assert evt["record_type"] == "signal"
        assert evt["timestamp"] == "2024-01-15T06:30:00Z"
        assert evt["source"] == source
        assert evt["payload"]["signal"]["type"] == "heart_rate_variability"
        assert evt["payload"]["signal"]["value"] == 65.0
        assert evt["payload"]["signal"]["unit"] == "ms"
        assert "event_id" in evt

    def test_signal_with_quality(self):
        """Signal with quality should include quality field."""
        source = _make_source("whoop", "device-123")
        evt = _emit_signal(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            signal_type="spo2",
            value=97,
            unit="percent",
            quality=0.95,
        )
        assert evt["payload"]["signal"]["quality"] == 0.95

    def test_signal_with_context(self):
        """Signal with context should include context."""
        source = _make_source("whoop", "device-123")
        ctx = {"session_id": "abc123", "timezone": "America/New_York"}
        evt = _emit_signal(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            signal_type="heart_rate",
            value=72,
            unit="bpm",
            context=ctx,
        )
        assert evt["context"] == ctx


class TestEmitSession:
    """Tests for session event emission."""

    def test_session_structure(self):
        """Session should have correct structure."""
        source = _make_source("whoop", "device-123")
        metrics = {
            "total_sleep_minutes": 420,
            "deep_sleep_minutes": 90,
            "rem_sleep_minutes": 100,
        }
        evt = _emit_session(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            session_type="sleep",
            start_time="2024-01-14T22:30:00Z",
            end_time="2024-01-15T06:30:00Z",
            metrics=metrics,
        )
        assert evt["schema_version"] == SCHEMA_VERSION
        assert evt["record_type"] == "session"
        assert evt["payload"]["session"]["type"] == "sleep"
        assert evt["payload"]["session"]["start_time"] == "2024-01-14T22:30:00Z"
        assert evt["payload"]["session"]["end_time"] == "2024-01-15T06:30:00Z"
        assert evt["payload"]["session"]["metrics"] == metrics


class TestEmitScore:
    """Tests for score event emission."""

    def test_score_structure(self):
        """Score should have correct structure."""
        source = _make_source("whoop", "device-123")
        evt = _emit_score(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            score_type="recovery",
            value=78,
            scale_min=0,
            scale_max=100,
        )
        assert evt["schema_version"] == SCHEMA_VERSION
        assert evt["record_type"] == "score"
        assert evt["payload"]["score"]["type"] == "recovery"
        assert evt["payload"]["score"]["value"] == 78.0
        assert evt["payload"]["score"]["scale"]["min"] == 0
        assert evt["payload"]["score"]["scale"]["max"] == 100

    def test_score_with_components(self):
        """Score with components should include components."""
        source = _make_source("whoop", "device-123")
        components = {"hrv_contribution": 0.3, "sleep_contribution": 0.7}
        evt = _emit_score(
            timestamp="2024-01-15T06:30:00Z",
            source=source,
            score_type="recovery",
            value=78,
            scale_min=0,
            scale_max=100,
            components=components,
        )
        assert evt["payload"]["score"]["components"] == components


class TestEmitSummary:
    """Tests for summary event emission."""

    def test_summary_structure(self):
        """Summary should have correct structure."""
        source = _make_source("garmin", "device-456")
        metrics = {"steps": 10000, "calories": 2500, "distance_meters": 8000}
        evt = _emit_summary(
            timestamp="2024-01-15T12:00:00Z",
            source=source,
            period="daily",
            date="2024-01-15",
            metrics=metrics,
        )
        assert evt["schema_version"] == SCHEMA_VERSION
        assert evt["record_type"] == "summary"
        assert evt["payload"]["summary"]["period"] == "daily"
        assert evt["payload"]["summary"]["date"] == "2024-01-15"
        assert evt["payload"]["summary"]["metrics"] == metrics


class TestWhoopConversion:
    """Tests for WHOOP data to raw events conversion."""

    def test_recovery_to_events(self):
        """WHOOP recovery should convert to score + signals."""
        whoop_data = {
            "recovery": [
                {
                    "id": 12345,
                    "created_at": "2024-01-15T06:30:00Z",
                    "score": {
                        "recovery_score": 78,
                        "hrv_rmssd_milli": 65,
                        "resting_heart_rate": 52,
                        "spo2_percentage": 97,
                    },
                }
            ],
            "sleep": [],
            "workout": [],
            "cycle": [],
        }
        events = _whoop_to_wear_raw_events(whoop_data, "device-123", "America/New_York")

        # Should have recovery score + HRV + RHR + SpO2 signals = 4 events
        assert len(events) == 4

        # Check recovery score
        score_events = [e for e in events if e["record_type"] == "score"]
        assert len(score_events) == 1
        assert score_events[0]["payload"]["score"]["type"] == "recovery"
        assert score_events[0]["payload"]["score"]["value"] == 78

        # Check signals
        signal_events = [e for e in events if e["record_type"] == "signal"]
        assert len(signal_events) == 3

        signal_types = {e["payload"]["signal"]["type"] for e in signal_events}
        assert "heart_rate_variability" in signal_types
        assert "resting_heart_rate" in signal_types
        assert "spo2" in signal_types

    def test_sleep_to_session(self):
        """WHOOP sleep should convert to session event."""
        whoop_data = {
            "recovery": [],
            "sleep": [
                {
                    "id": 67890,
                    "start": "2024-01-14T22:30:00Z",
                    "end": "2024-01-15T06:30:00Z",
                    "nap": False,
                    "score": {
                        "stage_summary": {
                            "total_sleep_time_milli": 25200000,  # 7 hours
                            "total_slow_wave_sleep_time_milli": 5400000,  # 90 min
                            "total_rem_sleep_time_milli": 6000000,  # 100 min
                        },
                        "sleep_performance_percentage": 85,
                    },
                }
            ],
            "workout": [],
            "cycle": [],
        }
        events = _whoop_to_wear_raw_events(whoop_data, "device-123", "America/New_York")

        assert len(events) == 1
        evt = events[0]
        assert evt["record_type"] == "session"
        assert evt["payload"]["session"]["type"] == "sleep"
        assert evt["payload"]["session"]["metrics"]["total_sleep_minutes"] == 420
        assert evt["payload"]["session"]["metrics"]["deep_sleep_minutes"] == 90
        assert evt["payload"]["session"]["metrics"]["sleep_score"] == 85

    def test_workout_to_session_and_strain(self):
        """WHOOP workout should convert to session + strain score."""
        whoop_data = {
            "recovery": [],
            "sleep": [],
            "workout": [
                {
                    "id": 11111,
                    "start": "2024-01-15T07:00:00Z",
                    "end": "2024-01-15T08:00:00Z",
                    "sport_id": 1,
                    "score": {
                        "strain": 12.5,
                        "average_heart_rate": 145,
                        "max_heart_rate": 175,
                        "kilojoule": 2500,
                    },
                }
            ],
            "cycle": [],
        }
        events = _whoop_to_wear_raw_events(whoop_data, "device-123", "America/New_York")

        assert len(events) == 2

        # Check workout session
        session_events = [e for e in events if e["record_type"] == "session"]
        assert len(session_events) == 1
        assert session_events[0]["payload"]["session"]["type"] == "workout"
        assert session_events[0]["payload"]["session"]["metrics"]["average_hr_bpm"] == 145

        # Check strain score
        score_events = [e for e in events if e["record_type"] == "score"]
        assert len(score_events) == 1
        assert score_events[0]["payload"]["score"]["type"] == "strain"
        assert score_events[0]["payload"]["score"]["value"] == 12.5

    def test_empty_data(self):
        """Empty WHOOP data should return empty list."""
        events = _whoop_to_wear_raw_events({}, "device-123", "UTC")
        assert events == []


class TestGarminConversion:
    """Tests for Garmin data to raw events conversion."""

    def test_daily_to_summary(self):
        """Garmin daily should convert to summary event."""
        garmin_data = {
            "dailies": [
                {
                    "calendarDate": "2024-01-15",
                    "totalSteps": 10000,
                    "totalDistanceMeters": 8000,
                    "totalKilocalories": 2500,
                    "restingHeartRate": 55,
                }
            ],
            "sleep": [],
        }
        events = _garmin_to_wear_raw_events(garmin_data, "device-456", "America/New_York")

        # Should have 1 summary event
        summary_events = [e for e in events if e["record_type"] == "summary"]
        assert len(summary_events) == 1
        assert summary_events[0]["payload"]["summary"]["period"] == "daily"
        assert summary_events[0]["payload"]["summary"]["date"] == "2024-01-15"
        assert summary_events[0]["payload"]["summary"]["metrics"]["steps"] == 10000

    def test_body_battery_to_score(self):
        """Garmin body battery should convert to score event."""
        garmin_data = {
            "dailies": [
                {
                    "calendarDate": "2024-01-15",
                    "totalSteps": 5000,
                    "bodyBatteryChargedValue": 85,
                }
            ],
            "sleep": [],
        }
        events = _garmin_to_wear_raw_events(garmin_data, "device-456", "UTC")

        score_events = [e for e in events if e["record_type"] == "score"]
        assert len(score_events) == 1
        assert score_events[0]["payload"]["score"]["type"] == "body_battery"
        assert score_events[0]["payload"]["score"]["value"] == 85

    def test_sleep_to_session(self):
        """Garmin sleep should convert to session event."""
        garmin_data = {
            "dailies": [],
            "sleep": [
                {
                    "calendarDate": "2024-01-15",
                    "sleepStartTimestampGmt": 1705272600000,  # epoch ms
                    "sleepEndTimestampGmt": 1705301400000,
                    "sleepTimeSeconds": 25200,  # 7 hours
                    "deepSleepSeconds": 5400,
                    "remSleepSeconds": 6000,
                    "sleepScores": {"overallScore": 80},
                }
            ],
        }
        events = _garmin_to_wear_raw_events(garmin_data, "device-456", "UTC")

        session_events = [e for e in events if e["record_type"] == "session"]
        assert len(session_events) == 1
        assert session_events[0]["payload"]["session"]["type"] == "sleep"
        assert session_events[0]["payload"]["session"]["metrics"]["total_sleep_minutes"] == 420
        assert session_events[0]["payload"]["session"]["metrics"]["sleep_score"] == 80


class TestNdjsonSerialization:
    """Tests for NDJSON serialization."""

    def test_whoop_to_ndjson(self):
        """WHOOP data should serialize to valid NDJSON."""
        whoop_data = {
            "recovery": [
                {
                    "id": 12345,
                    "created_at": "2024-01-15T06:30:00Z",
                    "score": {"recovery_score": 78},
                }
            ],
            "sleep": [],
            "workout": [],
            "cycle": [],
        }
        ndjson = whoop_to_raw_events_ndjson(whoop_data, "device-123", "UTC")

        # Should be valid NDJSON (one JSON object per line)
        lines = [l for l in ndjson.strip().split("\n") if l]
        assert len(lines) >= 1

        for line in lines:
            obj = json.loads(line)
            assert obj["schema_version"] == SCHEMA_VERSION
            assert "record_type" in obj
            assert "payload" in obj

    def test_garmin_to_ndjson(self):
        """Garmin data should serialize to valid NDJSON."""
        garmin_data = {
            "dailies": [
                {
                    "calendarDate": "2024-01-15",
                    "totalSteps": 10000,
                }
            ],
            "sleep": [],
        }
        ndjson = garmin_to_raw_events_ndjson(garmin_data, "device-456", "UTC")

        lines = [l for l in ndjson.strip().split("\n") if l]
        assert len(lines) >= 1

        for line in lines:
            obj = json.loads(line)
            assert obj["schema_version"] == SCHEMA_VERSION


class TestCliCommands:
    """Tests for CLI commands related to Flux."""

    def test_export_command_help(self):
        """Export command help should work."""
        from typer.testing import CliRunner
        from wear import app

        runner = CliRunner()
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "export" in result.stdout.lower()
        assert "--vendor" in result.stdout
        assert "--user-id" in result.stdout
        assert "--output" in result.stdout
        assert "ndjson" in result.stdout.lower()

    def test_pull_command_has_output_option(self):
        """Pull command should have --output option."""
        from typer.testing import CliRunner
        from wear import app

        runner = CliRunner()
        result = runner.invoke(app, ["pull", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.stdout
