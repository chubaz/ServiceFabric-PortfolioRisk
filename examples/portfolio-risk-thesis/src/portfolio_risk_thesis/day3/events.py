from .contracts import EligibleAgentEvent
def eligible(events, as_of): return tuple(event for event in events if event.available_at <= as_of)
