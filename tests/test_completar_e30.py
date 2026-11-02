import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('completar_e30', ROOT / 'scripts/completar_e30.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


def detector_corto():
    flujo = modulo.generar()
    flujo['nodes'] = [n for n in flujo['nodes'] if n['name'] not in {
        x['name'] for x in flujo['nodes'][9:19]
    }]
    flujo['nodes'].append(modulo.nodo('Buscar correos existentes en Gmail', 'gmail', 2.1, [0, 0], {
        'operation': 'getAll', 'filters': {'q': 'newer_than:7d'},
    }))
    for n in flujo['nodes']:
        if n['type'] == 'n8n-nodes-base.gmail':
            n['credentials'] = {'gmailOAuth2': {'id': 'cred-prueba', 'name': 'Gmail'}}
        if n['name'] == 'Buscar envíos al proveedor':
            n['credentials'] = {'httpHeaderAuth': {'id': 'nhost-prueba', 'name': 'Nhost'}}
    flujo['connections'] = {k: v for k, v in flujo['connections'].items()
                            if k in {n['name'] for n in flujo['nodes']}}
    return flujo


def test_completar_sin_perder_credenciales_ni_repetir_nodos():
    original = detector_corto()
    copia = copy.deepcopy(original)
    flujo = modulo.completar(original)
    assert original == copia
    assert modulo.completar(flujo) == flujo
    nodos = {n['name']: n for n in flujo['nodes']}
    assert len(nodos) == len(flujo['nodes'])
    buscar = nodos['Buscar correos existentes en Gmail']['parameters']
    assert buscar['returnAll'] is True
    assert 'newer_than' not in buscar['filters']['q']
    assert buscar['filters']['readStatus'] == 'both'
    assert nodos['Descargar adjuntos de la respuesta']['credentials']['gmailOAuth2']['id'] == 'cred-prueba'
    assert nodos['Guardar PDF en Nhost Storage']['credentials']['httpHeaderAuth']['id'] == 'nhost-prueba'
    assert not any(n['type'] == 'n8n-nodes-base.executeWorkflow' for n in flujo['nodes'])
    assert nodos['Guardar PDF en Nhost Storage']['parameters']['bodyParameters']['parameters'][0]['value'] == 'cotizaciones'
    comprobar = nodos['Comprobar PDF en Nhost Storage']['parameters']
    assert comprobar['sendQuery'] is True
    assert 'Date.now()' in comprobar['queryParameters']['parameters'][0]['value']


def test_lee_tres_correos_y_conserva_cuatro_pdf_y_su_proveedor():
    programa = r'''const {prepararPdfs}=require('./app/recepcion/adjuntos.js');
const codigo=JSON.parse(require('fs').readFileSync(0,'utf8'));
(async()=>{
  const detecciones=[0,1,2].map(i=>({estado_deteccion:'detectado',gmail_message_id:'m'+i,
    gmail_thread_id:'h'+i,solicitud_id:'solicitud',proveedor_id:'proveedor'+i}));
  const items=detecciones.map((d,i)=>({json:{id:d.gmail_message_id,threadId:d.gmail_thread_id,
    text:'Respuesta '+i},binary:Object.fromEntries(Array.from({length:i===0?2:1},(_,j)=>
      ['adjunto_'+j,{fileName:'ficha'+j+'.pdf',mimeType:'application/pdf',data:'binario'}]))}));
  const leidos=new Function('$input','$',codigo)({all:()=>items},()=>({itemMatching:i=>({json:detecciones[i]})}));
  const pdf=await prepararPdfs(leidos,leidos.map(x=>x.json.lectura_correo),async()=>Buffer.from('%PDF-1.4\nprueba'));
  console.log(JSON.stringify({correos:leidos.length,pdf:pdf.map(x=>({proveedor:x.json.proveedor_id,
    texto:x.json.cuerpo_texto,estado:x.json.estado_lectura_correo}))}));
})();'''
    r = subprocess.run(['node', '-e', programa], cwd=ROOT, input=json.dumps(modulo.LECTURA),
                       capture_output=True, text=True, check=True)
    resultado = json.loads(r.stdout)
    assert resultado['correos'] == 3
    assert len(resultado['pdf']) == 4
    assert [x['proveedor'] for x in resultado['pdf']] == ['proveedor0', 'proveedor0', 'proveedor1', 'proveedor2']
    assert all(x['estado'] == 'leido' and x['texto'].startswith('Respuesta') for x in resultado['pdf'])
