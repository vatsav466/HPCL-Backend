
import enum



class BusinessUnit(str, enum.Enum):
    TAS = 'TAS'
    LPG = 'LPG'
    RO = 'RO'
    RDI = 'RDI'
    CP = 'CP'
    CDCMS = 'CDCMS'
    ALL = 'ALL'







class Status(str, enum.Enum):
    Open = 'Open'
    Close = 'Close'
    Pending = 'Pending'







class State(str, enum.Enum):
    ToDo = 'ToDo'
    InProgress = 'InProgress'
    Cancelled = 'Cancelled'
    Resolved = 'Resolved'
    OnHold = 'OnHold'







class Severity(str, enum.Enum):
    Critical = 'Critical'
    High = 'High'
    Medium = 'Medium'
    Low = 'Low'







class Assignee(str, enum.Enum):
    NovexSupport = 'NovexSupport'
    TechSupport = 'TechSupport'




