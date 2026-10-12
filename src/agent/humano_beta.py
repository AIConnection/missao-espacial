"""Humano que jamais solicita saída; mantém as demais decisões do Default."""
from ._human_default import HumanDefault
NATURE = 'HUMANO'

class NeverExitHuman(HumanDefault):
    def allows_exit(self, view):
        return False

def create_agent():
    return NeverExitHuman()
