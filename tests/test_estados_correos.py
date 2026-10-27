from pathlib import Path


RAIZ = Path(__file__).parents[1]


def test_migracion_define_tres_estados_y_reserva_el_final_al_usuario():
    sql = (RAIZ / "db/migraciones/010_estados_por_correo.sql").read_text(encoding="utf-8")
    estados = (
        "respuesta_sin_nueva_cotizacion_ni_ficha_tecnica",
        "cotizacion_o_ficha_tecnica_recibida",
        "cotizacion_o_ficha_tecnica_aceptada_final",
    )
    for estado in estados:
        assert estado in sql
    assert "Solo el especialista puede aceptar" in sql
    assert "respuesta recibida fuera del plazo" in sql
    assert "historial_estados_correo" in sql
    assert "estado_asignado_por" in sql
    assert "old.origen_estado is distinct from new.origen_estado" in sql
    assert "old.estado_asignado_por is distinct from new.estado_asignado_por" in sql
    assert "documentos de proveedor deben indicar el correo de origen" in sql
    assert "recuperada por E3" in sql


def test_frontend_muestra_correos_y_guarda_su_estado_individual():
    app = (RAIZ / "frontend/js/app.js").read_text(encoding="utf-8")
    assert "correos_proveedor(" in app
    assert "update_correos_proveedor_by_pk" in app
    assert "Correos del proveedor" in app
    assert "Guardar estado" in app
    assert "Guardar corrección" not in app


def test_permisos_solo_dejan_al_usuario_actualizar_el_estado_del_correo():
    configuracion = (RAIZ / "scripts/configurar_nhost.py").read_text(encoding="utf-8")
    assert '"historial_estados_correo"' in configuracion
    assert '"columns": ["estado_correo"]' in configuracion
    assert '"correo_id"' in configuracion
    assert '"correo_origen"' in configuracion
    assert '"documentos_recuperados"' in configuracion
