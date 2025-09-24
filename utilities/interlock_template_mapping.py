from enum import Enum


class InterlockTemplateMapping(str, Enum):
    INTERLOCK_ALERT = "interlock_alert_activation.html"
    INTERLOCK_ALERT_CLOSURE = "interlock_alert_closure.html"
    INTERLOCK_ESCALATE = "interlock_escalate.html"
    INTERLOCK_EXCEPTION = "interlock_exception.html"
    BLOCKING_ALERT = "vts_truck_blocking.html"
    VTS_REJECTED = "vts_truck_unblocking_rejected.html"
    VTSJUSTIFIED = "vts_truck_blocked_justification.html"
    VTSRESOLVED = "vts_truck_unblocked.html"
    SENDITBACK = "vts_interlock_senditback.html"
    VTSACCEPT = "vts_blocking_accepted.html"
    BLACKLISTED = "vts_truck_blacklisted.html"


class TemplateMapping(str, Enum):
    ACTIVE = "INTERLOCK_ALERT"
    NOTIFY = "INTERLOCK_ALERT"
    REJECT = "INTERLOCK_ALERT"
    ESCALATION = "INTERLOCK_ESCALATE"
    EXCEPTION = "INTERLOCK_EXCEPTION"
    BLOCK = ""
    UNBLOCK = ""
    JUSTIFIED="INTERLOCK_ALERT"
    RESOLVED=""
    BLOCKING="BLOCKING_ALERT"
    VTSREJECTED="VTS_REJECTED"
    VTSJUSTIFIED="VTS_JUSTIFIED"
    VTSRESOLVED="VTS_RESOLVED"
    SENDITBACK="VTS_SENDITBACK"
    VTSACCEPT="VTS_ACCEPT"
    BLACKLISTED="BLACKLISTED"