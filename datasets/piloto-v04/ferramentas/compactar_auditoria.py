"""Compacta logs mantendo os originais e comprova identidade do conteúdo."""
from pathlib import Path
import gzip,hashlib,json,shutil,argparse

def compact(folder):
    result=[]
    for name in ('mundos.jsonl','continuacoes.jsonl'):
        source=folder/'auditoria'/name;target=source.with_suffix(source.suffix+'.gz')
        if target.exists():raise ValueError('Do not overwrite an audit archive')
        with source.open('rb') as original,target.open('wb') as destination:
            with gzip.GzipFile(filename='',fileobj=destination,mode='wb',mtime=0) as zipped:shutil.copyfileobj(original,zipped)
        def digest(stream):
            h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
            return h.hexdigest()
        with source.open('rb') as a,gzip.open(target,'rb') as b:assert digest(a)==digest(b)
        result.append({'name':name,'original_bytes':source.stat().st_size,'compressed_bytes':target.stat().st_size,'same_content':True})
    (folder/'compactacao-validacao.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args();compact(a.folder)
