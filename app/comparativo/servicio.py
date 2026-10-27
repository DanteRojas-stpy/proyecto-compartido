"""Servicio local autenticado de llenado Excel. No consulta Nhost ni interpreta ofertas."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import re
import threading
import uuid

from .plantilla import DatosPendientes, generar


def servir(bind, port, token_file, salida, node, worker):
    secreto=Path(token_file).read_text(encoding='utf-8').strip()
    if len(secreto)<32:raise ValueError('Se requiere un token local de al menos 32 caracteres.')
    salida=Path(salida);salida.mkdir(parents=True,exist_ok=True)
    bloqueo=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):pass  # No registrar datos de las cotizaciones ni cabeceras.
        def auth(self):return hmac.compare_digest(self.headers.get('X-CostFlow-Token',''),secreto)
        def enviar(self, status, obj):
            b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            if not self.auth():self.enviar(401,{'error':'No autorizado'});return
            if self.path=='/health':self.enviar(200,{'estado':'disponible'});return
            match=re.fullmatch(r'/archivos/([a-f0-9-]{36})',self.path)
            if not match:self.enviar(404,{'error':'Ruta no disponible'});return
            carpeta=salida/match[1];archivos=[p for p in carpeta.glob('*.xlsx') if p.name!='plantilla.xlsx']
            if len(archivos)!=1:self.enviar(404,{'error':'Archivo no disponible'});return
            b=archivos[0].read_bytes();self.send_response(200)
            self.send_header('Content-Type','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition','attachment; filename="'+archivos[0].name+'"')
            self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_POST(self):
            if not self.auth():self.enviar(401,{'error':'No autorizado'});return
            if self.path!='/generar':self.enviar(404,{'error':'Ruta no disponible'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8*1024*1024:raise ValueError('Tamaño no admitido')
                entrada=json.loads(self.rfile.read(size));datos=entrada['datos']
                plantilla=base64.b64decode(entrada['plantilla_base64'],validate=True)
                if len(plantilla)>4*1024*1024:raise ValueError('Plantilla demasiado grande')
                revision=datos.get('revision',0)
                if isinstance(revision,bool) or not isinstance(revision,int) or not 0<=revision<=999:raise ValueError('Revisión inválida')
                job=str(uuid.uuid4());carpeta=salida/job;carpeta.mkdir()
                origen=carpeta/'plantilla.xlsx';origen.write_bytes(plantilla)
                solicitud=datos['homologaciones'][0]['solicitud_id']
                codigo=datos['homologaciones'][0].get('proyecto',{}).get('codigo') or 'SIN_CODIGO'
                codigo=re.sub(r'[^A-Za-z0-9_-]','_',str(codigo))[:24]
                fecha=datetime.now(timezone(timedelta(hours=-5))).strftime('%y%m%d')
                with bloqueo:
                    for previo in salida.glob('*/validacion.json'):
                        registro=json.loads(previo.read_text(encoding='utf-8'))
                        if registro.get('solicitud_id')==solicitud:revision=max(revision,registro['revision']+1)
                    archivo=carpeta/f'{fecha}_{codigo}_CC_ASCENSORES_Rev.{revision:02d}.xlsx'
                    informe=generar(datos,origen,archivo,node=node,worker=worker)
                    informe.update(job_id=job,revision=revision,solicitud_id=solicitud,ruta_descarga='/archivos/'+job)
                    (carpeta/'datos_validados.json').write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8')
                    (carpeta/'validacion.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2),encoding='utf-8')
                self.enviar(200,informe)
            except DatosPendientes as e:self.enviar(200,{'estado':'pendiente_validacion','motivo':str(e)})
            except (ValueError,KeyError,TypeError) as e:self.enviar(400,{'estado':'error_entrada','motivo':str(e)})
            except Exception as e:self.enviar(500,{'estado':'error_generacion','motivo':type(e).__name__})
    ThreadingHTTPServer((bind,port),Handler).serve_forever()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=18775)
    for arg in ['token-file','salida','node','worker']:p.add_argument('--'+arg,required=True)
    a=p.parse_args();servir(a.bind,a.port,a.token_file,a.salida,a.node,a.worker)
