#!/bin/bash
# Carrega um .hal de verdade, sem os pinos externos, so' pra conferir se
# ele SOBE: nomes de pino, addf, loadrt, linha solta fora de comentario.
# E' o teste que pega o erro que impede a maquina de ligar.
#
#     tools/valida_hal.sh custom.hal
#     tools/valida_hal.sh custom.hal probe_basic_postgui_fix.hal
#
# Varios arquivos sao juntados NA ORDEM dada, que e' como o LinuxCNC os le
# (o postgui sozinho nao carrega: usa componentes do custom.hal, como o
# not.0, e sinais do Dino_Evo.hal, como o jog-speed).
#
# LIMITE: nao da' pra validar a cadeia inteira incluindo o Dino_Evo.hal —
# ele comeca com `loadrt [KINS]KINEMATICS`, que so' resolve com o INI em
# maos. Na pratica o que se valida e' o custom.hal, que e' onde a logica
# mora; o resto e' conferido pela checagem de linha solta, que roda em
# todos os arquivos passados.
#
# RECUSA RODAR COM O LINUXCNC ABERTO. O halrun precisa de uma sessao de
# realtime limpa, e o `halrun -U` que isso exige DERRUBA a HAL da sessao
# em andamento — ja' aconteceu em 2026-10-16, com a maquina ligada: o
# LinuxCNC ficou na tela mas sem HAL nenhuma por tras. (A posicao foi
# salva certo pelo salva_posicao.py, que recebe SIGTERM, mas nao da' pra
# contar com sorte.)
set -u
ARQS=("${@:-custom.hal}")
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
cd "$AQUI" || exit 1

if pgrep -x linuxcncsvr >/dev/null 2>&1; then
    echo "RECUSADO: o LinuxCNC esta aberto."
    echo "Feche-o antes — validar exige derrubar o realtime, e isso mataria"
    echo "a HAL da sessao que esta rodando."
    exit 2
fi

for a in "${ARQS[@]}"; do
    if [ ! -f "$a" ]; then
        echo "Nao achei $a"; exit 1
    fi
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

python3 - "$TMP/sem_externos.hal" "${ARQS[@]}" <<'PY'
import io, re, sys
saida, entradas = sys.argv[1], sys.argv[2:]
EXTERNOS = ("hm2_", "halui.", "joint.", "axis.", "iocontrol.", "motion.",
            "qtpyvcp.", "ams32.", "dino_", "salvaposicao.", "chuckangle.",
            "partcounter.")
COMANDOS = r"^(loadrt|loadusr|addf|net|setp|sets|unlinkp|start|stop|source)\b"
ruins, linhas = [], ["loadrt threads name1=servo-thread period1=1000000"]
for entrada in entradas:
  for n, l in enumerate(io.open(entrada, encoding="utf-8"), 1):
      bruta = l.strip()
      if bruta and not bruta.startswith("#") and not re.match(COMANDOS, bruta):
          ruins.append((entrada, n, bruta[:60]))
      s = l.split("#")[0].strip()
      if not s:
          continue
      if s.startswith("net "):
          toks = s.split()
          mantidos = [x for x in toks[2:]
                      if x not in ("<=", "=>") and not x.startswith(EXTERNOS)]
          if mantidos:
              linhas.append("net %s %s" % (toks[1], " ".join(mantidos)))
          continue
      if s.startswith(("setp ", "sets ")) and s.split()[1].startswith(EXTERNOS):
          continue
      if s.startswith("loadusr"):
          continue
      linhas.append(s)
linhas.append("start")
io.open(saida, "w", encoding="utf-8").write("\n".join(linhas) + "\n")
if ruins:
    print("LINHAS SOLTAS (nem comentario nem comando):")
    for arq, n, s in ruins:
        print("  %s linha %d: %s" % (arq, n, s))
    sys.exit(1)
PY
[ $? -ne 0 ] && exit 1

halrun -U >/dev/null 2>&1
SAIDA="$(halrun -f "$TMP/sem_externos.hal" 2>&1 | grep -v '^Note:')"
halrun -U >/dev/null 2>&1

if [ -n "$SAIDA" ]; then
    echo "${ARQS[*]} NAO carregou:"
    echo "$SAIDA"
    exit 1
fi
echo "${ARQS[*]} carregou limpo."
