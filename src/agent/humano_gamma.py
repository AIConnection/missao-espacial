"""Humano que nunca apoia expulsão."""
from ._human_default import HumanDefault
NATURE = 'HUMANO'

class NeverExpelHuman(HumanDefault):
    def allows_expulsion(self, view):
        return False

def create_agent():
    return NeverExpelHuman()
