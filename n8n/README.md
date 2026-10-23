# n8n: flujos de orquestación

n8n coordina los pasos del proceso: envía solicitudes, revisa la bandeja de correo,
llama a la app y guarda el estado. **No ejecuta la lógica de negocio**: esa vive en `app/`.

## Qué va aquí

- `flujos/`: cada flujo exportado como archivo `.json`, con un nombre claro.
  Ejemplo: `flujos/seguimiento-correo.json`.
- Este README: qué hace cada flujo, cuándo se dispara y qué variables necesita.

## Reglas

1. **Nunca subas claves, contraseñas ni tokens.** Antes de exportar, revisa el
   `.json` y reemplaza los valores sensibles por nombres de variables de entorno.
2. Un cambio en un flujo entra por Pull Request, igual que el código.
3. Documenta cada flujo aquí: qué dispara, qué entra, qué sale.

## Flujos

| Archivo | Qué hace | Se dispara con | Estado |
|---|---|---|---|
| _por definir_ | | | |
