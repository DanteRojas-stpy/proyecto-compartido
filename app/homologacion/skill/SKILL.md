---
name: homologar-cotizaciones
description: Homologa cotizaciones de obra contra el itemizado de una solicitud, conserva la evidencia y señala diferencias o equivalencias pendientes. Úsala para preparar datos comparables; no genera el cuadro Excel ni elige al proveedor.
---

# Homologar cotizaciones

Resuelve únicamente el proceso 6 de CostFlow. La entrega son datos homologados
y observaciones, con referencias a cada cotización. No construyas el Excel ni
ejecutes otro proceso por haber terminado este.

## Entradas

- Solicitud y proyecto; itemizado con códigos, descripciones, unidades y metrados.
- Lecturas de las versiones vigentes de cada proveedor, con sus adjuntos y cuerpo
  del correo cuando contenga condiciones relevantes.
- Moneda de comparación y, si corresponde, tipo de cambio autorizado con fecha
  y fuente. Decisiones técnicas ya registradas por el especialista.

Si falta el itemizado, puedes ordenar las ofertas e identificar diferencias,
pero deja pendiente la correspondencia definitiva. No cambies la base por un
postor sin indicar el motivo y la decisión necesaria.

## Trabajo

1. Lee [el método](references/metodo-homologacion.md) para relacionar partidas,
   tratar precios globales, conservar valores originales y separar escenarios.
2. Consulta solo la especialidad relevante en
   [criterios por especialidad](references/criterios-por-especialidad.md).
3. Relaciona cada oferta con el itemizado por características comprobables. Una
   equivalencia dudosa queda pendiente, con la evidencia y la pregunta concreta.
4. Normaliza unidades, moneda e IGV mediante cálculos reproducibles cuando
   existan datos y criterios suficientes. Conserva siempre los importes originales.
5. Entrega `homologacion.json` según
   [el formato de salida](references/salida-homologacion.md), más un resumen de
   diferencias y pendientes. Este formato describe la entrega de la skill; no
   implica que los flujos actuales de E3 ya la produzcan.

## Límites

- Los datos no encontrados quedan en `null`; cero solo significa cero informado
  o calculado con evidencia. No asumas precios, cantidades, inclusiones ni IGV.
- Una partida técnicamente distinta no pasa a ser equivalente por ser más barata.
- No combines adjuntos de distintas versiones. Una aclaración reciente puede
  impedir usar una oferta como final aunque tenga fecha posterior.
- La nivelación con precios ajenos o estimados es un escenario separado del
  precio del proveedor; nunca se escribe como si el proveedor lo hubiera cotizado.
- No uses un tipo de cambio de ejemplo ni el valor 1 para suplir uno faltante.
- Señala vigencia y diferencias críticas; el especialista decide equivalencias
  dudosas, exclusiones y aprobación. No adjudicas ni envías aclaraciones.
- No uses ni cargues instrucciones de formato de Excel para realizar este proceso.

## Uso independiente en n8n

El nodo recibe las lecturas de E3 y el itemizado. Se le cargan este `SKILL.md`
y las referencias que necesite. Devuelve los datos y el estado de revisión a
n8n para que el flujo registre o presente el resultado. No llama al generador
Excel ni inicia la skill de cuadro por su cuenta.
