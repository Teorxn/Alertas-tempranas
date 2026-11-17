"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api, ensureCsrf } from "@/lib/api";

export default function PaginaLogin() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [verClave, setVerClave] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError("");
    setCargando(true);
    try {
      await ensureCsrf();
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Demasiados intentos. Espera unos minutos e inténtalo de nuevo.");
      } else {
        setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
      }
      setCargando(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-hero">
        <div className="hero-badge">Sistema de alertas tempranas</div>
        <h1>
          Detecta señales
          <br />
          <span>a tiempo</span>
        </h1>
        <p>
          Identifica estudiantes que necesitan acompañamiento académico mientras aún hay
          oportunidad de intervenir.
        </p>

        <div className="hero-panel" aria-hidden="true">
          <div className="hero-panel-header">Seguimiento del semestre</div>
          <div className="hero-panel-row"><span>T0 · Inicio</span><span>Historial</span></div>
          <div className="hero-panel-row"><span>T1 · Corte 1</span><span>Primeras notas</span></div>
          <div className="hero-panel-row"><span>T2 · Corte 2</span><span>Último tramo</span></div>
        </div>

        <p className="hero-nota">Prototipo de investigación · Datos sintéticos</p>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={enviar} noValidate>
          <div className="login-logo">AT</div>
          <h2>Bienvenido, profesor</h2>
          <p className="login-sub">Ingresa para ver los estudiantes de tus cursos.</p>

          <label htmlFor="email">Correo institucional</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            required
            maxLength={255}
            placeholder="nombre@universidad.edu.co"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label htmlFor="password">Contraseña</label>
          <div className="clave-campo">
            <input
              id="password"
              name="password"
              type={verClave ? "text" : "password"}
              autoComplete="current-password"
              required
              maxLength={256}
              placeholder="Tu contraseña"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="button" className="ver-clave" onClick={() => setVerClave(!verClave)}>
              {verClave ? "Ocultar" : "Ver"}
            </button>
          </div>

          {error && <div className="alerta-error" role="alert">{error}</div>}

          <button className="boton-primario ancho" type="submit" disabled={cargando}>
            {cargando ? "Entrando…" : "Entrar a mi panel"}
          </button>

          <button
            type="button"
            className="demo-link"
            onClick={() => {
              setEmail("ana.torres@universidad.edu.co");
              setPassword("ClaveSegura123!");
              setError("");
            }}
          >
            Usar cuenta de ejemplo (Ana Torres)
          </button>

          <p className="login-foot">
            Tu sesión es privada: solo ves los cursos que dictas. La predicción es una
            orientación y la decisión siempre la toma el docente.
          </p>
        </form>
      </section>
    </main>
  );
}
