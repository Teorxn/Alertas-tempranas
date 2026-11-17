import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Docente } from "@/lib/api";
import DashboardClient from "./dashboard-client";

export default async function Panel() {
  const sesion = await cookies();
  const base = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
  const respuesta = await fetch(`${base}/api/auth/me`, {
    headers: { cookie: sesion.toString() },
    cache: "no-store",
  });
  if (!respuesta.ok) redirect("/login");
  const docente = (await respuesta.json()) as Docente;
  return <DashboardClient docente={docente} />;
}
