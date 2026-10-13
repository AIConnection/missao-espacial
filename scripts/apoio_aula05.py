"""Preparação e apresentação da aula 05; não modifica o carregador ou os pesos."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone


def _pacote(repositorio):
    repo = Path(repositorio).resolve()
    pacote = repo / 'treinamento/piloto-v01/pacote'
    sys.path.insert(0, str(pacote / 'ferramentas'))
    return repo, pacote


def carregar_demo(repositorio, **opcoes_modelo):
    """Carrega pesos e casos do checkout, preservando todas as verificações originais."""
    repo, pacote = _pacote(repositorio)
    from inferir import PilotPredictor
    heads = repo / 'treinamento/piloto-v01/execucao-local-01/heads'
    casos_dir = repo / 'treinamento/piloto-v01/avaliacao-fora-dominio-01'
    protocolo = json.loads((casos_dir / 'protocolo.json').read_text())
    for nome in ('inputs.jsonl', 'supervisao.jsonl'):
        digest = hashlib.sha256((casos_dir / nome).read_bytes()).hexdigest()
        if digest != protocolo['data_sha256'][nome]:
            raise ValueError('Dados de avaliação alterados: ' + nome)
    casos = [json.loads(linha) for linha in (casos_dir / 'inputs.jsonl').read_text().splitlines()]
    alvos = [json.loads(linha) for linha in (casos_dir / 'supervisao.jsonl').read_text().splitlines()]
    if len(casos) != 30 or len(alvos) != 30:
        raise ValueError('São necessários os 30 casos completos')
    for i, (caso, alvo) in enumerate(zip(casos, alvos)):
        if set(caso) != {'premise', 'hypothesis'} or alvo['index'] != i:
            raise ValueError('Entrada e supervisão fora do contrato')
    modelo = PilotPredictor(pacote, heads, **opcoes_modelo)
    print('Commit utilizado:', subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip())
    print('Dispositivo:', modelo.backend.identity['device'])
    print('Prefixo fixo usado pelo encoder:\n' + modelo.prefix)
    return modelo, casos, alvos


def avaliar_demo(repositorio, resultados, destino='avaliacao-demonstracao'):
    """Avalia classes públicas sem inferir probabilidades a partir de rótulos."""
    classes = ['suporte', 'insuficiente', 'contradição']
    if not resultados or len({r['index'] for r in resultados}) != len(resultados):
        raise ValueError('Resultados vazios ou casos duplicados')
    matriz = [[0] * 3 for _ in classes]
    for r in resultados:
        if set(r['output']) != {'classification'}:
            raise ValueError('Saída fora do contrato')
        matriz[classes.index(r['expected'])][classes.index(r['output']['classification'])] += 1
    por_classe = {}
    for i, classe in enumerate(classes):
        tp = matriz[i][i]
        previstos = sum(linha[i] for linha in matriz)
        reais = sum(matriz[i])
        por_classe[classe] = {'precision': tp / max(previstos, 1), 'recall': tp / max(reais, 1),
                              'f1': 2 * tp / max(previstos + reais, 1), 'count': reais}
    repo = Path(repositorio)
    artefato = json.loads((repo / 'treinamento/piloto-v01/execucao-local-01/heads/artefato.json').read_text())
    relatorio = {'github_commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
                 'heads_sha256': artefato['heads'], 'indices': [r['index'] for r in resultados],
                 'accuracy': sum(matriz[i][i] for i in range(3)) / len(resultados),
                 'macro_f1': sum(v['f1'] for v in por_classe.values()) / 3,
                 'labels': classes, 'confusion': matriz, 'per_class': por_classe}
    print(f"Acurácia: {relatorio['accuracy']:.1%} | Macro F1: {relatorio['macro_f1']:.3f}")
    print('Matriz: linhas = esperado; colunas = previsto; ordem =', classes)
    for linha in matriz:
        print(linha)
    for classe, m in por_classe.items():
        print(f"{classe}: precisão={m['precision']:.3f}, recall={m['recall']:.3f}, F1={m['f1']:.3f}")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / ('resultado-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    arquivo.write_text(json.dumps({'report': relatorio, 'predictions': resultados}, ensure_ascii=False, indent=2))
    print('Avaliação salva:', arquivo.resolve())
    return relatorio


def mostrar_avaliacao(resultado):
    """Resumo dos mesmos resultados completos já produzidos por train()."""
    print('CLASSIFICAÇÃO — teste reservado')
    for nome, m in resultado['tasks']['nli']['evaluation']['test'].items():
        print(f"{nome}: acurácia={m['accuracy']:.1%}, macro F1={m['macro_f1']:.3f}, NLL={m['nll']:.3f}")
    m = resultado['tasks']['nli']['evaluation']['test']['calibrated_head']
    print('Matriz da cabeça calibrada; linhas = esperado, colunas = previsto:', m['labels'])
    for linha in m['confusion_matrix_true_rows_predicted_columns']:
        print(linha)
    for linha in m['per_class']:
        print(f"{linha['label']}: precisão={linha['precision']:.3f}, recall={linha['recall']:.3f}, F1={linha['f1']:.3f}")
    print('\nEVENTO — teste reservado')
    for nome in ('raw_head', 'calibrated_head', 'train_prior_baseline'):
        m = resultado['tasks']['forecast']['evaluation'][nome]['partitions']['test']
        print(f"{nome}: Brier={m['brier_delivery']:.5f}, perda binária={m['log_loss_delivery']:.5f}")


def exportar(pacote, trabalho):
    """Empacota código, dados, cabeças e relatório; exclui corpo e cache de features."""
    pacote, trabalho = Path(pacote), Path(trabalho)
    arquivo = trabalho / 'missao-espacial-piloto-exportacao.zip'
    with zipfile.ZipFile(arquivo, 'w', zipfile.ZIP_DEFLATED) as zip_out:
        for item in pacote.rglob('*'):
            if item.is_file() and '__pycache__' not in item.parts:
                zip_out.write(item, 'pacote/' + str(item.relative_to(pacote)))
        for item in (trabalho / 'heads').rglob('*'):
            if item.is_file():
                zip_out.write(item, 'heads/' + str(item.relative_to(trabalho / 'heads')))
        zip_out.write(trabalho / 'resultado.json', 'resultado.json')
    print('Treinamento exportado:', arquivo.resolve())
    return arquivo
