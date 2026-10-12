"""Execução local das células Python em sequência, em diretório temporário."""
import json
import os
from pathlib import Path
import tempfile
import sys
from types import ModuleType

ROOT=Path(__file__).resolve().parents[1]
notebook=json.loads((ROOT/'notebooks/06-Engine_Missao_Espacial_2026-2.ipynb').read_text())
notebook_module=ModuleType('__local_mission_notebook__')
sys.modules[notebook_module.__name__]=notebook_module
namespace=notebook_module.__dict__
old_directory=Path.cwd()
old_sys_path=list(sys.path)
try:
    with tempfile.TemporaryDirectory() as temporary:
        os.chdir(temporary)
        sys.path.insert(0,temporary)
        for i,cell in enumerate(notebook['cells']):
            if cell['cell_type']=='code':
                source=''.join(cell['source'])
                exec(compile(source,f'cell-{i}','exec'),namespace)
                if 'agents = setup.start()' in source:
                    initial_state=namespace['game'].dumps()
        g=namespace['game']
        assert g.finished
        uninterrupted=namespace['Game'].loads(initial_state)
        actors=namespace['assign_agents'](uninterrupted,namespace['load_agents']('src/agent'))
        while not uninterrupted.finished:
            actors.run_round()
        assert uninterrupted.dumps()==g.dumps()
        assert namespace['checkpoint'].is_file()
        loaded=namespace['Game'].load(namespace['checkpoint'])
        assert loaded.dumps()==g.dumps()
        # Reexecutar preparação não apaga código personalizado nem reinicia a partida.
        agent_path=Path('src/agent/humano_alpha.py')
        customized=agent_path.read_text()+'\n# alteração do aluno preservada\n'
        agent_path.write_text(customized)
        saved_state=g.dumps()
        setup=next(''.join(c['source']) for c in notebook['cells']
                   if c['cell_type']=='code' and 'AGENT_SOURCES = ' in ''.join(c['source']))
        exec(compile(setup,'prepare-agents-again','exec'),namespace)
        assert agent_path.read_text()==customized
        assert namespace['game'].dumps()==saved_state
        assert set(namespace['agents'].assignment)==set(namespace['game'].ids)
        Path('src/agent').rename('src/agent-original')
        Path('src/agent').mkdir()
        Path('src/agent/custom.py').write_text('NATURE="HUMANO"\nfrom ._baseline import BaselineAgent\ndef create_agent(): return BaselineAgent()\n')
        exec(compile(setup,'prepare-custom-library','exec'),namespace)
        assert set(namespace['implementations'])=={'custom'}
        assert not list(Path('src/agent').glob('humano_*.py'))
        assert not Path('src/agent/humanoide.py').exists()
        assert namespace['game'].dumps()==saved_state
finally:
    os.chdir(old_directory)
    sys.path[:]=old_sys_path
    sys.modules.pop(notebook_module.__name__,None)
result={'passed':True,'agent_setup_preserves_existing_files':True,'no_sample_modules_added_to_custom_library':True,'code_cells':sum(c['cell_type']=='code' for c in notebook['cells']),
        'resume_matches_continuous_execution':True, 'scope':'local Python cell execution, central setup, random human active, checkpoint save/load; not executed in Google Colab'}
(ROOT/'evidencias/engine-v01/resultado-notebook.json').write_text(json.dumps(result,indent=2)+'\n')
print(result)
