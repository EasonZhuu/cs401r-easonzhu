"""Execute the saved demo in a clean project-Python kernel; keep runtime files local."""
import json
import os
from pathlib import Path
import sys


def main():
    repo=Path(__file__).resolve().parents[1]
    runtime=repo/'.notebook-runtime'
    kernel=runtime/'kernels/lab3'
    kernel.mkdir(parents=True,exist_ok=True)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
        'display_name':'Python (Lab 3 project)','language':'python'}),encoding='utf-8')
    os.environ['JUPYTER_PATH']=str(runtime)
    os.environ['JUPYTER_RUNTIME_DIR']=str(runtime/'runtime')
    os.environ['IPYTHONDIR']=str(runtime/'ipython')
    from nbclient import NotebookClient
    import nbformat
    path=repo/'notebooks/lab3-demo.ipynb'
    notebook=nbformat.read(path,as_version=4)
    NotebookClient(notebook,timeout=300,kernel_name='lab3',resources={'metadata':{'path':str(repo)}}).execute()
    nbformat.validate(notebook)
    nbformat.write(notebook,path)
    print('PASS fresh kernel: all demo cells executed and saved with outputs')


if __name__=='__main__':
    main()
