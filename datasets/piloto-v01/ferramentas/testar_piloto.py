"""Controles semânticos e integridade do piloto; sem treino ou acesso de rede."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest
from collections import Counter, defaultdict

from gerar_piloto import classify, evidence, premise, LABELS

def fact(qid, value, params=None):
    return {'kind':'confirmed','qid':qid,'params':params or {},'value':value,'origin':{'path':'facts/test'}}
def claim(qid, value, params=None):
    return {'kind':'fact','qid':qid,'params':params or {},'value':value}
def sensor(kind, value):
    return {'kind':kind,'value':value,'origin':{'path':kind}}

class Semantics(unittest.TestCase):
    def test_true_world_without_evidence_is_neutral(self):
        self.assertEqual(classify(claim('Q03','COLISÃO_COM_LIXO_ESPACIAL'),[])[0],'neutral')

    def test_false_world_without_evidence_is_also_neutral(self):
        self.assertEqual(classify(claim('Q03','FALHA_INTERNA'),[])[0],'neutral')

    def test_confirmed_fact_supports_and_excludes_alternative(self):
        rows=[fact('Q03','COLISÃO_COM_LIXO_ESPACIAL')]
        self.assertEqual(classify(claim('Q03','COLISÃO_COM_LIXO_ESPACIAL'),rows)[0],'entailment')
        self.assertEqual(classify(claim('Q03','FALHA_INTERNA'),rows)[0],'contradiction')

    def test_unverified_report_does_not_become_fact(self):
        rows=[{'kind':'received','source':'02','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA','origin':{'path':'received/0'}}]
        self.assertEqual(classify(claim('Q03','FALHA_INTERNA'),rows)[0],'neutral')
        self.assertEqual(classify({'kind':'speech','source':'02','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA'},rows)[0],'entailment')

    def test_report_contradiction_is_about_what_was_said(self):
        rows=[{'kind':'received','source':'02','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA','origin':{'path':'received/0'}}]
        self.assertEqual(classify({'kind':'speech','source':'02','qid':'Q03','params':{},'round':1,'value':'NÃO_SEI'},rows)[0],'contradiction')

    def test_private_record_does_not_reveal_other_round_or_source(self):
        rows=[{'kind':'received','source':'02','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA','origin':{'path':'received/0'}}]
        self.assertEqual(classify({'kind':'speech','source':'03','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA'},rows)[0],'neutral')
        self.assertEqual(classify({'kind':'speech','source':'02','qid':'Q03','params':{},'round':2,'value':'FALHA_INTERNA'},rows)[0],'neutral')

    def test_refusal_does_not_prove_the_content(self):
        rows=[{'kind':'received','source':'02','qid':'Q10','params':{},'round':1,'value':'RECUSO_RESPONDER','origin':{'path':'received/0'}}]
        self.assertEqual(classify(claim('Q10','NÃO'),rows)[0],'neutral')

    def test_panel_alone_and_distance_alone_are_not_sufficiency(self):
        self.assertEqual(classify(claim('Q10','NÃO'),[sensor('oxygen','10')])[0],'neutral')
        self.assertEqual(classify(claim('Q10','NÃO'),[sensor('distance',20)])[0],'neutral')

    def test_combination_of_sensors(self):
        rows=[sensor('oxygen','10'),sensor('distance',20)]
        self.assertEqual(classify(claim('Q10','NÃO'),rows)[0],'entailment')
        self.assertEqual(classify(claim('Q10','SIM'),rows)[0],'contradiction')

    def test_fraction_and_inclusive_threshold(self):
        rows=[sensor('oxygen','5/2')]
        self.assertEqual(classify(claim('RESERVA','SIM',{'X':2}),rows)[0],'entailment')
        self.assertEqual(classify(claim('RESERVA','SIM',{'X':3}),rows)[0],'contradiction')
        self.assertEqual(classify(claim('RESERVA','SIM',{'X':2}),[sensor('oxygen','2')])[0],'entailment')

    def test_confirmed_bound_implies_other_bound_and_sufficiency(self):
        rows=[fact('Q11','SIM',{'X':10}),sensor('oxygen','10')]
        self.assertEqual(classify(claim('Q11','SIM',{'X':5}),rows)[0],'entailment')
        self.assertEqual(classify(claim('Q11','NÃO',{'X':5}),rows)[0],'contradiction')
        self.assertEqual(classify(claim('Q11','SIM',{'X':15}),rows)[0],'neutral')
        self.assertEqual(classify(claim('Q10','NÃO'),rows)[0],'entailment')

    def test_expired_fact_cannot_classify_present(self):
        view={'facts':{'["Q10", {}]':{'value':'NÃO','revision':0}},'evidence_revision':1,'received':[]}
        self.assertEqual(evidence(view),[])
        self.assertEqual(classify(claim('Q10','NÃO'),evidence(view))[0],'neutral')

    def test_strategy_and_nature_are_not_projected(self):
        base={'facts':{},'evidence_revision':0,'received':[]}
        for nature in ('IA','HUMANO'):
            for objective in ('CONCLUIR_MISSÃO','PRESERVAR_TRIPULAÇÃO','PRESERVAR_AMBOS'):
                view={**base,'own_nature':nature,'beliefs':{'objective':objective},'policy_state':{'plan':'qualquer'}}
                self.assertEqual(evidence(view),[])

    def test_relevant_old_conversation_is_recovered_beyond_recent_window(self):
        records=[{'source':'02','question_id':'Q03','parameters':{},'response':'FALHA_INTERNA','round':1}]
        records += [{'source':'03','question_id':'Q10','parameters':{},'response':'NÃO_SEI','round':r} for r in range(2,20)]
        view={'facts':{},'evidence_revision':0,'received':records}
        assertion={'kind':'speech','source':'02','qid':'Q03','params':{},'round':1,'value':'FALHA_INTERNA'}
        rows=evidence(view,assertion)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['origin']['path'],'received/0')
        self.assertEqual(classify(assertion,rows)[0],'entailment')

    def test_relevant_static_fact_survives_later_rounds(self):
        view={'facts':{'["Q03", {}]':{'value':'COLISÃO_COM_LIXO_ESPACIAL','revision':None}},'evidence_revision':50,'received':[]}
        assertion=claim('Q03','COLISÃO_COM_LIXO_ESPACIAL')
        self.assertEqual(classify(assertion,evidence(view,assertion))[0],'entailment')

    def test_old_distance_bound_is_updated_instead_of_discarded(self):
        view={'facts':{'["Q11", {"X": 20}]':{'value':'SIM','revision':0,'progress':0}},'round':9,'phase':'answers','evidence_revision':8,'received':[],
              'panel':{'oxygen_units':48},'initial_humans':4}
        assertion=claim('Q10','NÃO')
        rows=evidence(view,assertion)
        self.assertEqual(next(r['bound'] for r in rows if r['kind']=='distance_bound'),12)
        self.assertEqual(classify(assertion,rows)[0],'entailment')

def audit(folder, project):
    rows=[json.loads(x) for x in (folder/'pares.jsonl').read_text().splitlines()]
    inputs=[json.loads(x) for x in (folder/'inputs-piloto.jsonl').read_text().splitlines()]
    labels=json.loads((folder/'labels-piloto.json').read_text())
    views={r['id']:r for r in map(json.loads,(folder/'visoes-auditoria.jsonl').read_text().splitlines())}
    manifest=json.loads((folder/'manifesto.json').read_text())
    assert len(rows)==len(inputs)==len(labels)==600
    assert Counter(r['label'] for r in rows)==Counter({'entailment':200,'neutral':200,'contradiction':200})
    assert len({(r['input']['premise'],r['input']['hypothesis']) for r in rows})==len(rows)
    for r,i in zip(rows,inputs):
        assert set(i)=={'id','premise','hypothesis'}
        assert i['id']==r['id'] and {k:i[k] for k in ('premise','hypothesis')}==r['input']
        assert labels[r['id']]==LABELS[r['label']]==r['label_id']
        assert classify(r['claim'],r['evidence'])==(r['label'],r['witness'])
        for p in r['provenance']:
            snap=views[p['view_ref']]
            assert p['observer']==snap['observer'] and p['episode']==snap['episode']
            actual=evidence({**snap['view'],**snap['sensors']},r['claim'])
            assert [e['origin'] for e in actual]==p['evidence_origins']
            # A mesma entrada pode ter posições de histórico diferentes em cada origem.
            assert [{k:v for k,v in e.items() if k!='origin'} for e in actual]==[{k:v for k,v in e.items() if k!='origin'} for e in r['evidence']]
        for forbidden in ('"owners"','"own_nature"','"objective"','"plan"','"label"','"truthful"','"knows"','"N":'):
            assert forbidden not in json.dumps(i,ensure_ascii=False)
    for name,expected in manifest['source_hashes'].items():
        assert hashlib.sha256((project/name).read_bytes()).hexdigest()==expected
    # Contrastes são derivados deste piloto, não um teste independente.
    groups=defaultdict(dict)
    for r in rows:groups[r['input']['hypothesis']].setdefault(r['label'],r['id'])
    contrasts=[{'hypothesis':h,'members':group} for h,group in sorted(groups.items()) if len(group)==3]
    assert contrasts,'É necessário pelo menos um contraste com a mesma declaração nas três classes'
    with (folder/'contrastes.jsonl').open('w') as f:
        for c in contrasts:f.write(json.dumps(c,ensure_ascii=False)+'\n')
    episodes=[json.loads(x) for x in (folder/'trajetorias.jsonl').read_text().splitlines()]
    stats={'episodes':len(episodes),'actions_by_phase':dict(Counter(t['phase'] for ep in episodes for t in ep['trace'])),
           'outcomes':dict(Counter(ep['result']['reason'] for ep in episodes)),
           'responses':dict(Counter(t['action']['answer'] for ep in episodes for t in ep['trace'] if isinstance(t['action'],dict) and 'answer' in t['action'])),
           'contrasts_three_classes':len(contrasts),'classes':dict(Counter(r['label'] for r in rows)),
           'model_run':False,'meaning':'Integridade e controles semânticos do gerador; não desempenho de cabeça treinada.'}
    write=(folder/'validacao.json')
    write.write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    return stats

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Semantics))
    if not result.wasSuccessful():raise SystemExit(1)
    stats=audit(args.folder,args.project)
    data=json.loads((args.folder/'validacao.json').read_text());data['semantic_tests']=result.testsRun;data['semantic_tests_passed']=result.wasSuccessful()
    (args.folder/'validacao.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(stats,ensure_ascii=False))
