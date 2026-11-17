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
        <div className="hero-badge">🎓 Semillero de investigación</div>
        <h1>
          Llegar antes
          <br />
          <span>importa</span>
        </h1>
        <p>
          Detecta señales de acompañamiento académico a tiempo, entiende qué está pasando
          y actúa con tus estudiantes antes de que sea demasiado tarde.
        </p>
        <div className="hero-ilustracion" aria-hidden="true">
          <span className="burbuja b1">📘</span>
          <span className="burbuja b2">💡</span>
          <span className="burbuja b3">🚦</span>
          <div className="hero-tarjeta">
            <div className="hero-tarjeta-linea" />
            <div className="hero-tarjeta-linea corta" />
            <div className="hero-tarjeta-pill">Alerta temprana · Corte 1</div>
          </div>
        </div>
        <p className="hero-nota">Datos sintéticos · Prototipo de investigación</p>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={enviar} noValidate>
          <div className="login-logo">🚦</div>
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
            Tu sesión es privada: solo ves los cursos que dictas. El modelo sugiere, tú decides.
          </p>
        </form>
      </section>
    </main>
  );
}
