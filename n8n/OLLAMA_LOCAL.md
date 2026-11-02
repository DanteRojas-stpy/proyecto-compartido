# Ollama local: conexión y fallo CUDA

Con n8n en Docker y Ollama en Windows, la dirección accesible desde n8n es
`http://host.docker.internal:11434`. El modelo instalado en este equipo es
`qwen3:8b`.

## Corrección aplicada al flujo de Juan

En **Modelo Ollama (local)**, la opción **Number of GPUs** se dejó en **0**
(`options.numGpu: 0`). n8n la entrega a Ollama como `num_gpu: 0` y la inferencia
se realiza en el procesador. El resto del nodo, sus credenciales y las conexiones
del flujo se conservan.

El registro de Ollama mostraba `CUDA error: device kernel image is invalid`
seguido de la terminación de `llama-server` con `0xc0000409`. La conexión a
Ollama respondía; el fallo ocurría al cargar el modelo en la GPU. Una prueba de
inferencia con `num_gpu: 0` devolvió una respuesta correcta.

El equipo tenía el controlador NVIDIA 546.18. La documentación de Ollama indica
550 o posterior para la RTX 4060. Esta corrección evita la GPU; no instala ni
cambia controladores. El procesamiento por CPU puede tardar más.

Para aplicar el mismo ajuste a una exportación de otro flujo:

```powershell
.venv\Scripts\python.exe scripts\configurar_ollama_cpu.py original.json corregido.json
```

Importar el resultado en el mismo flujo, después de guardar una copia previa.
No confundir este ajuste con una nueva credencial: no es necesario introducir
una clave para el Ollama local que está funcionando en este equipo.

Referencias oficiales:

- https://docs.ollama.com/gpu
- https://docs.ollama.com/troubleshooting
