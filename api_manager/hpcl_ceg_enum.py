
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
    InProgress = 'InProgress'
    Cancel = 'Cancel'
    OnHold = 'OnHold'







class AlertState(str, enum.Enum):
    InProgress = 'InProgress'
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
    interLockOk = 'interLockOk'
    Message = 'Message'
    excApprovalTimeExp = 'excApprovalTimeExp'
    Raised = 'Raised'
    Cancelled = 'Cancelled'







class IndentStatus(str, enum.Enum):
    Pending = 'Pending'
    IndentRaised = 'IndentRaised'
    IndentOnHold = 'IndentOnHold'
    IndentOnHoldReleased = 'IndentOnHoldReleased'
    Cancelled = 'Cancelled'
    TruckAllocated = 'TruckAllocated'
    Transit = 'Transit'
    InvoiceCreated = 'InvoiceCreated'
    ValidIndent = 'ValidIndent'
    SentToSAP = 'SentToSAP'
    SalesOrderPlaced = 'SalesOrderPlaced'
    Completed = 'Completed'




