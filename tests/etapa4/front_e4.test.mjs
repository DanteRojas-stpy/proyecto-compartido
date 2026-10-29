import assert from 'node:assert/strict';
import { test } from 'node:test';
import { describirEstadoE4, formatearImporte, nombreArchivoHomologacion, resumirHomologacion } from '../../frontend/js/e4.js';

const fila = (extra = {}) => ({ finales_e3: 3, e4_estado: null, homologacion_id: null, estado_revision: null, e4_error: null, ...extra });

test('sin finales no se puede homologar y se explica por qué', () => {
  const e = describirEstadoE4(fila({ finales_e3: 0 }));
  assert.equal(e.puedeHomologar, false);
  assert.equal(e.badge.texto, 'SIN FINALES');
  assert.match(e.mensaje, /aceptadas como finales/);
});

test('sin estado todavía (null) se comporta como sin finales', () => {
  assert.equal(describirEstadoE4(null).puedeHomologar, false);
  assert.equal(describirEstadoE4(undefined).badge.texto, 'SIN FINALES');
});

test('con finales y sin homologar se puede homologar', () => {
  const e = describirEstadoE4(fila());
  assert.equal(e.puedeHomologar, true);
  assert.equal(e.etiqueta, 'Homologar');
  assert.equal(e.puedeVerResultado, false);
  assert.match(e.mensaje, /3 cotizaciones finales/);
  assert.match(describirEstadoE4(fila({ finales_e3: 1 })).mensaje, /1 cotización final para homologar/);
});

test('mientras trabaja, el botón queda bloqueado y la tarjeta se actualiza sola', () => {
  for (const estado of ['pendiente', 'en_curso']) {
    const e = describirEstadoE4(fila({ e4_estado: estado }));
    assert.equal(e.activo, true);
    assert.equal(e.puedeHomologar, false);
    assert.equal(e.badge.texto, 'EN CURSO');
  }
});

test('lista para el cuadro, con pendientes y con error', () => {
  const lista = describirEstadoE4(fila({ e4_estado: 'completado', homologacion_id: 'h1', estado_revision: 'listo_para_cuadro' }));
  assert.equal(lista.badge.texto, 'LISTA');
  assert.equal(lista.etiqueta, 'Volver a homologar');
  assert.equal(lista.puedeVerResultado, true);
  const pendientes = describirEstadoE4(fila({ e4_estado: 'completado', homologacion_id: 'h1', estado_revision: 'requiere_revision' }));
  assert.equal(pendientes.badge.texto, 'CON PENDIENTES');
  assert.equal(pendientes.puedeHomologar, true);
  const error = describirEstadoE4(fila({ e4_estado: 'error', e4_error: 'La homologación no terminó. Vuelve a solicitarla.' }));
  assert.equal(error.badge.texto, 'CON ERROR');
  assert.equal(error.etiqueta, 'Reintentar homologación');
  assert.equal(error.puedeHomologar, true);
});

test('un error no oculta el resultado anterior', () => {
  const e = describirEstadoE4(fila({ e4_estado: 'error', homologacion_id: 'h1' }));
  assert.equal(e.puedeVerResultado, true);
});

test('importes con moneda y valores vacíos', () => {
  assert.equal(formatearImporte(86848, 'USD'), 'USD 86,848.00');
  assert.equal(formatearImporte(null, 'USD'), '—');
  assert.equal(formatearImporte(undefined), '—');
  assert.equal(formatearImporte('no es numero', 'USD'), '—');
});

test('el nombre del archivo es seguro y lleva la fecha', () => {
  assert.equal(nombreArchivoHomologacion('MA-001', '2026-10-29T12:00:00+00:00'), 'homologacion-MA-001-2026-10-29.json');
  assert.equal(nombreArchivoHomologacion('Año / 2', '2026-10-29'), 'homologacion-Ano-2-2026-10-29.json');
  assert.equal(nombreArchivoHomologacion(null, null), 'homologacion-solicitud-sin-fecha.json');
});

test('el resumen se arma con el resultado real del constructor de E4', () => {
  const resultado = JSON.parse(process.env.HOMOLOGACION_JSON);
  const r = resumirHomologacion(resultado);
  assert.equal(r.estado, 'Requiere revisión');
  assert.equal(r.moneda, 'USD');
  assert.match(r.base, /provisional/);
  assert.deepEqual(r.postores.map((p) => p.nombre), ['Alfa SAC', 'Beta SA', 'Gamma Lift']);
  const alfa = r.postores[0];
  assert.equal(alfa.total, 86848);
  const gamma = r.postores[2];
  assert.equal(gamma.total, null);
  assert.deepEqual(gamma.porDocumento, [89184.4, 86963.81], 'dos equipos distintos se muestran por documento');
  assert.equal(r.partidas.length, 2);
  assert.ok(r.partidas[0].ofertas.every((o) => ['Cotizado', 'No cotizó'].includes(o.estado)));
  assert.ok(r.bloqueantes >= 1 && r.informativos >= 1);
  assert.equal(r.pendientes.length, r.bloqueantes + r.informativos);
  assert.ok(r.pendientes.some((p) => p.proveedor === 'Delta SRL'), 'se muestra el proveedor sin final por su nombre');
});

test('un resultado incompleto no rompe el resumen', () => {
  const r = resumirHomologacion({});
  assert.deepEqual([r.postores, r.partidas, r.pendientes], [[], [], []]);
  assert.equal(resumirHomologacion(null).estado, 'Requiere revisión');
});

import { describirEstadoE5, leerTipoCambio, nombreArchivoCuadro } from '../../frontend/js/e4.js';

const cuadro = (extra = {}) => ({ homologacion_id: 'h1', estado_revision: 'listo_para_cuadro', e5_estado: null, e5_revision: null, ...extra });

test('E5: sin homologación no se genera el cuadro', () => {
  for (const f of [null, {}, { homologacion_id: null }]) {
    const e = describirEstadoE5(f);
    assert.equal(e.puedeGenerar, false);
    assert.equal(e.badge.texto, 'SIN HOMOLOGAR');
  }
});

test('E5: con homologación se puede generar y se avisa si saldrá como borrador', () => {
  assert.equal(describirEstadoE5(cuadro()).puedeGenerar, true);
  assert.doesNotMatch(describirEstadoE5(cuadro()).mensaje, /borrador/);
  assert.match(describirEstadoE5(cuadro({ estado_revision: 'requiere_revision' })).mensaje, /saldrá como borrador/);
});

test('E5: mientras genera bloquea el botón y se actualiza sola', () => {
  for (const e5_estado of ['pendiente', 'en_curso']) {
    const e = describirEstadoE5(cuadro({ e5_estado }));
    assert.equal(e.activo, true);
    assert.equal(e.puedeGenerar, false);
    assert.equal(e.puedeDescargar, false);
  }
});

test('E5: borrador y validado se descargan solo si hay archivo; el error permite reintentar', () => {
  const validado = describirEstadoE5(cuadro({ e5_estado: 'validado', e5_revision: 2, cuadro_storage_file_id: 'f1' }));
  assert.equal(validado.badge.texto, 'VALIDADO');
  assert.equal(validado.puedeDescargar, true);
  assert.equal(describirEstadoE5(cuadro({ e5_estado: 'borrador', cuadro_storage_file_id: null })).puedeDescargar, false);
  assert.equal(describirEstadoE5(cuadro({ e5_estado: 'borrador', cuadro_storage_file_id: 'f1' })).badge.texto, 'BORRADOR');
  const error = describirEstadoE5(cuadro({ e5_estado: 'error', e5_error: 'Falló' }));
  assert.equal(error.puedeGenerar, true);
  assert.equal(error.mensaje, 'Falló');
});

test('E5: el tipo de cambio es opcional, pero completo y positivo si se indica', () => {
  assert.deepEqual(leerTipoCambio({ valor: '', fecha: '', fuente: '' }), { tipoCambio: null });
  assert.deepEqual(leerTipoCambio({ valor: '3,75', fecha: '2026-10-29', fuente: ' SBS ' }), { tipoCambio: { valor: 3.75, fecha: '2026-10-29', fuente: 'SBS' } });
  assert.match(leerTipoCambio({ valor: '0', fecha: '2026-10-29', fuente: 'SBS' }).error, /mayor que cero/);
  assert.match(leerTipoCambio({ valor: 'abc', fecha: '2026-10-29', fuente: 'SBS' }).error, /mayor que cero/);
  assert.match(leerTipoCambio({ valor: '3.75', fecha: '', fuente: 'SBS' }).error, /fecha/);
  assert.match(leerTipoCambio({ valor: '3.75', fecha: '2026-10-29', fuente: '' }).error, /fuente/);
});

test('E5: nombre del archivo descargado', () => {
  assert.equal(nombreArchivoCuadro('cuadro-MA-001-rev1.xlsx', 'MA-001', 1), 'cuadro-MA-001-rev1.xlsx');
  assert.equal(nombreArchivoCuadro(null, 'Ascensores ñandú', 3), 'cuadro-Ascensores-nandu-rev3.xlsx');
});
