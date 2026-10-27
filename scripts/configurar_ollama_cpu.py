"""Evita el fallo CUDA de Ollama en una exportación de n8n.

Conserva modelo, contexto, instrucciones, conexiones y credenciales.
No cambia el controlador de Windows ni otras aplicaciones.
"""

import argparse
import copy
import json
from pathlib import Path


def configurar_cpu(flujo):
    resultado = copy.deepcopy(flujo)
    nodos = [n for n in resultado['nodes']
             if n['type'] == '@n8n/n8n-nodes-langchain.lmChatOllama']
    if not nodos:
        raise ValueError('El flujo no contiene un modelo de chat Ollama.')
    for nodo in nodos:
        nodo['parameters'].setdefault('options', {})['numGpu'] = 0
    return resultado


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada', type=Path)
    parser.add_argument('salida', type=Path)
    args = parser.parse_args()
    original = json.loads(args.entrada.read_text(encoding='utf-8-sig'))
    resultado = ([configurar_cpu(f) for f in original] if isinstance(original, list)
                 else configurar_cpu(original))
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
