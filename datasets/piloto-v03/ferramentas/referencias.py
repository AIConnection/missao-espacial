"""Referências descartáveis por chamada; correspondência somente na aplicação."""
from copy import deepcopy
import random,secrets

PERSON_FIELDS={'id','source','recipient','author','target','controller','agent','agente','alvo','subject','trusted'}
PERSON_LISTS={'participants','candidates','blockers'}
PERSON_MAPS={'votes','expulsion'}

def participants(ctx):
    found=set()
    def collect(value,parent=None):
        if isinstance(value,list):
            if parent in PERSON_LISTS:found.update(x for x in value if isinstance(x,str))
            else:
                for item in value:collect(item)
        elif isinstance(value,dict):
            for key,item in value.items():
                if key in PERSON_FIELDS and isinstance(item,str):found.add(item)
                elif key in PERSON_MAPS and isinstance(item,dict):
                    found.update(item)
                    if key=='votes':found.update(x for x in item.values() if isinstance(x,str) and x not in ('A_FAVOR','CONTRA','ABSTENÇÃO'))
                elif key in ('value','revealed_value') and value.get('qid')=='Q19' and isinstance(item,str) and item not in ('NÃO_SEI','RECUSO_RESPONDER'):found.add(item)
                else:collect(item,key)
    collect(ctx)
    return found

class ReferenceFrame:
    def __init__(self,ctx,*,nonce=None):
        # O nonce é externo e não deve ser serializado para o modelo.
        self.nonce=nonce if nonce is not None else secrets.token_hex(32)
        people=sorted(participants(ctx));slots=list(range(1,len(people)+1))
        random.Random(self.nonce).shuffle(slots)
        self.to_reference={person:f'participante temporário {slot}' for person,slot in zip(people,slots)}
        self.to_person={reference:person for person,reference in self.to_reference.items()}
        if len(self.to_reference)!=len(self.to_person):raise ValueError('Referências não são distintas')
    def ref(self,person):
        try:return self.to_reference[person]
        except KeyError:raise ValueError('Pessoa ausente do vínculo autorizado') from None
    def resolve(self,reference):return self.to_person[reference]
    def routing(self):return {'nonce':self.nonce,'references':deepcopy(self.to_reference)}
