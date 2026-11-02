import type { ReactNode } from "react";
import { FAIXAS, type Faixa } from "../lib/fisica";

export const COR_FAIXA: Record<Faixa, string> = {
  Normal: "bg-normal",
  Atenção: "bg-atencao",
  Alerta: "bg-alerta",
  Perigo: "bg-perigo",
};
export const TEXTO_FAIXA: Record<Faixa, string> = {
  Normal: "text-normal",
  Atenção: "text-atencao",
  Alerta: "text-alerta",
  Perigo: "text-perigo",
};
/** Nome do token de cada faixa em theme.css. */
export const TOKEN_FAIXA: Record<Faixa, string> = {
  Normal: "faixa-normal",
  Atenção: "faixa-atencao",
  Alerta: "faixa-alerta",
  Perigo: "faixa-perigo",
};
export const VAR_FAIXA = Object.fromEntries(
  Object.entries(TOKEN_FAIXA).map(([f, t]) => [f, `rgb(var(--${t}))`]),
) as Record<Faixa, string>;

/** Faixa como texto com marcador quadrado (sem pílula). */
export function FaixaMarca({ faixa }: { faixa: Faixa | "Sem aula" }) {
  if (faixa === "Sem aula") return <span className="text-muted">Sem aula</span>;
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold ${TEXTO_FAIXA[faixa]}`}>
      <span aria-hidden className={`inline-block h-2.5 w-2.5 ${COR_FAIXA[faixa]}`} />
      {faixa}
    </span>
  );
}

export function Secao({
  titulo,
  meta,
  acoes,
  children,
  className = "",
}: {
  titulo: string;
  meta?: ReactNode;
  acoes?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 border border-line bg-surface rounded-[var(--radius)] ${className}`}>
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-display text-sm font-bold tracking-tight">{titulo}</h2>
          {meta && <p className="mt-0.5 text-xs text-muted">{meta}</p>}
        </div>
        {acoes && <div className="flex flex-wrap items-center gap-2">{acoes}</div>}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Metrica({ rotulo, valor, nota }: { rotulo: string; valor: ReactNode; nota?: ReactNode }) {
  return (
    <div className="min-w-0 border-l-2 border-line pl-3">
      <div className="text-xs text-muted">{rotulo}</div>
      <div className="num mt-1 text-2xl font-semibold leading-none">{valor}</div>
      {nota && <div className="mt-1 text-xs text-muted">{nota}</div>}
    </div>
  );
}

export function classeBotao(primario = false): string {
  const base =
    "inline-flex items-center gap-2 rounded-[var(--radius)] px-3 py-1.5 text-sm font-semibold transition-colors " +
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
    "disabled:cursor-not-allowed disabled:opacity-50";
  const estilo = primario
    ? "bg-accent text-on-accent hover:bg-accent/90"
    : "border border-line bg-surface hover:bg-raised";
  return `${base} ${estilo}`;
}

/** Aviso em destaque dentro de um bloco (tom da faixa ou de erro). */
export function Nota({ tom, children }: { tom: "atencao" | "alerta"; children: ReactNode }) {
  const cor = tom === "alerta" ? "border-alerta bg-alerta/10" : "border-atencao bg-atencao/10";
  return <p className={`border-l-2 px-3 py-2 text-sm ${cor}`}>{children}</p>;
}

/** Subtítulo dentro de um bloco. */
export function Subtitulo({ children }: { children: ReactNode }) {
  return <h3 className="text-xs font-semibold text-muted">{children}</h3>;
}

/** Barra de distribuição pelas quatro faixas, com contagem e unidade. */
export function BarraFaixas({
  contagem,
  unidade = "",
  rotulo,
}: {
  contagem: Record<Faixa, number>;
  unidade?: string;
  rotulo?: string;
}) {
  const total = FAIXAS.reduce((s, f) => s + contagem[f], 0);
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden bg-raised" aria-hidden>
        {FAIXAS.map((f) => (
          <div key={f} className={COR_FAIXA[f]} style={{ width: `${total ? (100 * contagem[f]) / total : 0}%` }} />
        ))}
      </div>
      <p className="num mt-1 text-xs text-muted">
        {rotulo && <span className="font-sans">{rotulo} </span>}
        {FAIXAS.map((f) => `${f} ${contagem[f]}${unidade}`).join(" · ")}
      </p>
    </div>
  );
}

export function Botao({
  children,
  onClick,
  primario = false,
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  primario?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={classeBotao(primario)}>
      {children}
    </button>
  );
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <p role="status" className="py-6 text-sm text-muted">
      {texto}
    </p>
  );
}

export function Erro({ mensagem }: { mensagem: string }) {
  return (
    <p role="alert" className="border-l-2 border-perigo bg-perigo/10 px-3 py-2 text-sm">
      {mensagem}
    </p>
  );
}

export const campo =
  "rounded-[var(--radius)] border border-line bg-surface px-2 py-1.5 text-sm " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent";
