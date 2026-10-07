import { useEffect, useState } from "react";

export type Route =
  | { page: "beranda" }
  | { page: "sumber" }
  | { page: "pasien" }
  | { page: "pasien-detail"; id: number }
  | { page: "peringatan" }
  | { page: "ganda" }
  | { page: "kode" }
  | { page: "kualitas"; rule?: string };

export function parseHash(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query ?? "");
  switch (parts[0]) {
    case "sumber":
      return { page: "sumber" };
    case "pasien":
      return parts[1] ? { page: "pasien-detail", id: Number(parts[1]) } : { page: "pasien" };
    case "peringatan":
      return { page: "peringatan" };
    case "ganda":
      return { page: "ganda" };
    case "kode":
      return { page: "kode" };
    case "kualitas":
      return { page: "kualitas", rule: params.get("masalah") ?? undefined };
    default:
      return { page: "beranda" };
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setRoute(parseHash(window.location.hash));
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function go(path: string) {
  window.location.hash = path;
}
