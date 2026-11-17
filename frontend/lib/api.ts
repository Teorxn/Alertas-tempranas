export type Prioridad = "Alta" | "Media" | "Baja";
export type Momento = "T0_inicio" | "T1_corte1" | "T2_corte2";

export interface Docente {
  id: number;
  nombre: string;
  email: string;
  codigo: string;
}

export interface Curso {
  asignatura: string;
  curso: string;
  estudiantes: number;
}

export interface EstudianteItem {
  inscripcion_id: number;
  estudiante_id: string;
  asignatura: string;
  curso: string;
  momento: string;
  probabilidad: number;
  prioridad: Prioridad;
  no_leida: boolean;
}

export interface FactorItem {
  variable: string;
  etiqueta: string;
  valor: string;
  aporte: number;
}

export interface ResumenItem {
  titulo: string;
  texto: string;
  accion: string;
  fuente: "llm" | "plantilla";
}

export interface EstudianteDetalle {
  inscripcion_id: number;
  estudiante_id: string;
  asignatura: string;
  curso: string;
  momento: string;
  probabilidad: number;
  prioridad: Prioridad;
  modelo: string;
  factores: FactorItem[];
  resumen: ResumenItem;
  senales: string[];
  notificacion_id: number | null;
  no_leida: boolean;
  atendida: boolean;
}

export interface NotificacionItem {
  id: number;
  inscripcion_id: number;
  estudiante_id: string;
  asignatura: string;
  curso: string;
  momento: string;
  prioridad: Prioridad;
  probabilidad: number;
  titulo: string;
  mensaje: string;
  leida: boolean;
  atendida: boolean;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
    this.name = "ApiError";
  }
}

function leerCookie(nombre: string): string | undefined {
  const prefijo = `${nombre}=`;
  const parte = document.cookie.split("; ").find((c) => c.startsWith(prefijo));
  return parte ? decodeURIComponent(parte.slice(prefijo.length)) : undefined;
}

export async function ensureCsrf(): Promise<void> {
  if (!leerCookie("ews_csrf")) {
    await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store" });
  }
}

export async function api<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const metodo = (init.method || "GET").toUpperCase();
  const cabeceras = new Headers(init.headers);
  const csrf = leerCookie("ews_csrf");
  if (!["GET", "HEAD", "OPTIONS"].includes(metodo) && csrf) {
    cabeceras.set("X-CSRF-Token", csrf);
  }
  if (init.body && !cabeceras.has("Content-Type")) {
    cabeceras.set("Content-Type", "application/json");
  }

  const respuesta = await fetch(ruta, {
    ...init,
    headers: cabeceras,
    credentials: "same-origin",
    cache: "no-store",
  });

  if (!respuesta.ok) {
    const cuerpo = (await respuesta.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(respuesta.status, cuerpo.detail || "No se pudo completar la acción");
  }
  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

export function query(params: Record<string, string | number | boolean | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== "" && valor !== false) q.set(clave, String(valor));
  });
  const texto = q.toString();
  return texto ? `?${texto}` : "";
}
