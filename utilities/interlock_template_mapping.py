from enum import Enum


class InterlockTemplateMapping(str, Enum):
    INTERLOCK_ALERT = "interlock_alert_activation.html"
    INTERLOCK_ALERT_CLOSURE = "interlock_alert_closure.html"
    INTERLOCK_ESCALATE = "interlock_escalate.html"
    INTERLOCK_EXCEPTION = "interlock_exception.html"
    BLOCKING_ALERT = "interlock_truck_blocking.html"


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