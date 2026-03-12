"""
Email notification system (Spec Section 16.2 — P3 Future Enhancement).

Architecture is in place from day one; actual email sending to be implemented
when SMTP/email service is configured.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class Notification:
    """A notification to send to a user."""
    user_id: str
    subject: str
    body: str
    insurer: str | None = None
    metric: str | None = None
    severity: str = "info"


def check_notification_triggers(
    user_id: str,
    watched_metrics: list[str],
    anomalies: list[dict],
) -> list[Notification]:
    """
    Check if any anomalies match a user's watched metrics.

    Returns list of Notification objects ready to send.
    """
    notifications = []

    for anomaly in anomalies:
        metric = anomaly.get("metric", "")
        if metric in watched_metrics or not watched_metrics:
            notifications.append(Notification(
                user_id=user_id,
                subject=f"IBT Alert: {anomaly['insurer']} — {metric}",
                body=anomaly.get("description", ""),
                insurer=anomaly.get("insurer"),
                metric=metric,
                severity=anomaly.get("severity", "info"),
            ))

    return notifications


def send_notification(notification: Notification) -> bool:
    """
    Send a notification to a user.

    Currently logs the notification. Email integration to be added when
    SMTP configuration is available.
    """
    log.info(
        "Notification for %s: %s — %s",
        notification.user_id,
        notification.subject,
        notification.body[:100],
    )
    # TODO: Implement email sending via SMTP or external service
    # when EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD are configured
    return True
