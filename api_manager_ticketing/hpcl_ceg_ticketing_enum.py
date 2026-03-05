
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
    Open = 'Open'
    Escalated = 'Escalated'
    UpdatedByInitiator = 'Updated By Initiator'
    ReturnedByOcc = 'Returned By OCC'
    ReviewedByOcc = 'Reviewed By OCC'







class Severity(str, enum.Enum):
    Critical = 'Critical'
    High = 'High'
    Medium = 'Medium'
    Low = 'Low'







class Category(str, enum.Enum):
    TransportationDiscipline = 'Transportation Discipline'
    InventoryManagement = 'Inventory Management'
    SafetyPerformance = 'Safety Performance'
    AssetIntegrity = 'Asset Integrity'
    VTSLiveTracking = 'VTS Live Tracking'







class SubCategory(str, enum.Enum):
    RouteCorrection = 'Route Correction'
    CombinationOfAlerts = 'Combination of Alerts'
    GovernanceITDG = 'Governance – ITDG'
    EMLockingExceptions = 'EM Locking Exceptions'
    TTShortages = 'TT Shortages'
    AutoReco = 'Auto Reco'
    AIMHold = 'AIM Hold'
    AbnormalGainLoss = 'Abnormal Gain Loss'
    NoVTSNoLoad = 'No VTS No Load'
    PMOrders = 'PM Orders'
    FireEngine = 'Fire Engine'
    FireWaterAvailability = 'Fire Water Availability'
    FoamAvailability = 'Foam Availability'
    CCTVVAAnalytics = 'CCTV VA Analytics'
    RouteDeviationWithStoppage = 'Route Deviation with Stoppage'
    RouteDeviationWithoutStoppage = 'Route Deviation without Stoppage'
    StoppageWithoutRouteDeviation = 'Stoppage without Route Deviation'
    NightDriving = 'Night Driving'
    TASVsReconcileDipMonthend = 'Difference in TAS vs Reconcile Dip - Monthend'
    PowerDisconnectAnalysis = 'Power Disconnect Analysis'
    MultipleTTStoppageAtSameSpot = 'Multiple TT Stoppage at Same Spot'







class Assignee(str, enum.Enum):
    NovexSupport = 'NovexSupport'
    TechSupport = 'TechSupport'







class TicketType(str, enum.Enum):
    ToDo = 'TicketRaised'
    InProgress = 'TicketInProgress'
    Cancelled = 'TicketCancelled'
    Resolved = 'TicketResolved'
    OnHold = 'TicketOnHold'
    ReOpen = 'TicketReOpen'
    OnCompleted = 'TicketOnCompleted'







class ContextType(str, enum.Enum):
    Hpcl = 'Hpcl'
    Recon = 'Recon'
    DataValidation = 'DataValidation'




