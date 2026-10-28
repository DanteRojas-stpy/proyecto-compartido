import { timingSafeEqual } from 'node:crypto'
import type { Request, Response } from 'express'

const OPERACIONES = new Set([
  'configuracion',
  'eventos',
  'preparar_correo',
  'version',
  'registrar_documentos',
  'iniciar_lectura',
  'guardar_fuentes',
  'renovar_lease',
  'guardar_resultado',
  'fallo',
  'recuperar',
  'notificar',
  'decision',
  'documento_accesible',
])

function secretoValido(recibido: string, esperado: string): boolean {
  const a = Buffer.from(recibido)
  const b = Buffer.from(esperado)
  return a.length === b.length && timingSafeEqual(a, b)
}

function literal(valor: string): string {
  return `'${valor.replaceAll("'", "''")}'`
}

function baseHasura(): string {
  // La API pública de GraphQL (/v1) no publica la API administrativa (/v2/query).
  const configurada = process.env.NHOST_HASURA_URL ?? process.env.NHOST_GRAPHQL_URL
  if (!configurada) throw new Error('La URL de GraphQL/Hasura no está disponible en la función.')
  const url = new URL(configurada)
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('La dirección de Hasura no es válida.')
  }
  if (/\.graphql\.[a-z0-9-]+\.nhost\.run$/.test(url.hostname)) {
    url.hostname = url.hostname.replace('.graphql.', '.hasura.')
    url.pathname = '/'
  } else {
    url.pathname = url.pathname.replace(/\/(?:console|v1\/(?:graphql|metadata)|v2\/query)\/?$/, '')
    if (url.pathname !== '' && url.pathname !== '/') throw new Error('Configura NHOST_HASURA_URL con la dirección administrativa de Hasura.')
  }
  return url.origin
}

function respuestaRunSql(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object') throw new Error('Hasura no devolvió JSON.')
  const result = (payload as { result?: unknown }).result
  if (!Array.isArray(result) || result.length < 2 || !Array.isArray(result[1])) {
    throw new Error('Hasura no devolvió la respuesta de e3_operar.')
  }
  const value = result[1][0]
  if (typeof value !== 'string') throw new Error('La respuesta de e3_operar no es JSON.')
  return JSON.parse(value)
}

// Devuelve el id del usuario de Nhost a partir de su token de acceso, o null si no es válido.
async function usuarioVerificado(req: Request): Promise<string | null> {
  const cabecera = String(req.header('authorization') ?? '')
  const token = cabecera.startsWith('Bearer ') ? cabecera.slice(7).trim() : ''
  if (!token) return null
  const authBase = process.env.NHOST_AUTH_URL ?? `${baseHasura().replace('.hasura.', '.auth.')}/v1`
  const respuesta = await fetch(`${authBase}/user`, { headers: { Authorization: `Bearer ${token}` } })
  if (!respuesta.ok) return null
  const usuario = (await respuesta.json()) as { id?: unknown }
  return typeof usuario.id === 'string' ? usuario.id : null
}

export default async function handler(req: Request, res: Response) {
  res.setHeader('Cache-Control', 'no-store')
  if (req.method !== 'POST') return res.status(405).json({ error: 'Utiliza POST.' })

  const operacion = typeof req.body?.operacion === 'string' ? req.body.operacion : ''
  let datos = req.body?.datos

  if (operacion === 'decision') {
    // El especialista llama desde el navegador con su propio token. La identidad sale de Nhost Auth,
    // nunca de un campo que envía el cliente.
    const usuario = await usuarioVerificado(req)
    if (!usuario) return res.status(401).json({ error: 'Inicia sesión para registrar la decisión.' })
    if (datos && typeof datos === 'object' && !Array.isArray(datos)) {
      datos = { ...datos, usuario_id_verificado: usuario }
    }
  } else {
    const esperado = process.env.E3_INTERNAL_KEY ?? ''
    const recibido = String(req.header('x-costflow-internal-key') ?? '')
    if (!esperado || !secretoValido(recibido, esperado)) {
      return res.status(401).json({ error: 'Acceso interno no válido.' })
    }
  }

  if (!OPERACIONES.has(operacion) || !datos || typeof datos !== 'object' || Array.isArray(datos)) {
    return res.status(400).json({ error: 'Operación o datos inválidos.' })
  }

  const admin = process.env.NHOST_ADMIN_SECRET ?? process.env.HASURA_GRAPHQL_ADMIN_SECRET ?? ''
  if (!admin) return res.status(503).json({ error: 'Nhost no proporcionó su credencial administrativa.' })

  try {
    const json = JSON.stringify(datos)
    if (Buffer.byteLength(json, 'utf8') > 12 * 1024 * 1024) {
      return res.status(413).json({ error: 'La operación supera el tamaño permitido.' })
    }
    const sql = `SELECT public.e3_operar(${literal(operacion)},${literal(json)}::jsonb)::text AS respuesta;`
    const upstream = await fetch(`${baseHasura()}/v2/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-hasura-admin-secret': admin,
      },
      body: JSON.stringify({
        type: 'run_sql',
        args: {
          source: 'default',
          sql,
          cascade: false,
          read_only: false,
          check_metadata_consistency: false,
        },
      }),
      signal: AbortSignal.timeout(90000),
    })
    const payload = await upstream.json().catch(() => null)
    if (!upstream.ok) {
      console.error('e3_operar fue rechazado por Hasura', upstream.status)
      return res.status(502).json({ error: 'Nhost no pudo completar la operación de E3.' })
    }
    return res.status(200).json({ respuesta: respuestaRunSql(payload) })
  } catch {
    console.error('Fallo interno en e3-operar; revisa la configuración y disponibilidad de Hasura.')
    return res.status(500).json({ error: 'No fue posible completar la operación de E3.' })
  }
}

export { OPERACIONES, baseHasura, literal, respuestaRunSql, secretoValido }
