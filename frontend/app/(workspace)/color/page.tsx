"use client";
import { useEffect, useState } from "react";
import { api, type Status } from "@/lib/api";
import { ColorView } from "@/components/ColorView";

export default function Page() {
  const [status, setStatus] = useState<Status | null>(null);
  useEffect(() => { api.status().then(setStatus).catch(() => {}); }, []);
  return (
    <section className="view active">
      <ColorView enabled={!!status?.color_model} />
    </section>
  );
}
