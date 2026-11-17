"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError, api, query,
  type Curso, type Docente, type EstudianteDetalle, type EstudianteItem,
  type Momento, type NotificacionItem, type Prioridad,
} from "@/lib/api";

const MOMENTOS: { valor: Momento; etiqueta: string; pista: string }[] = [
  { valor: "T0_inicio", etiqueta: "Inicio de semestre", pista: "Solo historial académico" },
  { valor: "T1_corte1", etiqueta: "Después del corte 1", pista: "Primeras notas · mejor momento para actuar" },
  { valor: "T2_corte2", etiqueta: "Después del corte 2", pista: "Aún queda el 40% de la nota" },
];

const ETIQUETA_PRIORIDAD: Record<Prioridad, string> = {
  Alta: "Atención urgente",
  Media: "Estar atento",
  Baja: "Va bien",
};

export default function DashboardClient({ docente }: { docente: Docente }) {
  const router = useRouter();
  const [momento, setMomento] = useState<Momento>("T1_corte1");
  const [asignatura, setAsignatura] = useState("");
  const [curso, setCurso] = useState("");
  const [prioridad, setPrioridad] = useState<Prioridad | "">("");
  const [q, setQ] = useState("");
  const [soloAlertas, setSoloAlertas] = useState(false);
  const [estudiantes, setEstudiantes] = useState<EstudianteItem[]>([]);
  const [cursos, setCursos] = useState<Curso[]>([]);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<EstudianteDetalle | null>(null);
  const [notificaciones, setNotificaciones] = useState<NotificacionItem[]>([]);
  const [resumenNotif, setResumenNotif] = useState({ activas: 0, no_leidas: 0, pendientes: 0 });
  const [panelNotif, setPanelNotif] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [procesando, setProcesando] = useState("");
  const [error, setError] = useState("");

  const manejarError = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) {
      router.replace("/login");
      router.refresh();
      return;
    }
    setError(err instanceof Error ? err.message : "Ocurrió un error");
  }, [router]);

  const cargarNotificaciones = useCallback(async () => {
    try {
      const [lista, resumen] = await Promise.all([
        api<NotificacionItem[]>("/api/notificaciones?limite=60"),
        api<{ activas: number; no_leidas: number; pendientes: number }>("/api/notificaciones/resumen"),
      ]);
      setNotificaciones(lista);
      setResumenNotif(resumen);
    } catch (err) {
      manejarError(err);
    }
  }, [manejarError]);

  useEffect(() => {
    api<Curso[]>("/api/cursos").then(setCursos).catch(manejarError);
    cargarNotificaciones();
  }, [cargarNotificaciones, manejarError]);

  const cargarEstudiantes = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const lista = await api<EstudianteItem[]>(
        `/api/estudiantes${query({ momento, asignatura, curso, prioridad, q: q.trim(), solo_alertas: soloAlertas })}`,
      );
      setEstudiantes(lista);
    } catch (err) {
      manejarError(err);
    } finally {
      setCargando(false);
    }
  }, [momento, asignatura, curso, prioridad, q, soloAlertas, manejarError]);

  useEffect(() => {
    const temporizador = setTimeout(() => { cargarEstudiantes(); }, q ? 250 : 0);
    return () => clearTimeout(temporizador);
  }, [cargarEstudiantes, q]);

  useEffect(() => {
    if (seleccionado === null) {
      setDetalle(null);
      return;
    }
    let activo = true;
    api<EstudianteDetalle>(`/api/estudiantes/${seleccionado}${query({ momento })}`)
      .then((datos) => { if (activo) setDetalle(datos); })
      .catch((err) => { if (activo) manejarError(err); });
    return () => { activo = false; };
  }, [seleccionado, momento, manejarError, estudiantes]);

  const asignaturas = useMemo(
    () => Array.from(new Set(cursos.map((c) => c.asignatura))).sort(),
    [cursos],
  );
  const cursosFiltrados = useMemo(
    () => cursos.filter((c) => !asignatura || c.asignatura === asignatura),
    [cursos, asignatura],
  );
  const conteos = useMemo(() => ({
    Alta: estudiantes.filter((e) => e.prioridad === "Alta").length,
    Media: estudiantes.filter((e) => e.prioridad === "Media").length,
    Baja: estudiantes.filter((e) => e.prioridad === "Baja").length,
  }), [estudiantes]);
  const momentoActual = MOMENTOS.find((m) => m.valor === momento)!;

  async function generarAlertas() {
    setProcesando("Actualizando predicciones…");
    setError("");
    try {
      await api("/api/alertas/generar", { method: "POST", body: JSON.stringify({ momento }) });
      await cargarEstudiantes();
      await cargarNotificaciones();
    } catch (err) {
      manejarError(err);
    } finally {
      setProcesando("");
    }
  }

  async function marcarNotificacion(id: number, cambios: { leida?: boolean; atendida?: boolean }) {
    try {
      await api(`/api/notificaciones/${id}`, { method: "PATCH", body: JSON.stringify(cambios) });
      await cargarNotificaciones();
      if (seleccionado !== null) {
        const actualizado = await api<EstudianteDetalle>(`/api/estudiantes/${seleccionado}${query({ momento })}`);
        setDetalle(actualizado);
      }
    } catch (err) {
      manejarError(err);
    }
  }

  async function cerrarSesion() {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      // Igualmente se dirige al login: la sesión se cierra por inactividad en el servidor.
    }
    router.replace("/login");
    router.refresh();
  }

  function abrirNotificacion(notificacion: NotificacionItem) {
    setMomento(notificacion.momento as Momento);
    setSeleccionado(notificacion.inscripcion_id);
    setPanelNotif(false);
    if (!notificacion.leida) marcarNotificacion(notificacion.id, { leida: true });
  }

  return (
    <div className="app-shell">
      <header className="barra-superior">
        <div className="marca">
          <span className="marca-icono">AT</span>
          <div>
            <strong>Alertas tempranas</strong>
            <small>Acompañamiento académico</small>
          </div>
        </div>
        <div className="barra-acciones">
          <button
            className={`boton-notificaciones ${resumenNotif.no_leidas ? "con-alerta" : ""}`}
            onClick={() => setPanelNotif(!panelNotif)}
            aria-label={`Notificaciones: ${resumenNotif.no_leidas} sin leer`}
          >
            Notificaciones
            {resumenNotif.no_leidas > 0 && <span className="contador">{resumenNotif.no_leidas}</span>}
          </button>
          <div className="avatar" title={docente.email}>{docente.nombre.charAt(0)}</div>
          <div className="datos-usuario">
            <strong>{docente.nombre}</strong>
            <small>Docente · {docente.codigo}</small>
          </div>
          <button className="boton-salir" onClick={cerrarSesion}>Salir</button>
        </div>
      </header>

      {panelNotif && (
        <>
          <div className="telon" onClick={() => setPanelNotif(false)} />
          <aside className="drawer" aria-label="Centro de notificaciones">
            <div className="drawer-cabecera">
              <div>
                <h3>Notificaciones</h3>
                <p>{resumenNotif.activas} alertas activas · {resumenNotif.pendientes} por atender</p>
              </div>
              <button className="cerrar-drawer" onClick={() => setPanelNotif(false)}>Cerrar</button>
            </div>
            <div className="drawer-lista">
              {notificaciones.length === 0 && (
                <div className="vacio"><p>Por ahora no hay alertas activas.</p></div>
              )}
              {notificaciones.map((n) => (
                <button key={n.id} className={`notif ${n.leida ? "" : "sin-leer"}`} onClick={() => abrirNotificacion(n)}>
                  <span className={`punto prioridad-${n.prioridad.toLowerCase()}`} />
                  <span className="notif-cuerpo">
                    <strong>{n.titulo}</strong>
                    <small>{n.estudiante_id} · {n.asignatura} · {n.curso}</small>
                    <span>{n.mensaje}</span>
                  </span>
                  <span className="notif-hora">{new Date(n.created_at).toLocaleDateString("es-CO", { day: "2-digit", month: "short" })}</span>
                </button>
              ))}
            </div>
          </aside>
        </>
      )}

      <main className="contenido">
        <section className="bienvenida">
          <div>
            <h1>Hola, {docente.nombre.split(" ")[0]}</h1>
            <p>Veamos cómo van tus estudiantes. Puedes filtrar por curso y revisar cada caso con calma.</p>
          </div>
          <div className="momento-box">
            <label htmlFor="momento">Momento del semestre</label>
            <select id="momento" value={momento} onChange={(e) => setMomento(e.target.value as Momento)}>
              {MOMENTOS.map((m) => <option key={m.valor} value={m.valor}>{m.etiqueta}</option>)}
            </select>
            <small>{momentoActual.pista}</small>
          </div>
        </section>

        {error && <div className="alerta-error" role="alert">{error}</div>}

        <section className="tarjetas">
          <article className="tarjeta stat">
            <span className="stat-marca" />
            <div><small>Estudiantes visibles</small><strong>{estudiantes.length}</strong></div>
          </article>
          <article className="tarjeta stat prioridad-alta">
            <span className="stat-marca" />
            <div><small>Atención urgente</small><strong>{conteos.Alta}</strong></div>
          </article>
          <article className="tarjeta stat prioridad-media">
            <span className="stat-marca" />
            <div><small>Estar atento</small><strong>{conteos.Media}</strong></div>
          </article>
          <article className="tarjeta stat prioridad-baja">
            <span className="stat-marca" />
            <div><small>Van bien</small><strong>{conteos.Baja}</strong></div>
          </article>
        </section>

        <section className="tarjeta filtros">
          <div className="filtro-campo">
            <label htmlFor="asignatura">Asignatura</label>
            <select id="asignatura" value={asignatura} onChange={(e) => { setAsignatura(e.target.value); setCurso(""); }}>
              <option value="">Todas mis asignaturas</option>
              {asignaturas.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="filtro-campo">
            <label htmlFor="curso">Grupo</label>
            <select id="curso" value={curso} onChange={(e) => setCurso(e.target.value)}>
              <option value="">Todos mis grupos</option>
              {cursosFiltrados.map((c) => <option key={`${c.asignatura}-${c.curso}`} value={c.curso}>{c.curso} ({c.estudiantes})</option>)}
            </select>
          </div>
          <div className="filtro-campo">
            <label htmlFor="prioridad">Prioridad</label>
            <select id="prioridad" value={prioridad} onChange={(e) => setPrioridad(e.target.value as Prioridad | "")}>
              <option value="">Todas</option>
              <option value="Alta">Alta</option>
              <option value="Media">Media</option>
              <option value="Baja">Baja</option>
            </select>
          </div>
          <div className="filtro-campo crecer">
            <label htmlFor="buscar">Buscar estudiante</label>
            <input id="buscar" type="search" maxLength={60} placeholder="Código del estudiante…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <label className="check">
            <input type="checkbox" checked={soloAlertas} onChange={(e) => setSoloAlertas(e.target.checked)} />
            Solo con alerta
          </label>
          <button className="boton-primario" onClick={generarAlertas} disabled={!!procesando}>
            {procesando || "Actualizar predicciones"}
          </button>
        </section>

        <section className="rejilla">
          <article className="tarjeta tabla-wrap">
            <div className="tarjeta-titulo">
              <div>
                <h2>Estudiantes de tus cursos</h2>
                <p>Ordenados por prioridad de acompañamiento.</p>
              </div>
              {cargando && <span className="cargando">Cargando…</span>}
            </div>
            <div className="tabla-scroll">
              <table>
                <thead>
                  <tr><th>Estudiante</th><th>Grupo</th><th>Prioridad</th><th>Probabilidad</th><th></th></tr>
                </thead>
                <tbody>
                  {estudiantes.map((e) => (
                    <tr
                      key={e.inscripcion_id}
                      className={seleccionado === e.inscripcion_id ? "seleccionada" : ""}
                      onClick={() => setSeleccionado(e.inscripcion_id)}
                    >
                      <td><strong>{e.estudiante_id}</strong><small>{e.asignatura}</small></td>
                      <td>{e.curso}</td>
                      <td><span className={`badge prioridad-${e.prioridad.toLowerCase()}`}>{ETIQUETA_PRIORIDAD[e.prioridad]}</span></td>
                      <td>
                        <div className="barra"><div className={`relleno prioridad-${e.prioridad.toLowerCase()}`} style={{ width: `${Math.round(e.probabilidad * 100)}%` }} /></div>
                        <small>{Math.round(e.probabilidad * 100)}%</small>
                      </td>
                      <td>{e.no_leida && <span className="punto-nuevo" title="Notificación sin leer" />}</td>
                    </tr>
                  ))}
                  {!cargando && estudiantes.length === 0 && (
                    <tr><td colSpan={5} className="vacio-tabla">No hay estudiantes con estos filtros.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <article className="tarjeta ficha">
            {detalle === null ? (
              <div className="vacio">
                <h3>Selecciona un estudiante</h3>
                <p>Verás el resumen del caso, las señales que influyen y una acción sugerida.</p>
              </div>
            ) : (
              <>
                <div className="ficha-cabecera">
                  <div>
                    <small>Ficha de acompañamiento</small>
                    <h2>{detalle.estudiante_id}</h2>
                    <p>{detalle.asignatura} · Grupo {detalle.curso}</p>
                  </div>
                  <span className={`badge prioridad-${detalle.prioridad.toLowerCase()}`}>{ETIQUETA_PRIORIDAD[detalle.prioridad]}</span>
                </div>

                <div className="probabilidad">
                  <div className="probabilidad-numero">{Math.round(detalle.probabilidad * 100)}%</div>
                  <div>
                    <strong>Probabilidad estimada de no aprobar</strong>
                    <div className="barra grande"><div className={`relleno prioridad-${detalle.prioridad.toLowerCase()}`} style={{ width: `${Math.round(detalle.probabilidad * 100)}%` }} /></div>
                    <small>Modelo: {detalle.modelo.replace(/.*\//, "")}</small>
                  </div>
                </div>

                <div className="resumen">
                  <div className="resumen-titulo">
                    <h3>Resumen del caso</h3>
                  </div>
                  <h4>{detalle.resumen.titulo}</h4>
                  {detalle.resumen.texto.split("\n").filter(Boolean).map((parrafo, i) => <p key={i}>{parrafo}</p>)}
                  <div className="accion"><strong>Acción sugerida</strong><p>{detalle.resumen.accion}</p></div>
                </div>

                <div className="bloque">
                  <h3>Señales que influyen</h3>
                  {detalle.factores.length === 0 && <p className="suave">No se observan señales individuales destacadas.</p>}
                  {detalle.factores.map((f) => (
                    <div className="factor" key={f.variable}>
                      <span>{f.etiqueta}</span>
                      <div className="mini-barra"><div style={{ width: `${Math.min(100, Math.max(6, Math.round(f.aporte * 40)))}%` }} /></div>
                    </div>
                  ))}
                </div>

                {detalle.notificacion_id !== null && (
                  <div className="ficha-acciones">
                    <button className="boton-secundario" onClick={() => marcarNotificacion(detalle.notificacion_id!, { leida: true })} disabled={!detalle.no_leida}>
                      {detalle.no_leida ? "Marcar como leída" : "Leída"}
                    </button>
                    <button className="boton-primario" onClick={() => marcarNotificacion(detalle.notificacion_id!, { atendida: true })} disabled={detalle.atendida}>
                      {detalle.atendida ? "Atendida" : "Marcar como atendida"}
                    </button>
                  </div>
                )}
              </>
            )}
          </article>
        </section>

        <footer className="pie">
          <p>La predicción es una orientación: el docente decide la intervención. Los datos son sintéticos y se usan solo para demostrar el prototipo.</p>
          <p>Se trabajan identificadores seudonimizados y no se comparten datos personales con el generador del resumen.</p>
        </footer>
      </main>
    </div>
  );
}
