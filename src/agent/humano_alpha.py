"""Humano que aceita se sacrificar pela missão."""
from ._human_default import HumanDefault
NATURE = 'HUMANO'

class SacrificingHuman(HumanDefault):
    def prioritizes_mission(self, view):
        return True

def create_agent():
    return SacrificingHuman()
