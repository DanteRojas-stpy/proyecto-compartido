# E3.0: leer correos de proveedores y recibir PDF

Plantilla: `flujos/e3-0-detectar-respuestas-proveedores.json`.

En n8n local se completó el flujo existente «CostFlow - E3.0 Detectar respuestas
de proveedores», conservando sus conexiones a Gmail y Nhost. La plantilla del
repositorio no contiene credenciales, mensajes ni cotizaciones reales.

1. Ejecutar **Revisar correos existentes**. Se incluyen mensajes leídos y no
   leídos; se excluyen enviados, borradores, spam y papelera. No se limita la
   búsqueda a siete días ni a los primeros mensajes.
2. Se verifica el remitente contra los envíos registrados en Nhost y se comprueba
   que la conversación corresponda al mensaje enviado. No basta el asunto.
3. **Leer contenido del correo** muestra un elemento por respuesta, con
   `lectura_correo.cuerpo_texto`, `cuerpo_html`, proveedor y solicitud. El resumen
   de Gmail se conserva aparte; no sustituye al cuerpo completo.
4. Se descargan todos los PDF adjuntos y se verifica su cabecera. Los válidos se
   guardan en el bucket **cotizaciones**. Un archivo ya guardado se reutiliza.
5. Las salidas **PDF guardado y vinculado** y **PDF ya guardado anteriormente**
   mantienen los identificadores y datos necesarios para E3.1. E3.0 termina
   aquí: no ejecuta la interpretación de PDF con IA de E3.2 ni envía mensajes.

Tres correos pueden producir cuatro archivos: un proveedor puede adjuntar dos
PDF. Cada archivo conserva el correo, proveedor y solicitud de origen.

Para completar otra exportación del mismo flujo, sin reemplazar sus credenciales:

```powershell
.venv\Scripts\python.exe scripts\completar_e30.py exportacion.json completado.json
```

Para generar la plantilla sin datos privados:

```powershell
.venv\Scripts\python.exe -c "import sys,json; from pathlib import Path; sys.path.insert(0,'scripts'); from completar_e30 import generar_e30; Path('n8n/flujos/e3-0-detectar-respuestas-proveedores.json').write_text(json.dumps(generar_e30(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')"
```

Comprobación local: tres respuestas identificadas, cuerpos completos descargados
y cuatro PDF guardados. La prueba de repetición verifica que no se vuelvan a
subir. Las pruebas automáticas usan correos y PDF ficticios.
