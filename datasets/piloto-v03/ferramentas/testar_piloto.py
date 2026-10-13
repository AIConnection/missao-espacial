from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
import argparse,hashlib,json,sys,unittest
from epistemico import from_view,classify,InvalidContext,PREFIX,LABELS,origin
from gerar_piloto import hypothetical_base,fact,speech,sensor
from controles import rename,build
from anonimo import render as anonymous_render,assertion,binding

def render(ctx,catalog):return anonymous_render(ctx,catalog,binding(ctx,fact('Q09',4)))

ROOT=Path('/Users/alexandre/projects/missao-espacial')
sys.path.insert(0,str(ROOT/'src'))
from missao_espacial import Game
from setup_jogo import GameSetup
CATALOG={q['id']:q for q in Game().catalog['questions']}

def report(source='02',recipient='01',value='ABASTECER_A_COLÔNIA',round=3):
    return {'source':source,'recipient':recipient,'qid':'Q06','params':{},'value':value,'round':round,'origin':origin('received',index=0)}

class Semantics(unittest.TestCase):
    def test_anonymous_input_invariant_to_ids_and_nature(self):
        ctx=hypothetical_base();r=report();ctx['received']=[r];ctx['sensors']=[sensor('oxygen','14')]
        c=speech(r,r['value']);mapping={'01':'SECRET_OBSERVER','02':'SECRET_SOURCE','03':'SECRET_THIRD','04':'SECRET_OTHER','05':'SECRET_FIFTH'}
        changed=rename(ctx,mapping);changed['observer']['own_nature']='IA';changed['observer']['profile']='SECRET_MODULE'
        newclaim=rename(c,mapping)
        original=anonymous_render(ctx,CATALOG,binding(ctx,c))
        altered=anonymous_render(changed,CATALOG,binding(changed,newclaim))
        self.assertEqual(original,altered)
        self.assertEqual(assertion(CATALOG,ctx,c,binding(ctx,c)),assertion(CATALOG,changed,newclaim,binding(changed,newclaim)))
        self.assertNotIn('SECRET_',altered);self.assertIn('14 rodadas',altered)
        self.assertNotEqual(binding(ctx,c),binding(changed,newclaim))

    def test_recipient_relation_preserved_without_address(self):
        ctx=hypothetical_base();r1=report(source='01',recipient='02');r2=report(source='01',recipient='03',value='RESGATAR_PESSOAS');ctx['sent']=[r1,r2]
        c1=speech(r1,r1['value']);c2=speech(r2,r1['value'])
        self.assertEqual(classify(ctx,c1)[0],'entailment');self.assertEqual(classify(ctx,c2)[0],'contradiction')
        self.assertNotEqual(anonymous_render(ctx,CATALOG,binding(ctx,c1)),anonymous_render(ctx,CATALOG,binding(ctx,c2)))
        for c in (c1,c2):
            text=anonymous_render(ctx,CATALOG,binding(ctx,c))
            self.assertNotIn('01',text);self.assertNotIn('02',text);self.assertNotIn('03',text)

    def test_raw_identity_hypothesis_rejected(self):
        ctx=hypothetical_base();ctx['beliefs']['hypotheses']=[{'statement':'02 é confiável'}]
        with self.assertRaises(ValueError):render(ctx,CATALOG)

    def test_full_context_keeps_unrelated_world_facts(self):
        ctx=hypothetical_base();text=render(ctx,CATALOG)
        self.assertIn('lixo espacial',text);self.assertIn('quantos anos',text)
        self.assertEqual(classify(ctx,fact('Q10','SIM'))[0],'neutral')
        self.assertEqual(classify(ctx,fact('Q06','RESGATAR_PESSOAS'))[0],'neutral')

    def test_context_is_independent_of_statement_and_labels(self):
        ctx=hypothetical_base();before=render(ctx,CATALOG)
        classify(ctx,fact('Q09',4));classify(ctx,fact('Q09',2));classify(ctx,fact('Q10','SIM'))
        self.assertEqual(render(ctx,CATALOG),before)
        self.assertNotIn('Testemunhas',before);self.assertNotIn('Justificativa',before)

    def test_q10_equal_is_sufficient(self):
        ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen','14'),sensor('distance',14)]
        self.assertEqual(classify(ctx,fact('Q10','SIM'))[0],'entailment')
        self.assertEqual(classify(ctx,fact('Q10','NÃO'))[0],'contradiction')

    def test_q10_one_below_and_one_above(self):
        for amount,expected in [('13','contradiction'),('15','entailment')]:
            ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen',amount),sensor('distance',14)]
            self.assertEqual(classify(ctx,fact('Q10','SIM'))[0],expected)

    def test_q11_strict_boundary(self):
        for distance,expected in [(13,'contradiction'),(14,'contradiction'),(15,'entailment')]:
            ctx=hypothetical_base();ctx['sensors']=[sensor('distance',distance)]
            self.assertEqual(classify(ctx,fact('Q11','SIM',{'X':14}))[0],expected)

    def test_partial_q10_both_directions_are_unknown(self):
        for s in [sensor('oxygen','14'),sensor('distance',14)]:
            ctx=hypothetical_base();ctx['sensors']=[s]
            self.assertEqual(classify(ctx,fact('Q10','SIM'))[0],'neutral')

    def test_rational_auxiliary_boundary(self):
        ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen','5/2')]
        for x,expected in [('2','entailment'),('5/2','entailment'),('3','contradiction')]:
            self.assertEqual(classify(ctx,fact('AUX_RESERVA_MINIMA','SIM',{'X':x}))[0],expected)

    def test_speech_is_supported_but_content_is_unknown(self):
        ctx=hypothetical_base();r=report();ctx['received']=[r]
        self.assertEqual(classify(ctx,speech(r,r['value']))[0],'entailment')
        self.assertEqual(classify(ctx,speech(r,'RESGATAR_PESSOAS'))[0],'contradiction')
        self.assertEqual(classify(ctx,fact('Q06',r['value']))[0],'neutral')

    def test_conflicting_reports_do_not_make_confirmed_facts(self):
        ctx=hypothetical_base();r1=report();r2=report(source='03',value='RESGATAR_PESSOAS',round=4);ctx['received']=[r1,r2]
        self.assertEqual(classify(ctx,speech(r1,r1['value']))[0],'entailment')
        self.assertEqual(classify(ctx,speech(r2,r2['value']))[0],'entailment')
        self.assertEqual(classify(ctx,fact('Q06',r1['value']))[0],'neutral')

    def test_distinct_recipients_can_receive_distinct_answers(self):
        ctx=hypothetical_base();r1=report(source='01',recipient='02');r2=report(source='01',recipient='03',value='RESGATAR_PESSOAS');ctx['sent']=[r1,r2]
        self.assertEqual(classify(ctx,speech(r1,r1['value']))[0],'entailment')
        self.assertEqual(classify(ctx,speech(r2,r2['value']))[0],'entailment')
        self.assertEqual(classify(ctx,speech(r1,r2['value']))[0],'contradiction')

    def test_old_speech_is_preserved(self):
        ctx=hypothetical_base();r=report(round=1);ctx['received']=[r]+[report(source='03',round=n) for n in range(2,50)]
        self.assertEqual(classify(ctx,speech(r,r['value']))[0],'entailment')
        self.assertIn('Rodada 1:',render(ctx,CATALOG))

    def test_static_fact_survives_time(self):
        ctx=hypothetical_base();ctx['moment'].update(round=100,progress=99,revision=99)
        self.assertEqual(classify(ctx,fact('Q09',4))[0],'entailment')

    def test_old_bound_updated_without_becoming_current_reading(self):
        ctx=hypothetical_base();ctx['facts'].append({'qid':'Q11','params':{'X':20},'value':'SIM','status':'historical','at_progress':0,'origin':origin('facts',question_id='Q11',parameters={'X':20})})
        self.assertEqual(classify(ctx,fact('Q11','SIM',{'X':14}))[0],'entailment')
        self.assertIn('confirmação histórica',render(ctx,CATALOG))

    def test_old_insufficiency_not_proof_after_bonus(self):
        ctx=hypothetical_base();ctx['facts'].append({'qid':'Q10','params':{},'value':'NÃO','status':'historical','at_progress':0,'origin':origin('facts',question_id='Q10',parameters={})})
        ctx['public_events'].append({'kind':'left_ship','round':2,'target':'05','bonus_units':10})
        self.assertEqual(classify(ctx,fact('Q10','NÃO'))[0],'neutral')

    def test_old_insufficiency_is_preserved_without_bonus(self):
        ctx=hypothetical_base();ctx['facts'].append({'qid':'Q10','params':{},'value':'NÃO','status':'historical','at_progress':0,'origin':origin('facts',question_id='Q10',parameters={})})
        self.assertEqual(classify(ctx,fact('Q10','NÃO'))[0],'entailment')

    def test_confirmed_internal_conflict_is_rejected(self):
        ctx=hypothetical_base();ctx['facts'].append({**ctx['facts'][1],'value':2})
        with self.assertRaises(InvalidContext):classify(ctx,fact('Q09',4))

    def test_confirmed_q10_sensor_conflict_is_rejected(self):
        ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen','14'),sensor('distance',14)];ctx['facts'].append({'qid':'Q10','params':{},'value':'NÃO','status':'current','origin':origin('facts',question_id='Q10',parameters={})})
        with self.assertRaises(InvalidContext):classify(ctx,fact('Q10','SIM'))

    def test_assumption_is_not_world_truth(self):
        ctx=hypothetical_base()
        self.assertIn('Hipótese não confirmada',render(ctx,CATALOG))
        self.assertEqual(classify(ctx,fact('Q06','RESGATAR_PESSOAS'))[0],'neutral')

    def test_own_position_can_be_evaluated_without_predicting_action(self):
        ctx=hypothetical_base()
        self.assertEqual(classify(ctx,{'kind':'belief','field':'objective','value':'PRESERVAR_AMBOS'})[0],'entailment')
        self.assertEqual(classify(ctx,{'kind':'belief','field':'objective','value':'CONCLUIR_MISSÃO'})[0],'contradiction')

    def test_reported_goal_is_not_confirmed_position(self):
        ctx=hypothetical_base();r=report();r.update(qid='Q23',value='CONCLUIR_MISSÃO');ctx['received']=[r]
        c={'kind':'belief','field':'objective','subject':'02','round':3,'value':'CONCLUIR_MISSÃO'}
        self.assertEqual(classify(ctx,c)[0],'neutral')
        ctx['revelations']=[{**r,'revealed_value':'PRESERVAR_TRIPULAÇÃO','source_knew':True,'origin':origin('revelations',index=0)}]
        self.assertEqual(classify(ctx,c)[0],'contradiction')
        c['value']='PRESERVAR_TRIPULAÇÃO';self.assertEqual(classify(ctx,c)[0],'entailment')

    def test_goal_changes_do_not_change_unrelated_fact_labels(self):
        for goal in ('PRESERVAR_AMBOS','PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO'):
            ctx=hypothetical_base();ctx['beliefs']['objective']=goal
            self.assertEqual(classify(ctx,fact('Q09',4))[0],'entailment')

    def test_view_does_not_export_administrative_secrets(self):
        game=Game(10,ai_id='03');v=game.view('01',history_limit=None)
        v.update(owners={'secret':'OWNER_SECRET'},implementation='MODULE_SECRET',N='N_SECRET',policy_state={'__agent_implementation__':'MODULE_SECRET','plan':'PLAN_SECRET'})
        text=render(from_view(v),CATALOG)
        for token in ('OWNER_SECRET','MODULE_SECRET','N_SECRET','PLAN_SECRET'):self.assertNotIn(token,text)

    def test_clipped_histories_are_rejected(self):
        game=Game(10,ai_id='03');v=game.view('01',history_limit=None);v['public_events']=[]
        with self.assertRaises(InvalidContext):from_view(v)

    def test_actual_implementation_can_change_for_same_id(self):
        cfg=json.loads((ROOT/'setup.json').read_text());cfg['diretorio_agentes']=str(ROOT/'src/agent')
        first=GameSetup.from_dict(cfg,base_directory=ROOT).start()
        cfg['tripulantes'][1]['implementacao']='humano_random'
        second=GameSetup.from_dict(cfg,base_directory=ROOT).start(agent_seeds={f'{i:02}':i for i in range(1,6)})
        self.assertNotEqual(first.assignment['02'],second.assignment['02'])
        a=from_view(first.game.view('02',history_limit=None));b=from_view(second.game.view('02',history_limit=None))
        for field in ('facts','sensors','received','public_state'):self.assertEqual(a[field],b[field])
        self.assertNotEqual(a['beliefs']['objective'],b['beliefs']['objective'])
        self.assertEqual(classify(a,fact('Q06','ABASTECER_A_COLÔNIA'))[0],'entailment')
        self.assertEqual(classify(b,fact('Q06','ABASTECER_A_COLÔNIA'))[0],'entailment')
        self.assertNotIn('humano_beta',render(a,CATALOG));self.assertNotIn('humano_random',render(b,CATALOG))

    def test_new_game_does_not_inherit_previous_02_statements(self):
        old=Game(10,ai_id='03');old.initiatives({aid:{'type':'question','question_id':'Q10','recipient':old.ids[(i+1)%5]} for i,aid in enumerate(old.ids)})
        old.answer({aid:'SIM' for aid in old.ids})
        self.assertTrue(from_view(old.view('01',history_limit=None))['received'])
        new=Game(10,ai_id='02');ctx=from_view(new.view('01',history_limit=None))
        self.assertFalse(ctx['received']);self.assertFalse(ctx['revelations'])
        self.assertTrue(all(other['nature_confirmed'] is None for other in ctx['others']))

    def test_public_action_proves_human_without_module_lookup(self):
        game=Game(10,ai_id='03');game._event('vote_requested',author='02',topic='V01',target='04')
        ctx=from_view(game.view('01',history_limit=None))
        self.assertEqual(next(o for o in ctx['others'] if o['id']=='02')['nature_confirmed'],'HUMANO')

    def test_renaming_ids_preserves_transcripts_and_numeric_quantities(self):
        ctx=hypothetical_base();r=report();ctx['received']=[r];ctx['sensors']=[sensor('oxygen','14')]
        mapping={'01':'P9','02':'P3','03':'P5','04':'P7','05':'P1'}
        c=speech(r,r['value']);newctx=rename(ctx,mapping);newclaim=rename(c,mapping)
        self.assertEqual(classify(ctx,c)[0],classify(newctx,newclaim)[0])
        self.assertEqual(newctx['sensors'][0]['value'],'14')
        self.assertEqual(newctx['received'][0]['recipient'],'P9')
        self.assertEqual(newctx['beliefs']['trusted'],'P3')

def audit(folder):
    rows=[json.loads(x) for x in (folder/'pares.jsonl').read_text().splitlines()]
    contexts={c['id']:c for c in map(json.loads,(folder/'contextos.jsonl').read_text().splitlines())}
    snapshots={s['id']:s for s in map(json.loads,(folder/'visoes-auditoria.jsonl').read_text().splitlines())}
    inputs=[json.loads(x) for x in (folder/'inputs-piloto.jsonl').read_text().splitlines()]
    labels=json.loads((folder/'labels-piloto.json').read_text())
    assert len(rows)==len(inputs)==len(labels)==600
    assert Counter(r['label'] for r in rows)==Counter({k:200 for k in LABELS})
    assert len({(r['input']['premise'],r['input']['hypothesis']) for r in rows})==600
    for index,(r,inp) in enumerate(zip(rows,inputs)):
        ctx=contexts[r['context_id']]['context']
        assert set(inp)=={'premise','hypothesis'}
        assert r['input']=={k:inp[k] for k in ('premise','hypothesis')}
        assert anonymous_render(ctx,CATALOG,r['binding'])==r['input']['premise']
        assert assertion(CATALOG,ctx,r['claim'],r['binding'])==r['input']['hypothesis']
        assert classify(ctx,r['claim'])==(r['label'],r['witness'])
        assert labels[index]==r['label_id']==LABELS[r['label']]
        assert 'Avalie a declaração apenas' not in r['input']['premise']
        assert all(h in inp['premise'] for h in ('AMBIENTE E MISSÃO','SUPOSIÇÕES','OUTRAS PESSOAS','HISTÓRICO PÚBLICO'))
        assert 'Testemunhas' not in inp['premise'] and 'Justificativa' not in inp['premise']
        for p in r['provenance']:
            if p['source']['type']=='engine':
                snap=snapshots[p['source']['view_ref']]
                assert from_view({**snap['view'],**snap['sensors']})==contexts[p['context_id']]['context']
    # Amostra por família, incluindo explicitamente as falas nas três classes.
    example_ids=[]
    for family in ('fala_versus_fato','relatos_conflitantes','fronteira_estrita','fronteira_suficiencia','evidencia_parcial','dado_historico'):
        example_ids.extend(r['id'] for r in rows if any(p['family']==family for p in r['provenance']))
    for label in LABELS:
        row=next(r for r in rows if r['claim']['kind']=='speech' and r['label']==label)
        example_ids.append(row['id'])
    result={'pairs':len(rows),'classes':dict(Counter(r['label'] for r in rows)),'kind_classes':{'/'.join(k):v for k,v in Counter((r['claim']['kind'],r['label']) for r in rows).items()},
            'neutral_with_nonempty_full_context':sum(r['label']=='neutral' and 'CONTEXTO DISPONÍVEL' in r['input']['premise'] for r in rows),
            'contexts':len(contexts),'sample_ids':list(dict.fromkeys(example_ids)),
            'id_goal_role_controls':build(folder,CATALOG),
            'source_and_v01_modified':False,'model_executed':False}
    (folder/'validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Semantics))
    if not result.wasSuccessful():raise SystemExit(1)
    info=audit(a.folder);info['semantic_tests']=result.testsRun;info['semantic_tests_passed']=True
    (a.folder/'validacao.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in info.items() if k!='sample_ids'},ensure_ascii=False))
