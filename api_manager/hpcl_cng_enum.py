
import enum



class BusinessUnit(str, enum.Enum):
    RO = 'RO'
    TAS = 'TAS'
    LPG = 'LPG'
    RDI = 'RDI'
    CP = 'CP'







class NotificationLevel(str, enum.Enum):
    InitialNotification = 'InitialNotification'
    InitialEscalation = 'InitialEscalation'







class AlertStatus(str, enum.Enum):
    Open = 'Open'
    Close = 'Close'







class AlertState(str, enum.Enum):
    Notified = 'Notified'
    Escalated = 'Escalated'
    Resolved = 'Resolved'







class Severity(str, enum.Enum):
    Low = 'Low'
    Medium = 'Medium'
    High = 'High'
    Critical = 'Critical'







class LocationHealth(str, enum.Enum):
    Normal = 'Normal'
    Failed = 'Failed'
    Deactivated = 'Deactivated'







class AlertActionType(str, enum.Enum):
    Justification = 'Justification'
    Rejected = 'Rejected'
    Approved = 'Approved'
    Override = 'Override'




