COSTFLOW — DESARROLLO DEL MVP
Agente de IA para automatizar la gestión de cotizaciones

He incorporado este contexto como la definición actualizada del MVP de CostFlow. Esta versión delimita las responsabilidades del especialista y del agente de IA.

1. OBJETIVO DEL MVP

Automatizar la gestión de solicitudes de cotización, desde el envío de correos hasta la generación de un cuadro comparativo de propuestas homologadas, manteniendo la intervención del especialista para resolver consultas técnicas y tomar decisiones.

2. DISTRIBUCIÓN DE RESPONSABILIDADES

Actividad | Especialista | Agente IA
- Cargar metrados y plantillas | Responsable | Validación inicial
- Seleccionar proveedores | Responsable | Registra información
- Definir partidas y ruta crítica | Responsable | Prioriza seguimiento
- Enviar solicitudes | Autoriza | Ejecuta
- Seguimiento de correos | Supervisa | Automatiza
- Analizar respuestas y PDF | Revisa excepciones | Extrae información
- Identificar aclaraciones | Resuelve consultas | Detecta y notifica
- Recuperar cotizaciones finales | Interviene si es necesario | Realiza seguimiento
- Homologar cotizaciones | Valida criterios | Propone homologación
- Elaborar cuadro comparativo | Revisa resultado | Genera documento
- Evaluar y seleccionar proveedor | Decide | Facilita información

3. FLUJO AUTOMATIZADO PROPUESTO

1) ESPECIALISTA: carga metrados, proveedores, partidas, ruta crítica, vigencias y plantilla.
2) AGENTE COSTFLOW: envía solicitudes y ejecuta seguimiento automático por correo.
3) ANÁLISIS: examina correos y documentos recibidos para identificar respuestas, cotizaciones, archivos adjuntos y consultas pendientes.
4) DECISIÓN: ¿existen aclaraciones pendientes?
   - Sí: notifica al especialista para que resuelva las consultas.
   - No: continúa la revisión de la propuesta.
   Tras resolver las aclaraciones, el agente continúa hasta obtener la cotización final.
5) HOMOLOGACIÓN: contrasta el alcance de cada propuesta con el metrado referencial y registra diferencias.
6) CUADRO COMPARATIVO: completa la plantilla Excel y vincula cotizaciones finales de respaldo.
7) ESPECIALISTA: valida homologación, revisa el comparativo y toma la decisión final.

4. CONSIDERACIONES FUNCIONALES IMPORTANTES

- Ruta crítica: las partidas críticas tendrán reglas de seguimiento y notificación más exigentes.
- Vigencia de cotizaciones: el sistema debe alertar cuando una propuesta esté próxima a vencer.
- Cotización final: el agente debe diferenciar versiones preliminares, corregidas y finales para evitar comparar documentos desactualizados.
- Homologación: el agente no debe asumir equivalencias técnicas sin evidencia o aprobación del especialista.

5. ARQUITECTURA PRELIMINAR

- Excel: entrada de metrados y salida del comparativo.
- Gmail API: comunicación y seguimiento con proveedores.
- n8n: orquestación de flujos y ejecución de tareas.
- Supabase / PostgreSQL: persistencia, trazabilidad y estados.
- Supabase Storage: almacenamiento de cotizaciones y adjuntos.
- Modelo de IA: interpretación de correos y documentos, detección de consultas y apoyo a la homologación.

La distinción central: n8n orquesta el proceso; el modelo de IA interpreta información y propone acciones; PostgreSQL mantiene el estado y la trazabilidad del proceso.

Este será el contexto de referencia para trabajar en la definición del alcance, arquitectura, automatizaciones y desarrollo del MVP de CostFlow. No implica todavía que las tecnologías o funcionalidades estén implementadas.
