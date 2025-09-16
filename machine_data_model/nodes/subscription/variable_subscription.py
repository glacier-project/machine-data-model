from enum import IntFlag, auto


class EventType(IntFlag):
    DATA_CHANGE = auto()
    OUT_OF_RANGE = auto()
    IN_RANGE = auto()
    ANY = DATA_CHANGE | OUT_OF_RANGE | IN_RANGE


class VariableSubscription:
    def __init__(self, subscriber_id: str, correlation_id: str):
        self.subscriber_id = subscriber_id
        self.correlation_id = correlation_id
        # TODO: add more fields as needed, e.g., subscription type, thresholds, etc.

    pass
