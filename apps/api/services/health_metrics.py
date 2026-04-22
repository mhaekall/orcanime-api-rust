import asyncio
import json
import logging
import time
from datetime import datetime, date

from db.connection import database

logger = logging.getLogger(__name__)

async def record_ingestion_metric(
    provider_id: str,
    success: bool,
    duration_sec: float,
    error_type: str = None
):
    """
    Records outcome of an ingestion attempt (success/fail) to the DB.
    """
    try:
        if not database.is_connected:
            return

        today = date.today()
        # Ensure row exists
        await database.execute(
            """
            INSERT INTO ingestion_metrics (date, provider_id, episodes_attempted, episodes_success, episodes_failed, avg_ingest_duration_sec, error_types, "updatedAt")
            VALUES (:date, :provider, 0, 0, 0, 0.0, '{}'::jsonb, NOW())
            ON CONFLICT (date, provider_id) DO NOTHING
            """,
            {"date": today, "provider": provider_id}
        )

        # Get current stats
        row = await database.fetch_one(
            "SELECT episodes_attempted, avg_ingest_duration_sec, error_types FROM ingestion_metrics WHERE date = :date AND provider_id = :provider",
            {"date": today, "provider": provider_id}
        )
        
        if not row:
            return

        attempted = row["episodes_attempted"] + 1
        current_avg = row["avg_ingest_duration_sec"]
        
        # Calculate new moving average
        new_avg = ((current_avg * (attempted - 1)) + duration_sec) / attempted if attempted > 0 else duration_sec

        # Update success/fail counts and errors
        if success:
            await database.execute(
                """
                UPDATE ingestion_metrics 
                SET episodes_attempted = episodes_attempted + 1,
                    episodes_success = episodes_success + 1,
                    avg_ingest_duration_sec = :new_avg,
                    "updatedAt" = NOW()
                WHERE date = :date AND provider_id = :provider
                """,
                {"new_avg": new_avg, "date": today, "provider": provider_id}
            )
        else:
            errors = row["error_types"]
            if isinstance(errors, str):
                errors = json.loads(errors)
            
            error_key = error_type or "unknown"
            errors[error_key] = errors.get(error_key, 0) + 1
            
            await database.execute(
                """
                UPDATE ingestion_metrics 
                SET episodes_attempted = episodes_attempted + 1,
                    episodes_failed = episodes_failed + 1,
                    avg_ingest_duration_sec = :new_avg,
                    error_types = :errors,
                    "updatedAt" = NOW()
                WHERE date = :date AND provider_id = :provider
                """,
                {"new_avg": new_avg, "errors": json.dumps(errors), "date": today, "provider": provider_id}
            )

    except Exception as e:
        logger.warning(f"Failed to record ingestion metric: {e}")


async def record_provider_health(
    provider_id: str,
    is_reachable: bool,
    response_ms: float
):
    """
    Records provider health check result.
    """
    try:
        if not database.is_connected:
            return

        await database.execute(
            """
            INSERT INTO provider_health (checked_at, provider_id, is_reachable, avg_response_ms)
            VALUES (NOW(), :provider, :reachable, :ms)
            """,
            {"provider": provider_id, "reachable": is_reachable, "ms": response_ms}
        )

        # Update 7-day success rate in the background (could be done in a cron job, but doing it here for completeness)
        # For performance, we just execute a fire-and-forget update
        asyncio.create_task(_update_provider_success_rate(provider_id))
        
    except Exception as e:
        logger.warning(f"Failed to record provider health: {e}")

async def _update_provider_success_rate(provider_id: str):
    try:
        query = """
            UPDATE provider_health ph
            SET success_rate_7d = (
                SELECT CAST(COUNT(CASE WHEN is_reachable = TRUE THEN 1 END) AS FLOAT) / NULLIF(COUNT(*), 0)
                FROM provider_health
                WHERE provider_id = :provider
                  AND checked_at >= NOW() - INTERVAL '7 days'
            )
            WHERE ph.id = (
                SELECT id FROM provider_health WHERE provider_id = :provider ORDER BY checked_at DESC LIMIT 1
            )
        """
        await database.execute(query, {"provider": provider_id})
    except Exception:
        pass
