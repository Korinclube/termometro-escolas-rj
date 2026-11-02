import { Botao } from "./ui";

export type Aba = "monitoramento" | "mapa" | "simulador" | "ficha" | "gemini";

export const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "monitoramento", rotulo: "Monitoramento 72h" },
  { id: "mapa", rotulo: "Mapa de risco" },
  { id: "simulador", rotulo: "Simulador da sala" },
  { id: "ficha", rotulo: "Ficha de evidência" },
  { id: "gemini", rotulo: "Laboratório Gemini" },
];

export function TopBar({
  aba,
  onAba,
  onBoletim,
}: {
  aba: Aba;
  onAba: (a: Aba) => void;
  onBoletim: () => void;
}) {
  return (
    <header className="no-print sticky top-0 z-[1000] border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2">
        <div className="font-display text-base font-extrabold tracking-tight">
          Termômetro das Escolas <span className="text-alerta">RJ</span>
        </div>
        <nav aria-label="Seções" className="order-3 -mx-1 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto md:flex-1 md:justify-center">
          {ABAS.map((a) => (
            <button
              key={a.id}
              type="button"
              aria-current={aba === a.id ? "page" : undefined}
              onClick={() => onAba(a.id)}
              className={
                "whitespace-nowrap border-b-2 px-3 py-2 text-sm font-semibold transition-colors " +
                (aba === a.id ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink")
              }
            >
              {a.rotulo}
            </button>
          ))}
        </nav>
        <div className="ml-auto md:ml-0">
          <Botao primario onClick={onBoletim}>
            Exportar boletim
          </Botao>
        </div>
      </div>
    </header>
  );
}
