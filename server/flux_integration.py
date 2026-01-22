"""Integration module for Synheart Flux HSI processing (Rust binary).

This module converts vendor wearable data to the unified wear.raw_event.v1 schema
and processes it through the Flux CLI to produce HSI-compliant outputs.

Schema: wear.raw_event.v1
Supported record types:
  - signal: Individual point-in-time readings (HR, HRV, SpO2, etc.)
  - session: Sleep, workout, meditation sessions with metrics
  - summary: Daily/hourly aggregates
  - score: Vendor-computed scores (recovery, strain, readiness)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

# Schema version constant
SCHEMA_VERSION = "wear.raw_event.v1"


def is_flux_enabled() -> bool:
    """Check if flux processing is enabled."""
    if os.getenv("USE_FLUX", "false").lower() not in ("true", "1", "yes"):
        return False
    return resolve_flux_binary() is not None


def resolve_flux_binary() -> str | None:
    """
    Resolve the Flux executable path.

    Discovery order:
    1) SYNHEART_FLUX_PATH (explicit)
    2) repo-local bin/ (for bundled/dev binaries)
    3) ~/.synheart/bin/ (optional cache)
    4) PATH lookup ("flux")
    """
    env_path = os.getenv("SYNHEART_FLUX_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        if p.exists() and os.access(str(p), os.X_OK):
            return str(p)

    # Repo-local bin candidates (matches FLUX_INTEGRATION.md packaging section)
    cli_root = Path(__file__).parent.parent
    bin_dir = cli_root / "bin"
    candidates: list[Path] = []
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            candidates.extend([bin_dir / "flux-macos-arm64", bin_dir / "flux"])
        else:
            candidates.extend([bin_dir / "flux-macos-x64", bin_dir / "flux"])
    elif system == "windows":
        candidates.extend([bin_dir / "flux-windows-x64.exe", bin_dir / "flux.exe"])
    else:
        candidates.extend([bin_dir / "flux-linux-x64", bin_dir / "flux"])

    # User cache
    home_bin = Path.home() / ".synheart" / "bin"
    if system == "windows":
        candidates.append(home_bin / "flux.exe")
    else:
        candidates.append(home_bin / "flux")

    for c in candidates:
        if c.exists() and os.access(str(c), os.X_OK):
            return str(c)

    # PATH
    which = shutil.which("flux")
    return which


def _utc_iso(ts: Any) -> str:
    """Best-effort timestamp normalization to ISO8601 UTC."""
    if ts is None:
        raise ValueError("Missing timestamp")
    if isinstance(ts, str):
        dt = date_parser.parse(ts)
    else:
        dt = date_parser.parse(str(ts))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_source(provider: str, device_id: str, device_model: str | None = None) -> dict[str, Any]:
    """Create a source object for wear.raw_event.v1."""
    source: dict[str, Any] = {
        "provider": provider,
        "device_id": device_id,
    }
    if device_model:
        source["device_model"] = device_model
    return source


def _emit_signal(
    timestamp: str,
    source: dict[str, Any],
    signal_type: str,
    value: float | int,
    unit: str,
    quality: float | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a signal record (individual point-in-time reading).

    Signal types: heart_rate, heart_rate_variability, resting_heart_rate,
                  respiratory_rate, spo2, steps, calories, distance, etc.
    """
    evt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "source": source,
        "record_type": "signal",
        "payload": {
            "signal": {
                "type": signal_type,
                "value": float(value),
                "unit": unit,
            }
        },
    }
    if quality is not None:
        evt["payload"]["signal"]["quality"] = quality
    if context:
        evt["context"] = context
    return evt


def _emit_session(
    timestamp: str,
    source: dict[str, Any],
    session_type: str,
    start_time: str,
    end_time: str,
    metrics: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a session record (sleep, workout, meditation, etc.).

    Session types: sleep, nap, workout, meditation, recovery
    """
    evt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "source": source,
        "record_type": "session",
        "payload": {
            "session": {
                "type": session_type,
                "start_time": start_time,
                "end_time": end_time,
                "metrics": metrics,
            }
        },
    }
    if context:
        evt["context"] = context
    return evt


def _emit_score(
    timestamp: str,
    source: dict[str, Any],
    score_type: str,
    value: float,
    scale_min: float,
    scale_max: float,
    components: dict[str, float] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a score record (vendor-computed scores).

    Score types: recovery, strain, sleep, readiness, stress, body_battery
    """
    evt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "source": source,
        "record_type": "score",
        "payload": {
            "score": {
                "type": score_type,
                "value": float(value),
                "scale": {"min": scale_min, "max": scale_max},
            }
        },
    }
    if components:
        evt["payload"]["score"]["components"] = components
    if context:
        evt["context"] = context
    return evt


def _emit_summary(
    timestamp: str,
    source: dict[str, Any],
    period: str,
    date: str,
    metrics: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a summary record (daily/hourly aggregates).

    Period types: hourly, daily, weekly, monthly
    """
    evt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp,
        "source": source,
        "record_type": "summary",
        "payload": {
            "summary": {
                "period": period,
                "date": date,
                "metrics": metrics,
            }
        },
    }
    if context:
        evt["context"] = context
    return evt


def _whoop_to_wear_raw_events(
    whoop_data: dict[str, Any],
    device_id: str,
    user_timezone: str = "UTC",
) -> list[dict[str, Any]]:
    """
    Convert WHOOP collections to wear.raw_event.v1 NDJSON records.

    Uses proper record types:
    - Recovery data -> score (recovery) + signals (HRV, RHR, SpO2)
    - Sleep data -> session (sleep) with metrics
    - Workout data -> session (workout) + score (strain)
    - Cycle data -> score (strain) for daily strain
    """
    events: list[dict[str, Any]] = []
    source = _make_source("whoop", device_id, "WHOOP 4.0")

    # Recovery records -> recovery score + physiological signals
    for rec in whoop_data.get("recovery", []) or []:
        if not isinstance(rec, dict):
            continue
        score_data = rec.get("score", {}) or {}
        ts = rec.get("created_at") or rec.get("timestamp") or rec.get("start")
        if not ts:
            continue

        try:
            ts_iso = _utc_iso(ts)
        except Exception:
            continue

        ctx = {"session_id": str(rec.get("cycle_id") or rec.get("id")), "timezone": user_timezone}

        # Recovery score
        if score_data.get("recovery_score") is not None:
            events.append(
                _emit_score(
                    timestamp=ts_iso,
                    source=source,
                    score_type="recovery",
                    value=score_data["recovery_score"],
                    scale_min=0,
                    scale_max=100,
                    context=ctx,
                )
            )

        # HRV signal
        if score_data.get("hrv_rmssd_milli") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="heart_rate_variability",
                    value=score_data["hrv_rmssd_milli"],
                    unit="ms",
                    context=ctx,
                )
            )

        # Resting heart rate signal
        if score_data.get("resting_heart_rate") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="resting_heart_rate",
                    value=score_data["resting_heart_rate"],
                    unit="bpm",
                    context=ctx,
                )
            )

        # SpO2 signal
        if score_data.get("spo2_percentage") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="spo2",
                    value=score_data["spo2_percentage"],
                    unit="percent",
                    context=ctx,
                )
            )

        # Skin temperature signal
        if score_data.get("skin_temp_celsius") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="skin_temperature",
                    value=score_data["skin_temp_celsius"],
                    unit="celsius",
                    context=ctx,
                )
            )

    # Sleep records -> sleep session with metrics
    for rec in whoop_data.get("sleep", []) or []:
        if not isinstance(rec, dict):
            continue
        score_data = rec.get("score", {}) or {}
        stage_summary = score_data.get("stage_summary", {}) or {}

        start = rec.get("start")
        end = rec.get("end")
        if not start or not end:
            continue

        try:
            start_iso = _utc_iso(start)
            end_iso = _utc_iso(end)
        except Exception:
            continue

        ctx = {"session_id": str(rec.get("id")), "timezone": user_timezone}
        is_nap = rec.get("nap", False)

        # Build sleep metrics
        metrics: dict[str, Any] = {}
        if stage_summary.get("total_sleep_time_milli") is not None:
            metrics["total_sleep_minutes"] = stage_summary["total_sleep_time_milli"] / 60000
        if stage_summary.get("total_in_bed_time_milli") is not None:
            metrics["time_in_bed_minutes"] = stage_summary["total_in_bed_time_milli"] / 60000
        if stage_summary.get("total_awake_time_milli") is not None:
            metrics["awake_minutes"] = stage_summary["total_awake_time_milli"] / 60000
        if stage_summary.get("total_light_sleep_time_milli") is not None:
            metrics["light_sleep_minutes"] = stage_summary["total_light_sleep_time_milli"] / 60000
        if stage_summary.get("total_slow_wave_sleep_time_milli") is not None:
            metrics["deep_sleep_minutes"] = (
                stage_summary["total_slow_wave_sleep_time_milli"] / 60000
            )
        if stage_summary.get("total_rem_sleep_time_milli") is not None:
            metrics["rem_sleep_minutes"] = stage_summary["total_rem_sleep_time_milli"] / 60000
        if stage_summary.get("disturbance_count") is not None:
            metrics["awakenings"] = stage_summary["disturbance_count"]
        if score_data.get("sleep_performance_percentage") is not None:
            metrics["sleep_score"] = score_data["sleep_performance_percentage"]
        if score_data.get("sleep_efficiency_percentage") is not None:
            metrics["efficiency"] = score_data["sleep_efficiency_percentage"] / 100
        if score_data.get("respiratory_rate") is not None:
            metrics["respiratory_rate"] = score_data["respiratory_rate"]
        if score_data.get("sleep_latency_time_milli") is not None:
            metrics["latency_minutes"] = score_data["sleep_latency_time_milli"] / 60000

        events.append(
            _emit_session(
                timestamp=end_iso,
                source=source,
                session_type="nap" if is_nap else "sleep",
                start_time=start_iso,
                end_time=end_iso,
                metrics=metrics,
                context=ctx,
            )
        )

    # Workout records -> workout session + strain score
    for rec in whoop_data.get("workout", []) or []:
        if not isinstance(rec, dict):
            continue
        score_data = rec.get("score", {}) or {}

        start = rec.get("start")
        end = rec.get("end")
        if not start or not end:
            continue

        try:
            start_iso = _utc_iso(start)
            end_iso = _utc_iso(end)
        except Exception:
            continue

        ctx = {"session_id": str(rec.get("id")), "timezone": user_timezone}

        # Build workout metrics
        metrics: dict[str, Any] = {}
        if score_data.get("average_heart_rate") is not None:
            metrics["average_hr_bpm"] = score_data["average_heart_rate"]
        if score_data.get("max_heart_rate") is not None:
            metrics["max_hr_bpm"] = score_data["max_heart_rate"]
        if score_data.get("kilojoule") is not None:
            metrics["calories"] = score_data["kilojoule"] * 0.239006  # kJ to kcal
        if score_data.get("distance_meter") is not None:
            metrics["distance_meters"] = score_data["distance_meter"]
        if rec.get("sport_id") is not None:
            metrics["sport_id"] = rec["sport_id"]

        events.append(
            _emit_session(
                timestamp=end_iso,
                source=source,
                session_type="workout",
                start_time=start_iso,
                end_time=end_iso,
                metrics=metrics,
                context=ctx,
            )
        )

        # Workout strain score
        if score_data.get("strain") is not None:
            events.append(
                _emit_score(
                    timestamp=end_iso,
                    source=source,
                    score_type="strain",
                    value=score_data["strain"],
                    scale_min=0,
                    scale_max=21,  # WHOOP strain scale
                    context=ctx,
                )
            )

    # Cycle records -> daily strain score
    for rec in whoop_data.get("cycle", []) or []:
        if not isinstance(rec, dict):
            continue
        score_data = rec.get("score", {}) or {}

        ts = rec.get("end") or rec.get("start")
        if not ts:
            continue

        try:
            ts_iso = _utc_iso(ts)
        except Exception:
            continue

        ctx = {"session_id": str(rec.get("id")), "timezone": user_timezone}

        # Daily strain score
        if score_data.get("strain") is not None:
            events.append(
                _emit_score(
                    timestamp=ts_iso,
                    source=source,
                    score_type="strain",
                    value=score_data["strain"],
                    scale_min=0,
                    scale_max=21,
                    context=ctx,
                )
            )

        # Daily calories (from cycle)
        if score_data.get("kilojoule") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="calories",
                    value=score_data["kilojoule"] * 0.239006,
                    unit="kcal",
                    context=ctx,
                )
            )

    return events


def _garmin_to_wear_raw_events(
    garmin_data: dict[str, Any],
    device_id: str,
    user_timezone: str = "UTC",
) -> list[dict[str, Any]]:
    """
    Convert Garmin collections to wear.raw_event.v1 NDJSON records.

    Uses proper record types:
    - Daily summaries -> summary (daily) with activity metrics
    - Sleep data -> session (sleep) with metrics
    - Body battery -> score (body_battery)
    """
    events: list[dict[str, Any]] = []
    source = _make_source("garmin", device_id)

    # Daily summaries
    for rec in garmin_data.get("dailies", []) or []:
        if not isinstance(rec, dict):
            continue

        date = rec.get("calendarDate")
        if not date:
            continue

        # Use noon of the date as timestamp
        try:
            ts_iso = _utc_iso(f"{date}T12:00:00Z")
        except Exception:
            continue

        ctx = {"timezone": user_timezone}

        # Build daily metrics
        metrics: dict[str, Any] = {}
        if rec.get("totalSteps") is not None:
            metrics["steps"] = rec["totalSteps"]
        if rec.get("totalDistanceMeters") is not None:
            metrics["distance_meters"] = rec["totalDistanceMeters"]
        if rec.get("totalKilocalories") is not None:
            metrics["calories"] = rec["totalKilocalories"]
        if rec.get("activeKilocalories") is not None:
            metrics["active_calories"] = rec["activeKilocalories"]
        if rec.get("restingHeartRate") is not None:
            metrics["resting_heart_rate"] = rec["restingHeartRate"]
        if rec.get("averageHeartRate") is not None:
            metrics["average_heart_rate"] = rec["averageHeartRate"]
        if rec.get("maxHeartRate") is not None:
            metrics["max_heart_rate"] = rec["maxHeartRate"]
        if rec.get("avgSpo2Value") is not None:
            metrics["spo2"] = rec["avgSpo2Value"]
        if rec.get("moderateIntensityMinutes") is not None:
            metrics["moderate_intensity_minutes"] = rec["moderateIntensityMinutes"]
        if rec.get("vigorousIntensityMinutes") is not None:
            metrics["vigorous_intensity_minutes"] = rec["vigorousIntensityMinutes"]

        if metrics:
            events.append(
                _emit_summary(
                    timestamp=ts_iso,
                    source=source,
                    period="daily",
                    date=date,
                    metrics=metrics,
                    context=ctx,
                )
            )

        # Body battery as score
        if rec.get("bodyBatteryChargedValue") is not None:
            events.append(
                _emit_score(
                    timestamp=ts_iso,
                    source=source,
                    score_type="body_battery",
                    value=rec["bodyBatteryChargedValue"],
                    scale_min=0,
                    scale_max=100,
                    context=ctx,
                )
            )

        # Training load as score
        if rec.get("trainingLoadBalance") is not None:
            events.append(
                _emit_score(
                    timestamp=ts_iso,
                    source=source,
                    score_type="training_load",
                    value=rec["trainingLoadBalance"],
                    scale_min=0,
                    scale_max=100,
                    context=ctx,
                )
            )

        # HRV if available
        if rec.get("restingHeartRateHrv") is not None:
            events.append(
                _emit_signal(
                    timestamp=ts_iso,
                    source=source,
                    signal_type="heart_rate_variability",
                    value=rec["restingHeartRateHrv"],
                    unit="ms",
                    context=ctx,
                )
            )

    # Sleep records
    for rec in garmin_data.get("sleep", []) or []:
        if not isinstance(rec, dict):
            continue

        date = rec.get("calendarDate")
        start_ts = rec.get("sleepStartTimestampGmt")
        end_ts = rec.get("sleepEndTimestampGmt")

        if not date:
            continue

        try:
            if start_ts and end_ts:
                start_iso = (
                    datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                end_iso = (
                    datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
            else:
                # Fallback to date-based timestamps
                start_iso = _utc_iso(f"{date}T22:00:00Z")
                end_iso = _utc_iso(f"{date}T06:00:00Z")
        except Exception:
            continue

        ctx = {"timezone": user_timezone}

        # Build sleep metrics
        metrics: dict[str, Any] = {}
        if rec.get("sleepTimeSeconds") is not None:
            metrics["total_sleep_minutes"] = rec["sleepTimeSeconds"] / 60
        if rec.get("awakeSleepSeconds") is not None:
            metrics["awake_minutes"] = rec["awakeSleepSeconds"] / 60
        if rec.get("lightSleepSeconds") is not None:
            metrics["light_sleep_minutes"] = rec["lightSleepSeconds"] / 60
        if rec.get("deepSleepSeconds") is not None:
            metrics["deep_sleep_minutes"] = rec["deepSleepSeconds"] / 60
        if rec.get("remSleepSeconds") is not None:
            metrics["rem_sleep_minutes"] = rec["remSleepSeconds"] / 60
        if rec.get("awakeCount") is not None:
            metrics["awakenings"] = rec["awakeCount"]
        if rec.get("avgSleepRespiration") is not None:
            metrics["respiratory_rate"] = rec["avgSleepRespiration"]

        sleep_scores = rec.get("sleepScores", {}) or {}
        if sleep_scores.get("overallScore") is not None:
            metrics["sleep_score"] = sleep_scores["overallScore"]
        if sleep_scores.get("qualityScore") is not None:
            metrics["quality_score"] = sleep_scores["qualityScore"]

        if metrics:
            events.append(
                _emit_session(
                    timestamp=end_iso,
                    source=source,
                    session_type="sleep",
                    start_time=start_iso,
                    end_time=end_iso,
                    metrics=metrics,
                    context=ctx,
                )
            )

    return events


def _run_flux_transform(
    raw_events: list[dict[str, Any]],
    user_timezone: str = "UTC",
    device_id: str = "unknown",
    baseline_days: int = 14,
    load_baselines: str | None = None,
    save_baselines: str | None = None,
) -> list[dict[str, Any]]:
    """Run flux transform command on raw events."""
    flux = resolve_flux_binary()
    if not flux:
        raise ValueError(
            "Flux binary not found. Set SYNHEART_FLUX_PATH or place a flux binary in ./bin/ "
            "(see FLUX_INTEGRATION.md)."
        )

    with tempfile.TemporaryDirectory(prefix="synheart_flux_") as td:
        td_path = Path(td)
        in_path = td_path / "raw.ndjson"
        out_path = td_path / "hsi.ndjson"

        with in_path.open("w", encoding="utf-8") as f:
            for evt in raw_events:
                f.write(json.dumps(evt, separators=(",", ":"), ensure_ascii=False) + "\n")

        cmd = [
            flux,
            "transform",
            "--input",
            str(in_path),
            "--output",
            str(out_path),
            "--input-format",
            "ndjson",
            "--output-format",
            "ndjson",
            "--timezone",
            user_timezone,
            "--device-id",
            device_id,
            "--baseline-days",
            str(baseline_days),
        ]

        if load_baselines:
            cmd.extend(["--load-baselines", load_baselines])
        if save_baselines:
            cmd.extend(["--save-baselines", save_baselines])

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            raise ValueError(f"Flux transform failed (exit {e.returncode}): {stderr or e}") from e

        if not out_path.exists():
            return []

        outputs: list[dict[str, Any]] = []
        with out_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                outputs.append(json.loads(line))
        return outputs


def process_whoop_to_hsi(
    whoop_data: dict[str, Any],
    user_timezone: str = "UTC",
    device_id: str | None = None,
    baseline_days: int = 14,
    load_baselines: str | None = None,
    save_baselines: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert WHOOP data to HSI format using Flux.

    Args:
        whoop_data: Raw WHOOP API response (dict with sleep, recovery, cycle, workout arrays)
        user_timezone: User's timezone in IANA format (default: UTC)
        device_id: Device identifier (default: auto-generated)
        baseline_days: Number of days for baseline window (default: 14)
        load_baselines: Path to load baselines from
        save_baselines: Path to save baselines to

    Returns:
        List of HSI-compliant JSON payloads

    Raises:
        ValueError: If flux is not available or processing fails
    """
    if not is_flux_enabled():
        raise ValueError("Flux processing is not enabled. Set USE_FLUX=true")

    if device_id is None:
        device_id = whoop_data.get("device_id") or "whoop-device"

    raw_events = _whoop_to_wear_raw_events(
        whoop_data, device_id=device_id, user_timezone=user_timezone
    )

    if not raw_events:
        return []

    return _run_flux_transform(
        raw_events,
        user_timezone=user_timezone,
        device_id=device_id,
        baseline_days=baseline_days,
        load_baselines=load_baselines,
        save_baselines=save_baselines,
    )


def process_garmin_to_hsi(
    garmin_data: dict[str, Any],
    user_timezone: str = "UTC",
    device_id: str | None = None,
    baseline_days: int = 14,
    load_baselines: str | None = None,
    save_baselines: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert Garmin data to HSI format using Flux.

    Args:
        garmin_data: Raw Garmin API response (dict with dailies, sleep arrays)
        user_timezone: User's timezone in IANA format (default: UTC)
        device_id: Device identifier (default: auto-generated)
        baseline_days: Number of days for baseline window (default: 14)
        load_baselines: Path to load baselines from
        save_baselines: Path to save baselines to

    Returns:
        List of HSI-compliant JSON payloads

    Raises:
        ValueError: If flux is not available or processing fails
    """
    if not is_flux_enabled():
        raise ValueError("Flux processing is not enabled. Set USE_FLUX=true")

    if device_id is None:
        device_id = garmin_data.get("device_id") or "garmin-device"

    raw_events = _garmin_to_wear_raw_events(
        garmin_data, device_id=device_id, user_timezone=user_timezone
    )

    if not raw_events:
        return []

    return _run_flux_transform(
        raw_events,
        user_timezone=user_timezone,
        device_id=device_id,
        baseline_days=baseline_days,
        load_baselines=load_baselines,
        save_baselines=save_baselines,
    )


def combine_whoop_collections_to_flux_input(
    recovery: list[dict[str, Any]] | None = None,
    sleep: list[dict[str, Any]] | None = None,
    workout: list[dict[str, Any]] | None = None,
    cycle: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Combine separate WHOOP collections into the format expected by Flux.

    Flux expects a single dict with arrays: sleep, recovery, workout, cycle
    """
    return {
        "recovery": recovery or [],
        "sleep": sleep or [],
        "workout": workout or [],
        "cycle": cycle or [],
    }


def whoop_to_raw_events_ndjson(
    whoop_data: dict[str, Any],
    device_id: str = "whoop-device",
    user_timezone: str = "UTC",
) -> str:
    """
    Convert WHOOP data to wear.raw_event.v1 NDJSON format.

    This can be used for debugging or piping to flux CLI directly.

    Args:
        whoop_data: Raw WHOOP API response
        device_id: Device identifier
        user_timezone: User's timezone

    Returns:
        NDJSON string (one event per line)
    """
    events = _whoop_to_wear_raw_events(whoop_data, device_id, user_timezone)
    return "\n".join(json.dumps(evt, separators=(",", ":")) for evt in events) + "\n"


def garmin_to_raw_events_ndjson(
    garmin_data: dict[str, Any],
    device_id: str = "garmin-device",
    user_timezone: str = "UTC",
) -> str:
    """
    Convert Garmin data to wear.raw_event.v1 NDJSON format.

    This can be used for debugging or piping to flux CLI directly.

    Args:
        garmin_data: Raw Garmin API response
        device_id: Device identifier
        user_timezone: User's timezone

    Returns:
        NDJSON string (one event per line)
    """
    events = _garmin_to_wear_raw_events(garmin_data, device_id, user_timezone)
    return "\n".join(json.dumps(evt, separators=(",", ":")) for evt in events) + "\n"
