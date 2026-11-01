# Agente de IA do torno (aba AGENTE IA)

A aba AGENTE IA, a última da tela, tem um chat para pedir programas, por texto ou pelo microfone.
Cada mensagem roda o Claude Code (`claude -p`) com um servidor MCP próprio (`servidor_mcp.py`).
O agente só monta programas pelo gerador da aba GERAR PGM, valida no interpretador do LinuxCNC
(`rs274`) e salva o `.ngc` na pasta de programas. A aba mostra o G-code e carrega o arquivo no
LinuxCNC sozinha, só com o interpretador parado. O agente não tem shell, arquivos nem internet,
não move eixos e não dá partida no ciclo.

Quando o agente começa a gerar ou modificar um programa, a aba primeiro descarrega o programa que
está no LinuxCNC (o mesmo "novo programa" da tela) e só carrega o novo depois de salvo e validado.
Com a máquina executando, nada é descarregado nem carregado.

Os valores do programa salvo também vão para a aba GERAR PGM, para o operador assumir de lá: cada
operação no formulário dela e, com mais de uma operação, a fila com todas na ordem do agente
(SALVAR + CARREGAR refaz o mesmo programa). A fila que estava na GERAR PGM é trocada pela do agente.
A GERAR PGM guarda sempre os últimos valores, do operador ou do agente (inclusive o que foi digitado
sem ENTER, ao trocar de aba ou fechar o LinuxCNC), em `torno_cam_ui.json`, que fica fora do git.

Regras do agente:
- faceamento termina sempre em Z0 e o sobremetal é para mais (facear 3 mm = Z3 até Z0);
- furação sempre em ciclo: G81 (furo direto, PASSO 0), G82 (com espera) ou G83 (com bicada);
- furo de centro sempre G81 (quebra-cavaco 0, sem espera);
- "ferramenta negativa" deixa negativos todos os X da operação (Ø50 para Ø38 = X-50 para X-38).
  A rosca não aceita X negativo no gerador: o agente avisa.

## Instalar no torno (uma vez, usuário `evo`)

1. Instale o Claude Code:
   ```
   curl -fsSL https://claude.ai/install.sh | bash
   ```
2. Faça login no terminal (o login do aplicativo não vale para o comando `claude`):
   ```
   claude auth login
   ```
   Confira com `claude auth status`: tem que aparecer `"loggedIn": true`.
3. `git pull` nesta pasta e reabra o LinuxCNC.

Para digitar no chat, o torno precisa de um teclado (físico ou o teclado virtual do sistema).

## Microfone (Whisper local, sem internet)

Dois jeitos de falar:
- **Segurar SHIFT** com a aba aberta: grava enquanto o SHIFT está apertado; ao soltar, transcreve e
  já envia ao agente. Maiúscula (SHIFT+letra) e SHIFT+ENTER continuam normais: com outra tecla
  junto, a gravação é descartada.
- **Botão do microfone** (toque): toque, fale e toque de novo. O texto aparece na caixa para
  conferir antes de tocar ENVIAR.

Instalação, uma vez:

1. Áudio do Qt e ambiente separado do Python:
   ```
   sudo apt install libqt5multimedia5-plugins python3-venv
   ```
2. Whisper num ambiente separado (não mexe no Python do LinuxCNC):
   ```
   python3 -m venv ~/.local/share/agente_torno/voz
   ~/.local/share/agente_torno/voz/bin/pip install faster-whisper
   ```
3. Baixe o modelo (uns 480 MB, uma vez):
   ```
   ~/.local/share/agente_torno/voz/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root='$HOME/.local/share/agente_torno/voz/modelos')"
   ```

Um microfone USB ou headset ligado no PC do torno é o suficiente. Se o PC for fraco, use o
modelo `base` (troque `small` por `base` no passo 3 e defina `AGENTE_VOZ_MODELO=base`).

## Arquivos

- `torno_cam/agente/servidor_mcp.py`: servidor MCP por stdio, sem pacote extra.
- `torno_cam/agente/ferramentas.py`: listar_operacoes, buscar_rosca, sugerir_furacao,
  gerar_programa e salvar_programa. `salvar_programa` recebe as operações, nunca texto de G-code.
- `torno_cam/agente/prompt_sistema.md`: as regras do agente.
- `torno_cam/agente/transcrever.py`: a transcrição de voz (roda no ambiente do Whisper).
- `torno_cam_ui/agente_tab.py`: a aba (chat, microfone, programa e carregamento).
- `user_tabs/agente_ia/agente_ia.py`: o arquivo que o Probe Basic carrega.

## Opções

- `AGENTE_MODELO`: modelo do Claude (sem ela, vale o padrão da conta).
- `AGENTE_VOZ_MODELO`: modelo do Whisper (`small` por padrão).
- A conversa continua entre mensagens; NOVA CONVERSA começa outra.
- Se aparecer "não está logado", repita o passo 2 da instalação.
