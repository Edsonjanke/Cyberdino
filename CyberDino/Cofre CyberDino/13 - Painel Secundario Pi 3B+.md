# Painel Secundario - Raspberry Pi 3B+

> **PROJETO ELIMINADO em 2026-08-01.** O painel do Raspberry Pi nao
> sera usado. O codigo dele saiu do config (commit 8eaf79c) e o IP
.103 ficou livre. Nota mantida so como historico.

## Hardware
| Componente      | Detalhe                                       |
| --------------- | --------------------------------------------- |
| **Pi**          | Raspberry Pi 3B+                              |
| **IP Cabo**     | 192.168.0.103 (hostname: cyberdino)           |
| **Tela**        | BTT PITFT70, DSI, **800x480** (nao 1024x600!) |
| **Touch**       | Capacitivo USB                                |
| **PC LinuxCNC** | 192.168.0.120                                 |

## Arquitetura
```
PC (192.168.0.120):
  Xvfb :1 (800x480) -> secondary_panel.py -> x11vnc porta 5901

Pi (192.168.0.103):
  xtigervncviewer 192.168.0.120::5901 -FullScreen
```
- Separado do ProbeBasic principal (display :0 do PC)
- Pi e terminal burro (VNC client), processamento no PC

## Painel (secondary_panel.py)
- Python3 + PyQt5 + modulo linuxcnc (stat/command)
- **Duas paginas** alternadas via QStackedWidget:
- Tema escuro com cobre (matching ProbeBasic)
- Reconecta automaticamente se LinuxCNC nao estiver rodando

### Pagina DRO (padrao)
- DRO posicao X/Z (diametro, com offsets G5x + G92 + tool)
- Ferramenta atual, Feed, Tempo de ciclo
- Visualizador G-code (5 linhas antes/depois da atual)
- Spindle Override: botoes 50/75/100/150/200% + ajuste fino -10/-1/+1/+10
- Rapid Override: botoes 5/25/50/75/100%
- Botao **MDI** para trocar de pagina

### Pagina MDI (estilo ProbeBasic)
- Campo de entrada MDI na barra inferior + botoes DRO/MDI
- Historico de comandos (lista branca, duplo-clique para recall)
- Botoes de acao: DEL SEL, DEL ALL, CLR QUE, PAUSE, RUN FROM, RUN SEL
- Teclado touch 5 colunas:
  - Letras (laranja): I J K D R / X Y Z A B / G F M S T H O P L Q
  - Numeros (branco): 0-9, ponto
  - Menos (vermelho), SPACE, ⌫, ◄ ►, ENTER
- Envia comando via `linuxcnc.command.mdi()` (troca automatica para MODE_MDI)

## Arquivos no PC
| Arquivo | Funcao |
|---------|--------|
| `secondary_panel.py` | Painel PyQt5 |
| `start_panel.sh` | Launcher (Xvfb + painel + x11vnc) |
| `cyberdino-panel.service` | Systemd service autostart |

## Autostart
**PC:** `sudo systemctl enable cyberdino-panel`
**Pi:** `/usr/local/bin/start-vnc.sh` (xinit + matchbox-window-manager + vncviewer)

## Status
Funcionando desde 2026-04-09. Autostart configurado (pendente validar apos reinicio).
Pagina MDI adicionada em 2026-04-10.
