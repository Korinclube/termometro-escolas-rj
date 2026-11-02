import { useEffect, useRef, useState } from "react";
import type { Cenario, SalaParams, Selecao } from "../lib/api";
import { consulta, useApi } from "../lib/api";
import { Botao, Carregando, Erro, classeBotao } from "./ui";

export function BoletimDialog({
  aberto,
  onFechar,
  sel,
  sala,
  cenario,
}: {
  aberto: boolean;
  onFechar: () => void;
  sel: Selecao;
  sala: SalaParams;
  cenario: Cenario;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [copiado, setCopiado] = useState(false);
  const { dados, erro, carregando } = useApi<{ texto: string }>(aberto ? `/api/boletim?${consulta(sel, sala, cenario)}` : null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (aberto && !d.open) d.showModal();
    if (!aberto && d.open) d.close();
    setCopiado(false);
  }, [aberto]);

  return (
    <dialog
      ref={ref}
      onClose={onFechar}
      className="w-[min(640px,calc(100vw-32px))] rounded-[var(--radius)] border border-line bg-surface p-0 text-ink backdrop:bg-black/50"
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="font-display text-sm font-bold tracking-tight">Boletim para WhatsApp · {sel.nome}</h2>
        <button type="button" onClick={onFechar} className="text-sm text-muted hover:text-ink" aria-label="Fechar">
          ✕
        </button>
      </div>
      <div className="p-4">
        {carregando && <Carregando />}
        {erro && <Erro mensagem={erro} />}
        {dados && (
          <>
            <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap border border-line bg-raised p-3 font-sans text-sm">{dados.texto}</pre>
            <div className="mt-3 flex flex-wrap gap-2">
              <Botao primario onClick={() => navigator.clipboard.writeText(dados.texto).then(() => setCopiado(true))}>
                {copiado ? "Copiado" : "Copiar texto"}
              </Botao>
              <a
                className={classeBotao()}
                href={`https://wa.me/?text=${encodeURIComponent(dados.texto)}`}
                target="_blank"
                rel="noreferrer"
              >
                Abrir no WhatsApp
              </a>
            </div>
            <p className="mt-3 text-xs text-muted">
              Texto gerado pelo cálculo, sem IA. Revise antes de encaminhar a grêmios, famílias ou ao Sepe.
            </p>
          </>
        )}
      </div>
    </dialog>
  );
}
