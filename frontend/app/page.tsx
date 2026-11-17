import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function Inicio() {
  const sesion = await cookies();
  redirect(sesion.has("ews_session") ? "/dashboard" : "/login");
}
