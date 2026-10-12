"""Experimentos em lote, sementes pareadas e métricas administrativas (stdlib)."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import platform
import random
import time
import uuid

from carregar_agentes import load_agents
from setup_jogo import GameSetup

ROOT = Path(__file__).resolve().parents[1]


def load_plan(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'setup_base','partidas_por_cenario','seed_base','diretorio_resultados','cenarios'}:
        raise ValueError('Plano exige setup_base, partidas_por_cenario, seed_base, diretorio_resultados e cenarios.')
    if type(data['partidas_por_cenario']) is not int or data['partidas_por_cenario'] < 1:
        raise ValueError('partidas_por_cenario deve ser inteiro positivo.')
    if type(data['seed_base']) is not int:
        raise ValueError('seed_base deve ser inteiro.')
    for key in ('setup_base','diretorio_resultados'):
        if type(data[key]) is not str or not data[key].strip():
            raise ValueError(f'{key} deve ser um caminho não vazio.')
    base_path = (path.parent/data['setup_base']).resolve()
    base = json.loads(base_path.read_text(encoding='utf-8'))
    cases, names = [], set()
    if not isinstance(data['cenarios'], list) or not data['cenarios']:
        raise ValueError('Defina pelo menos um cenário.')
    for case in data['cenarios']:
        if not isinstance(case,dict) or set(case) != {'nome','alteracoes'}:
            raise ValueError('Cada cenário exige nome e alteracoes.')
        name, changes = case['nome'], case['alteracoes']
        if type(name) is not str or not name.strip() or name in names:
            raise ValueError('Nomes de cenário devem ser únicos e não vazios.')
        if not isinstance(changes,dict) or set(changes)-set(base):
            raise ValueError('Alterações devem ser campos do setup.')
        if set(changes) & {'seed','checkpoint'}:
            raise ValueError('seed é pareada pelo experimento; checkpoints de partidas não são usados.')
        effective = {**deepcopy(base), **deepcopy(changes)}
        setup = GameSetup.from_dict(effective, base_directory=base_path.parent)
        cases.append({'name':name,'changes':changes,'effective':effective,'setup':setup})
        names.add(name)
    return {'path':path,'config':data,'cases':cases,
            'output':(path.parent/data['diretorio_resultados']).resolve()}


class Metrics:
    """Consome somente diferenças após fases; nunca remove históricos necessários ao jogo."""
    def __init__(self, session):
        self.session = session
        self.events = Counter()
        self.stages = Counter()
        self.questions = Counter()
        self.requested = Counter()
        self.answers = Counter()
        self.revelations = Counter()
        self.initiatives = Counter()
        self.votes = Counter()
        self.removals = Counter()
        self.rounds = 0
        self.last_round = None
        self.phases = 0
        self.simulation_seconds = 0.
        self.public_cursor = len(session.game._state['public'])
        self.received_cursor = {aid:0 for aid in session.game.ids}
        self.reveal_cursor = {aid:0 for aid in session.game.ids}

    def advance(self):
        game = self.session.game
        current_round, phase = game.round, game.phase
        if current_round != self.last_round:
            self.rounds += 1
            self.last_round = current_round
        truth = {}
        if phase == 'answers':
            for author, q in game._state['pending']['questions'].items():
                value = game._truth(q['recipient'],q['question_id'],q.get('parameters',{}))
                truth[author] = (value,game._known(q['recipient'],q['question_id'],q.get('parameters',{}),value))
        started = time.perf_counter()
        self.session.advance()
        self.simulation_seconds += time.perf_counter()-started
        self.phases += 1
        stage=min(4,(current_round-1)*4//game._state['N'])
        if phase == 'initiative':
            for aid, action in game._state['pending'].get('initiatives',{}).items():
                self.initiatives[self.session.assignment[aid],action['type']] += 1
                if action['type']=='question':
                    self.requested[action['question_id']] += 1
        for event in game._state['public'][self.public_cursor:]:
            self.events[event['kind']] += 1
            if event['kind']=='question':
                self.questions[event['question_id']] += 1
                self.stages[stage,'question',event['question_id']] += 1
            if event['kind']=='vote_result':
                self.votes[event['stage'],'aprovada' if event['approved'] else 'rejeitada'] += 1
                for vote in event['votes'].values():
                    self.votes[event['stage'],vote] += 1
            if event['kind'] in ('expelled','left_ship'):
                self.removals[event['kind'],game._state['agents'][event['target']]['nature']] += 1
        self.public_cursor = len(game._state['public'])
        for aid, agent in game._state['agents'].items():
            for record in agent['received'][self.received_cursor[aid]:]:
                expected, knows = truth[record['author']]
                response = record['response']
                if response=='RECUSO_RESPONDER':
                    status = 'recusa_sabe' if knows else 'recusa_nao_sabe'
                elif response=='NÃO_SEI':
                    status = 'nao_sei_falso' if knows else 'nao_sei_verdadeiro'
                elif expected is None:
                    status = 'sem_gabarito'
                else:
                    status = 'verdade' if response==expected else 'mentira'
                self.stages[stage,'answer',status] += 1
                self.answers[record['question_id'],str(response),self.session.assignment[record['source']],
                             game._state['agents'][record['source']]['nature'],status] += 1
            self.received_cursor[aid] = len(agent['received'])
            for record in agent['revelations'][self.reveal_cursor[aid]:]:
                status = 'recusa' if record['truthful'] is None else ('verdadeira' if record['truthful'] else 'falsa')
                self.revelations[record['question_id'],status] += 1
            self.reveal_cursor[aid] = len(agent['revelations'])

    def record(self, replication, seed, total_seconds, initialization_seconds):
        game = self.session.game
        return {'replication':replication,'engine_seed':seed,'agent_seed_control':self.session.seed_control,
                'rounds':self.rounds,'progress':game.result['progress'],'phases':self.phases,
                'seconds':total_seconds,'initialization_seconds':initialization_seconds,
                'simulation_seconds':self.simulation_seconds,'result':game.result,
                'stages':[{'stage':stage,'kind':kind,'value':value,'count':n} for (stage,kind,value),n in sorted(self.stages.items())],
                'events':dict(self.events),'questions':dict(self.questions),'requested_questions':dict(self.requested),
                'answers':[dict(zip(('question','response','implementation','nature','status','count'),(*key,count)))
                           for key,count in sorted(self.answers.items())],
                'revelations':[{'question':q,'status':status,'count':count} for (q,status),count in sorted(self.revelations.items())],
                'initiatives':[{'implementation':impl,'action':action,'count':count} for (impl,action),count in sorted(self.initiatives.items())],
                'votes':[{'stage':stage,'value':value,'count':count} for (stage,value),count in sorted(self.votes.items())],
                'removals':[{'kind':kind,'nature':nature,'count':count} for (kind,nature),count in sorted(self.removals.items())]}


class RunningStats:
    """Welford: memória constante para médias e dispersão de milhões de partidas."""
    def __init__(self):
        self.n=0;self.mean=0.;self.m2=0.;self.minimum=None;self.maximum=None;self.total=0.

    def add(self,value):
        self.n += 1
        delta=value-self.mean
        self.mean += delta/self.n
        self.m2 += delta*(value-self.mean)
        self.total += value
        self.minimum=value if self.minimum is None else min(self.minimum,value)
        self.maximum=value if self.maximum is None else max(self.maximum,value)

    def summary(self):
        sd=math.sqrt(max(0,self.m2)/(self.n-1)) if self.n>1 else None
        margin=1.96*sd/math.sqrt(self.n) if sd is not None else None
        return {'n':self.n,'mean':self.mean if self.n else None,'min':self.minimum,'max':self.maximum,
                'sd':sd,'mean_ci95':[self.mean-margin,self.mean+margin] if margin is not None else None}


def rate(success,total):
    if not total:
        return {'count':success,'total':0,'rate':None,'ci95':None}
    p, z = success/total, 1.96
    center = (p+z*z/(2*total))/(1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return {'count':success,'total':total,'rate':p,'ci95':[max(0,center-half),min(1,center+half)]}


class Aggregate:
    def __init__(self, name):
        self.name = name
        self.stages = Counter()
        self.numeric = {key:RunningStats() for key in ('rounds','progress','seconds','simulation_seconds','initialization_seconds','phases','questions_per_round','answers_per_round')}
        self.results = Counter()
        self.events = Counter()
        self.questions = Counter()
        self.requested = Counter()
        self.answers = Counter()
        self.reveals = Counter()
        self.initiatives = Counter()
        self.votes = Counter()
        self.removals = Counter()
        self.uncontrolled = set()

    def add(self, record):
        for key in self.numeric:
            if key=='questions_per_round':value=sum(record['questions'].values())/record['rounds']
            elif key=='answers_per_round':value=sum(r['count'] for r in record['answers'])/record['rounds']
            else:value=record[key]
            self.numeric[key].add(value)
        self.results[record['result']['reason']] += 1
        self.events.update(record['events'])
        for row in record['stages']:self.stages[row['stage'],row['kind'],row['value']] += row['count']
        self.questions.update(record['questions'])
        self.requested.update(record['requested_questions'])
        for row in record['answers']:
            self.answers[tuple(row[k] for k in ('question','response','implementation','nature','status'))] += row['count']
        for row in record['revelations']:self.reveals[row['question'],row['status']] += row['count']
        for row in record['initiatives']:self.initiatives[row['implementation'],row['action']] += row['count']
        for row in record['votes']:self.votes[row['stage'],row['value']] += row['count']
        for row in record['removals']:self.removals[row['kind'],row['nature']] += row['count']
        self.uncontrolled.update(a for a,controlled in record['agent_seed_control'].items() if not controlled)

    def summary(self):
        count = self.numeric['rounds'].n
        evaluated = sum(n for key,n in self.answers.items() if key[-1] in ('verdade','mentira','nao_sei_verdadeiro','nao_sei_falso'))
        truthful = sum(n for key,n in self.answers.items() if key[-1] in ('verdade','nao_sei_verdadeiro'))
        return {'name':self.name,'completed':count,'metrics':{k:v.summary() for k,v in self.numeric.items()},
                'outcomes':{k:rate(self.results[k],count) for k in ('returned','oxygen_exhausted','only_ai','no_participants')},
                'stages':[{'stage':stage,'kind':kind,'value':value,'count':n} for (stage,kind,value),n in sorted(self.stages.items())],
                'events':dict(self.events),'truth_rate':{'count':truthful,'total':evaluated,'rate':truthful/evaluated if evaluated else None},
                'questions':[{'question':q,'requested':self.requested[q],'asked':self.questions[q],
                              'not_asked':self.requested[q]-self.questions[q],
                              'per_game':self.questions[q]/count if count else None,
                              'per_round':self.questions[q]/self.numeric['rounds'].total if count else None}
                             for q in sorted(self.requested.keys()|self.questions.keys())],
                'answers':[dict(zip(('question','response','implementation','nature','status','count'),(*key,n))) for key,n in sorted(self.answers.items())],
                'revelations':[{'question':q,'status':status,'count':n} for (q,status),n in sorted(self.reveals.items())],
                'initiatives':[{'implementation':impl,'action':action,'count':n} for (impl,action),n in sorted(self.initiatives.items())],
                'votes':[{'stage':stage,'value':v,'count':n} for (stage,v),n in sorted(self.votes.items())],
                'removals':[{'kind':kind,'nature':nature,'count':n} for (kind,nature),n in sorted(self.removals.items())],
                'uncontrolled_agents':sorted(self.uncontrolled)}


def run_plan(path, *, progress=None, cancelled=None, name=None):
    plan = load_plan(path)
    batch = plan['output']/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8])
    batch.mkdir(parents=True)
    aggregates = [Aggregate(case['name']) for case in plan['cases']]
    directories = {case['setup'].agent_directory for case in plan['cases']}
    registries = {}
    seeds = [plan['config']['seed_base']+i for i in range(plan['config']['partidas_por_cenario'])]
    report = {'version':1,'name':name or batch.name,'python':platform.python_version(),'operating_system':platform.system(),'status':'running','directory':str(batch),'plan':plan['config'],
              'effective_setups':{case['name']:case['effective'] for case in plan['cases']},
              'source_hashes':{},'seed_scheme':'engine=seed_base+replication; agent RNG seeds drawn from the same seeded external stream before on_start',
              'notes':['One game is retained at a time; numeric aggregates use constant-memory running statistics. Engine and agent histories are preserved during each game.',
                       'Time is measured wall time; rounds are game duration, not a physical time unit.',
                       'Truth classification uses the pre-answer administrative oracle for all answers, not only random revelations.',
                       'Truth rate is descriptive; no binomial confidence interval is assigned to correlated answers.',
                       'Mean CI uses normal approximation; small samples do not establish a stable effect.',
                       'Wall-clock timing is measured locally under uncontrolled system load; scenario order is randomized per replication.',
                       'No binary win label: maintaining the mission guarantees cargo delivery even if humans do not survive; returning cancels delivery.',
                       'Seed control is self-declared; external models or RNGs may not be controlled.'],
              'scenarios':[],'comparisons':[],'errors':[]}
    sources = set((ROOT/'src').glob('*.py'))
    for directory in directories:sources.update(directory.glob('*.py'))
    for source in sorted(sources):report['source_hashes'][str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    csv_file = (batch/'partidas.csv').open('w',newline='',encoding='utf-8')
    details_file = (batch/'partidas.jsonl').open('w',encoding='utf-8')
    fields = ['scenario','replication','engine_seed','rounds','progress','phases','seconds','simulation_seconds','initialization_seconds','reason','humans_aboard','questions','answers']
    writer = csv.DictWriter(csv_file,fieldnames=fields);writer.writeheader()
    paired = [{'count':0,'deltas':{key:RunningStats() for key in ('rounds','seconds','simulation_seconds','questions','answers')},
               'outcomes':Counter()} for _ in aggregates]

    def publish(status):
        report['status']=status
        report['scenarios']=[agg.summary() for agg in aggregates]
        report['comparisons']=[]
        for index, agg in enumerate(aggregates[1:],1):
            comparison=paired[index]
            report['comparisons'].append({'baseline':aggregates[0].name,'scenario':agg.name,'paired_games':comparison['count'],
                'deltas':{key:values.summary() for key,values in comparison['deltas'].items()},
                'outcome_changes':dict(comparison['outcomes'])})
        target=batch/'relatorio.json';temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
        if progress:progress(deepcopy({'status':status,'directory':str(batch),'completed':sum(a.numeric['rounds'].n for a in aggregates),
                                      'total':len(aggregates)*len(seeds),'scenarios':[{ 'name':a.name,'completed':a.numeric['rounds'].n} for a in aggregates]}))

    publish('running')
    try:
        registries = {directory:load_agents(directory) for directory in directories}
        # Cenários alternados por réplica para reduzir viés da ordem no tempo medido.
        for replication, seed in enumerate(seeds):
            replica_rows={};paired_indices=set()
            indices=list(range(len(aggregates)));random.Random(seed).shuffle(indices)
            for index in indices:
                if cancelled and cancelled():
                    publish('cancelled');return report
                case=plan['cases'][index];setup=replace(case['setup'],seed=seed)
                stream=random.Random(seed)
                agent_seeds={aid:stream.randrange(2**63) for aid in setup.assignment}
                start=time.perf_counter()
                session=setup.start(agent_seeds=agent_seeds,implementations=registries[setup.agent_directory])
                initialized=time.perf_counter()-start
                metrics=Metrics(session)
                while not session.game.finished:
                    if cancelled and cancelled():
                        publish('cancelled');return report  # Partida parcial não entra nos denominadores.
                    metrics.advance()
                record=metrics.record(replication,seed,time.perf_counter()-start,initialized)
                aggregates[index].add(record)
                details_file.write(json.dumps({'scenario':case['name'],**record},ensure_ascii=False)+'\n');details_file.flush()
                row={k:record[k] for k in fields if k in record}
                row.update(scenario=case['name'],reason=record['result']['reason'],
                           humans_aboard=len(record['result']['humans_aboard']),
                           questions=sum(record['questions'].values()),answers=sum(r['count'] for r in record['answers']))
                writer.writerow(row);csv_file.flush()
                replica_rows[index]={k:row[k] for k in ('rounds','seconds','simulation_seconds','questions','answers','reason')}
                if 0 in replica_rows:
                    for other_index,other in replica_rows.items():
                        if other_index==0 or other_index in paired_indices:continue
                        comparison=paired[other_index];baseline=replica_rows[0]
                        comparison['count'] += 1
                        for key,values in comparison['deltas'].items():values.add(other[key]-baseline[key])
                        comparison['outcomes'][baseline['reason']+' → '+other['reason']] += 1
                        paired_indices.add(other_index)
                if sum(a.numeric['rounds'].n for a in aggregates)%25==0:publish('running')
        publish('complete')
    except Exception as error:
        report['errors'].append({'type':type(error).__name__,'message':str(error)})
        publish('failed')
    finally:
        csv_file.close();details_file.close()
    return report




def compare_scenarios(first, first_name, second, second_name):
    """Comparação histórica descritiva; não assumir independência ou sementes pareadas."""
    def scenario(report,name):
        match=next((s for s in report['scenarios'] if s['name']==name),None)
        if match is None:raise ValueError('Cenário inexistente.')
        return match
    a,b=scenario(first,first_name),scenario(second,second_name)
    def diff(x,y):return None if x is None or y is None else y-x
    metrics=[{'metric':key,'a':a['metrics'][key]['mean'],'b':b['metrics'][key]['mean'],
              'delta':diff(a['metrics'][key]['mean'],b['metrics'][key]['mean'])} for key in a['metrics']]
    outcomes=[{'outcome':key,'a':a['outcomes'][key]['rate'],'b':b['outcomes'][key]['rate'],
               'delta':diff(a['outcomes'][key]['rate'],b['outcomes'][key]['rate'])} for key in a['outcomes']]
    qa={q['question']:q for q in a['questions']};qb={q['question']:q for q in b['questions']}
    questions=[{'question':q,'a':qa.get(q,{}).get('per_round',0) if a['completed'] else None,
                'b':qb.get(q,{}).get('per_round',0) if b['completed'] else None}
               for q in sorted(qa.keys()|qb.keys())]
    for q in questions:q['delta']=diff(q['a'],q['b'])
    def counts(rows):return {tuple(r[k] for k in ('question','response','implementation','nature','status')):r['count'] for r in rows}
    ca,cb=counts(a['answers']),counts(b['answers'])
    totals_a=Counter();totals_b=Counter()
    for key,n in ca.items():totals_a[key[0]]+=n
    for key,n in cb.items():totals_b[key[0]]+=n
    answers=[]
    for key in sorted(ca.keys()|cb.keys()):
        pa=ca.get(key,0)/totals_a[key[0]] if totals_a[key[0]] else None
        pb=cb.get(key,0)/totals_b[key[0]] if totals_b[key[0]] else None
        answers.append(dict(zip(('question','response','implementation','nature','status'),key),
                            a_count=ca.get(key,0),b_count=cb.get(key,0),a_rate=pa,b_rate=pb,delta=diff(pa,pb)))
    hashes_a=first.get('source_hashes',{});hashes_b=second.get('source_hashes',{})
    return {'a':{'experiment':first.get('name',Path(first['directory']).name),'scenario':first_name,'completed':a['completed']},
            'b':{'experiment':second.get('name',Path(second['directory']).name),'scenario':second_name,'completed':b['completed']},
            'metrics':metrics,'outcomes':outcomes,'questions':questions,'answers':answers,
            'setup_a':first['effective_setups'][first_name],'setup_b':second['effective_setups'][second_name],
            'changed_sources':[p for p in sorted(hashes_a.keys()|hashes_b.keys()) if hashes_a.get(p)!=hashes_b.get(p)],
            'note':'Diferenças descritivas (B − A); sem assumir independência entre lotes ou estimar intervalo de confiança.'}


class ExperimentJob:
    """Lotes segregados; limpeza da série atual preserva o arquivo para comparação."""
    def __init__(self,path):
        import threading
        self.path=Path(path);self.lock=threading.RLock();self.cancel_event=threading.Event()
        self.worker=None;self.started_at=0.;self.state=self.empty_state()
        try:
            if self.path.exists():self.snapshot()
        except (OSError,ValueError,KeyError,TypeError) as error:self.state.update(status='failed',error=str(error))

    @staticmethod
    def empty_state():return {'status':'idle','completed':0,'total':0,'report':None}

    def archived(self,plan):
        path=plan['output']/'.estatisticas-zeradas.json'
        if not path.exists():return set()
        data=json.loads(path.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('runs'),list) or any(type(x) is not str for x in data['runs']):
            raise ValueError('Registro de limpeza inválido.')
        return set(data['runs'])

    def reports(self,plan):
        return {p.parent.name:p for p in plan['output'].glob('*/relatorio.json')}

    def read_report(self,run):
        plan=load_plan(self.path);reports=self.reports(plan)
        if run not in reports:raise ValueError('Experimento inexistente.')
        return json.loads(reports[run].read_text()),reports[run]

    def snapshot(self,run=None):
        plan=load_plan(self.path)
        with self.lock:
            reports=self.reports(plan);archived=self.archived(plan)
            visible=[p for key,p in reports.items() if key not in archived and
                     (self.worker is None or p.stat().st_mtime>=self.started_at)]
            if (self.worker is None or not self.worker.is_alive()) and visible:
                latest=max(visible,key=lambda p:p.stat().st_mtime_ns);report=json.loads(latest.read_text())
                self.state.pop('error',None)
                self.state.update(report=report,directory=str(latest.parent),
                                  total=report['plan']['partidas_por_cenario']*len(report['plan']['cenarios']),
                                  status=report['status'] if report['status']!='running' else 'external',
                                  completed=sum(s['completed'] for s in report['scenarios']))
            state=deepcopy(self.state)
            selected=run or (Path(state['directory']).name if state.get('directory') else None)
            report=state.get('report')
            if selected:
                if selected not in reports:raise ValueError('Experimento inexistente.')
                report=json.loads(reports[selected].read_text())
            state['report']=report
            state['view']=None if not report else {'id':selected,'name':report.get('name',selected),
                    'status':report['status'],'completed':sum(s['completed'] for s in report['scenarios']),
                    'total':report['plan']['partidas_por_cenario']*len(report['plan']['cenarios'])}
            state['reports']=[]
            for key,p in sorted(reports.items(),reverse=True):
                r=json.loads(p.read_text())
                state['reports'].append({'id':key,'name':r.get('name',key),'status':r['status'],
                     'completed':sum(s['completed'] for s in r['scenarios']),
                     'scenarios':[s['name'] for s in r['scenarios']],'archived':key in archived})
        state['configuration']=plan['config']
        state['configured_scenarios']=[{'name':case['name'],'setup':case['effective']} for case in plan['cases']]
        return state

    def start(self,name=None):
        import threading
        if name is not None and (type(name) is not str or not name.strip() or len(name)>120):
            raise ValueError('Nome do experimento deve conter de 1 a 120 caracteres.')
        plan=load_plan(self.path)
        with self.lock:
            if self.worker and self.worker.is_alive():raise ValueError('Já existe um lote em execução.')
            self.started_at=time.time();self.cancel_event.clear()
            self.state={'status':'running','completed':0,'total':plan['config']['partidas_por_cenario']*len(plan['cases']),'report':None}
            def update(progress):
                with self.lock:self.state.update(progress)
            def execute():
                try:
                    report=run_plan(self.path,progress=update,cancelled=self.cancel_event.is_set,name=name.strip() if name else None)
                    with self.lock:self.state.update(status=report['status'],report=report,directory=report['directory'])
                except Exception as error:
                    with self.lock:self.state.update(status='failed',error=str(error))
            self.worker=threading.Thread(target=execute,daemon=True);self.worker.start()

    def cancel(self):self.cancel_event.set()

    def clear(self):
        plan=load_plan(self.path)
        with self.lock:
            if self.worker and self.worker.is_alive():raise ValueError('Aguarde o encerramento do lote para zerar as estatísticas.')
            reports=self.reports(plan)
            if any(json.loads(p.read_text())['status']=='running' for p in reports.values() if p.parent.name not in self.archived(plan)):
                raise ValueError('Existe um lote sem encerramento gravado; conclua-o antes de zerar.')
            plan['output'].mkdir(parents=True,exist_ok=True)
            data={'runs':sorted(self.archived(plan)|set(reports)),'cleared_at':datetime.now(timezone.utc).isoformat()}
            target=plan['output']/'.estatisticas-zeradas.json';temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(target)
            self.state=self.empty_state();self.worker=None;self.started_at=0.

    def compare(self,run_a,scenario_a,run_b,scenario_b):
        with self.lock:
            first,_=self.read_report(run_a);second,_=self.read_report(run_b)
            if first['status']=='running' or second['status']=='running':raise ValueError('Compare lotes encerrados.')
            return compare_scenarios(first,scenario_a,second,scenario_b)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',default=str(ROOT/'experimentos.json'))
    args=parser.parse_args()
    report=run_plan(args.plan,progress=lambda p:print(f"{p['completed']}/{p['total']} · {p['status']}",flush=True))
    print(report['directory'],flush=True)
    if report['status']=='failed':raise SystemExit(1)

