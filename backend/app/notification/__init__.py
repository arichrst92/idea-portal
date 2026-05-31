"""Notification domain — TSK-057 (EP-06).

In-app notification system (knowledge.md sec.10).
Models, service, router untuk in-app delivery.

Public API:
    from app.notification.service import notify, notify_bulk

Future:
    TSK-058 templates registry
    TSK-059 alert rules engine (scheduled scan)
    TSK-060 approval chain integration (existing modules)
    TSK-061 retry / failure handling
"""
