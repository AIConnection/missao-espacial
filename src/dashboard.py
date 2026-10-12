"""Dashboard administrativa local, independente do contrato dos agentes (stdlib)."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import threading

from carregar_agentes import assign_agents, load_agents
from missao_espacial import Game
from setup_jogo import GameSetup
from experimentos import ExperimentJob

ROOT = Path(__file__).resolve().parents[1]
PHASES = {'initiative':'Escolha das ações', 'renounce':'Consenso entre solicitantes',
          'authorize':'Autorização da votação', 'proposal':'Votação da proposta',
          'answers':'Respostas e revelação', 'election':'Eleição obrigatória',
          'route':'Rota e movimento', 'exit':'Saídas e bloqueios', 'finished':'Encerrado'}


def observe(session, participant=None, *, before=None, limit=50):
    """Projeção do professor. Não chama agentes nem altera estado/RNG.

    Lê apenas fatias dos históricos; não copia o checkpoint inteiro a cada consulta.
    Acesso administrativo deliberado, nunca entregue às políticas.
    """
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('Limite deve estar entre 1 e 200.')
    game = session.game
    state = game._state
    if participant is None:
        participant = game.ids[0]
    if participant not in state['agents']:
        raise ValueError('Participante inexistente.')
    events = state['public']
    end = len(events) if before is None else before
    if type(end) is not int or not 0 <= end <= len(events):
        raise ValueError('Cursor de eventos inválido.')
    start = max(0, end-limit)
    catalog = {q['id']:q['text'] for q in game.catalog['questions']}
    roster = []
    for aid, agent in state['agents'].items():
        roster.append({'id':aid, 'nature':agent['nature'], 'implementation':session.assignment[aid],
                       'active':agent['active'], 'controller':state['controller']==aid,
                       'penalties':agent['penalty_rounds'], 'exit_locked':agent['exit_locked'],
                       'domains':[d for d, owner in state['owners'].items() if owner==aid],
                       'counts':{k:len(agent[k]) for k in ('facts','received','sent','revelations')}})
    agent = state['agents'][participant]
    facts = []
    for key, fact in agent['facts'].items():
        qid, parameters = json.loads(key)
        facts.append({'question_id':qid, 'parameters':parameters, **deepcopy(fact),
                      'current':fact['revision'] is None or fact['revision']==state['revision']})
    detail = {'id':participant, 'facts':facts, 'beliefs':deepcopy(agent['beliefs']),
              'profile':deepcopy(agent['profile']),
              'messages':{k:deepcopy(agent[k][-limit:]) for k in ('received','sent','revelations')},
              'sensors':{}}
    if agent['active'] and state['owners']['PAINEL']==participant:
        detail['sensors']['oxigenio_rodadas'] = str(game.oxygen)
    if agent['active'] and state['owners']['DISTÂNCIA']==participant:
        detail['sensors']['rodadas_ate_colonia'] = 2*state['N']-state['progress']
    # Indicadores declarados pela política humana; ausentes em outras implementações.
    detail['policy_indicators'] = deepcopy({k:agent['policy_state'][k]
        for k in ('humans','trust') if k in agent['policy_state']})
    return {'round':game.round, 'phase':game.phase, 'phase_label':PHASES.get(game.phase,game.phase),
            'finished':game.finished, 'result':game.result, 'controller':state['controller'],
            'progress':state['progress'], 'destination':2*state['N'],
            'oxygen':str(game.oxygen), 'oxygen_decimal':float(game.oxygen),
            'initial_rounds':state['N'], 'roster':deepcopy(roster), 'detail':detail,
            'pending':deepcopy(state['pending']), 'catalog':catalog,
            'events':deepcopy(events[start:end]), 'event_start':start, 'event_end':end,
            'event_total':len(events)}


class Dashboard:
    def __init__(self, setup_path=ROOT/'setup.json'):
        self.setup_path = Path(setup_path).resolve()
        self.setup = GameSetup.load(self.setup_path)
        self.session = self.setup.start()
        self.lock = threading.RLock()
        self.experiments = ExperimentJob(self.setup_path.parent/'experimentos.json')

    def command(self, action):
        with self.lock:
            if action == 'phase':
                self.session.advance()
            elif action == 'round':
                self.session.run_round()
            elif action == 'save':
                self.session.save(self.setup.checkpoint)
            elif action == 'load':
                setup = GameSetup.load(self.setup_path)
                session = assign_agents(Game.load(setup.checkpoint), load_agents(setup.agent_directory))
                self.setup, self.session = setup, session
            elif action == 'new':
                setup = GameSetup.load(self.setup_path)
                session = setup.start()
                self.setup, self.session = setup, session
            else:
                raise ValueError('Comando desconhecido.')

    def observe(self, **options):
        with self.lock:
            return observe(self.session, **options)


def make_server(dashboard, port=8765):
    from urllib.parse import urlsplit, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, content, content_type='application/json; charset=utf-8'):
            data = content if isinstance(content, bytes) else json.dumps(content, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/':
                self.reply(200, Path(__file__).with_name('dashboard.html').read_bytes(), 'text/html; charset=utf-8')
                return
            if url.path == '/api/experiments':
                try:
                    self.reply(200,dashboard.experiments.snapshot(parse_qs(url.query).get('run',[None])[0]))
                except (ValueError,OSError,KeyError,TypeError) as error:
                    self.reply(400,{'error':str(error)})
                return
            if url.path == '/api/experiment-compare':
                try:
                    query=parse_qs(url.query)
                    self.reply(200,dashboard.experiments.compare(*(query[key][0] for key in ('run_a','scenario_a','run_b','scenario_b'))))
                except (ValueError,OSError,KeyError,TypeError) as error:self.reply(400,{'error':str(error)})
                return
            if url.path in ('/api/experiment-report','/api/experiment-csv'):
                with dashboard.experiments.lock:
                    directory=dashboard.experiments.state.get('directory')
                if not directory and not parse_qs(url.query).get('run'):
                    self.reply(404,{'error':'Nenhum lote disponível.'});return
                filename='relatorio.json' if url.path.endswith('report') else 'partidas.csv'
                selected=parse_qs(url.query).get('run',[None])[0]
                if selected:
                    try:
                        _,report_path=dashboard.experiments.read_report(selected);directory=str(report_path.parent)
                    except (ValueError,OSError) as error:
                        self.reply(404,{'error':str(error)});return
                path=Path(directory)/filename
                if not path.exists():
                    self.reply(404,{'error':'Arquivo ainda não disponível.'});return
                import shutil
                with path.open('rb') as file:
                    self.send_response(200)
                    self.send_header('Content-Type','application/json' if filename.endswith('json') else 'text/csv; charset=utf-8')
                    self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
                    self.end_headers()
                    shutil.copyfileobj(file,self.wfile)
                return
            if url.path != '/api/state':
                self.reply(404, {'error':'Recurso inexistente.'})
                return
            try:
                query = parse_qs(url.query)
                options = {'participant':query.get('agent',[None])[0]}
                if 'before' in query:
                    options['before'] = int(query['before'][0])
                self.reply(200, dashboard.observe(**options))
            except ValueError as error:
                self.reply(400, {'error':str(error)})

        def do_POST(self):
            if self.path not in ('/api/command','/api/experiments'):
                self.reply(404, {'error':'Recurso inexistente.'})
                return
            # Somente requisições da própria página local podem operar a sessão.
            if self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host")}'):
                self.reply(403, {'error':'Origem inválida.'})
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 1024:
                    raise ValueError('Comando inválido.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict) or 'action' not in body or set(body)-{'action','name'} or ('name' in body and (self.path!='/api/experiments' or body['action']!='start')):
                    raise ValueError('Informe apenas action.')
                if self.path=='/api/experiments':
                    if body['action']=='start':dashboard.experiments.start(body.get('name'))
                    elif body['action']=='cancel':dashboard.experiments.cancel()
                    elif body['action']=='clear':dashboard.experiments.clear()
                    else:raise ValueError('Comando de experimento desconhecido.')
                else:
                    dashboard.command(body['action'])
                self.reply(200, {'ok':True})
            except Exception as error:
                self.reply(400, {'error':str(error)})

    return ThreadingHTTPServer(('127.0.0.1',port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', default=str(ROOT/'setup.json'))
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(Dashboard(args.setup), args.port)
    print(f'Dashboard: http://127.0.0.1:{server.server_port} — Ctrl+C para encerrar', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
