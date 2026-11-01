# -*- coding: utf-8 -*-
"""Aba AGENTE IA: chat para pedir programas ao agente.

Cada mensagem roda o Claude Code sem interface (`claude -p`), com:
- so' as ferramentas do servidor MCP do torno (torno_cam/agente): nada de
  shell, arquivo ou internet; o agente monta o programa pelo mesmo motor da
  aba GERAR PGM, valida no interpretador do LinuxCNC e salva o .ngc;
- a conversa continua entre mensagens (--session-id / --resume); NOVA
  CONVERSA comeca outra.

Quando o agente salva um programa, a aba mostra o G-code e carrega o arquivo
no LinuxCNC sozinha, com o mesmo program_actions.load do SALVAR + CARREGAR,
e so' com o interpretador parado. A aba nunca da partida no ciclo.

O processo roda fora da pasta do config (senao o Claude Code leria o
CLAUDE.md dela, que e' para quem edita a interface).
"""

import html
import json
import os
import re
import shutil
import sys
import uuid
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_ROOT = os.path.dirname(_HERE)
if _CONFIG_ROOT not in sys.path:
    sys.path.insert(0, _CONFIG_ROOT)

from qtpy.QtCore import (Qt, QObject, QProcess, QProcessEnvironment, Signal, QEvent,
                         QBuffer, QIODevice, QTimer, QSize)
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
                            QPushButton, QPlainTextEdit, QTextBrowser, QToolButton,
                            QApplication)

try:
    from qtpy.QtMultimedia import QAudioFormat, QAudioInput, QAudioDeviceInfo
except Exception:              # sem o modulo de audio do Qt: o botao avisa
    QAudioInput = None

from .realce_gcode import RealceGcode
from .ciclo_panel import espacamento

try:
    from qtpyvcp.actions import program_actions
except Exception:              # fora do LinuxCNC (testes)
    program_actions = None

SERVIDOR = os.path.join(_CONFIG_ROOT, "torno_cam", "agente", "servidor_mcp.py")
PROMPT = os.path.join(_CONFIG_ROOT, "torno_cam", "agente", "prompt_sistema.md")
PASTA_TRABALHO = os.path.expanduser("~/.local/share/agente_torno")
MARCA_ARQUIVO = "ARQUIVO_SALVO:"
FERRAMENTA_SALVAR = "mcp__torno__salvar_programa"

# Voz: Whisper local num ambiente separado (ver torno_cam/agente/LEIA-ME.md)
TRANSCRITOR = os.path.join(_CONFIG_ROOT, "torno_cam", "agente", "transcrever.py")
PYTHON_VOZ = os.path.expanduser(os.environ.get(
    "AGENTE_VOZ_PYTHON", "~/.local/share/agente_torno/voz/bin/python"))
ICONE_MIC = os.path.join(_HERE, "icones", "microfone.svg")
GRAVACAO_MAX_MS = 60000          # para sozinho depois de 1 minuto

_PAINEL_QSS = ('QFrame#{nome} {{ background: #1A1E24; border: 1px solid #2E343C;'
               ' border-radius: 8px; }}')
_HEAD_QSS = ('QLabel { color: #A9B0B5; font-family: "Bebas Neue"; font-size: 16px;'
             ' background: transparent; border: none; }')
_STATUS_QSS = ('QLabel { color: #A9B0B5; font: 11pt "Barlow Condensed SemiBold";'
               ' background: transparent; border: none; }')
_CHAT_QSS = ('QTextBrowser { background: #0B0D10; color: #E7EAEE; border: 2px solid #2E343C;'
             ' border-radius: 5px; padding: 8px; font-family: "DejaVu Sans"; font-size: 15px; }')
_ENTRADA_QSS = ('QPlainTextEdit { background: #0B0D10; color: #FFFFFF; border: 2px solid #5A6268;'
                ' border-radius: 4px; padding: 6px; font-family: "DejaVu Sans"; font-size: 16px; }'
                ' QPlainTextEdit:focus { border-color: #00838F; }')
_PREVIEW_QSS = ('QPlainTextEdit { background:#0B0D10; color:#E7EAEE;'
                ' border:2px solid #2E343C; border-radius:5px; padding:6px;'
                ' font-family:"DejaVu Sans Mono", monospace; font-size:13px; }')
_BOTAO_QSS = """
QPushButton {{
    background: {fundo}; color: {texto}; border: 2px solid {borda};
    border-radius: 4px; padding: 0px 10px; font-family: "Bebas Neue"; font-size: {fonte}px;
    min-height: {altura}px; max-height: {altura}px;
}}
QPushButton:disabled {{ background: #3A4046; color: #7A8288; border-color: #2E343C; }}
"""


def _botao(texto, fundo="#5A6268", cor="#FFFFFF", borda="#2E343C", altura=48, fonte=18):
    b = QPushButton(texto)
    b.setStyleSheet(_BOTAO_QSS.format(fundo=fundo, texto=cor, borda=borda,
                                      altura=altura, fonte=fonte))
    espacamento(b, 1.0)
    return b


def achar_claude():
    """Caminho do executavel do Claude Code (o PATH do LinuxCNC pode nao ter
    o ~/.local/bin)."""
    achado = shutil.which("claude")
    if achado:
        return achado
    for c in (os.path.expanduser("~/.local/bin/claude"), "/usr/local/bin/claude",
              "/usr/bin/claude"):
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def config_mcp():
    """--mcp-config em JSON: o servidor do torno com o mesmo Python da tela."""
    env = {}
    for k in ("INI_FILE_NAME", "EMC2_HOME", "LINUXCNC_HOME", "PATH", "HOME",
              "TORNO_CAM_STATE", "AGENTE_PASTA_PROGRAMAS"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return json.dumps({"mcpServers": {"torno": {
        "command": sys.executable or "python3", "args": [SERVIDOR], "env": env}}})


def argumentos(sessao, continuar, prompt_sistema, modelo=None):
    """Argumentos do `claude -p` (a mensagem vai pelo stdin)."""
    args = ["-p", "--output-format", "stream-json", "--verbose",
            "--tools", "",                       # sem ferramentas nativas
            "--strict-mcp-config", "--mcp-config", config_mcp(),
            "--allowedTools", "mcp__torno",
            "--setting-sources", "",
            "--system-prompt", prompt_sistema]
    if modelo:
        args += ["--model", modelo]
    args += (["--resume", sessao] if continuar else ["--session-id", sessao])
    return args


def md_para_html(texto):
    """Markdown simples do agente -> HTML do QTextBrowser (negrito, codigo,
    listas e quebras de linha)."""
    partes = re.split(r"```[a-zA-Z]*\n?(.*?)```", texto, flags=re.S)
    saida = []
    for i, p in enumerate(partes):
        if i % 2:          # bloco de codigo
            saida.append('<pre style="background:#14181D; color:#E7EAEE;'
                         ' font-family:\'DejaVu Sans Mono\'; font-size:13px;">'
                         + html.escape(p.rstrip()) + "</pre>")
            continue
        t = html.escape(p)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`([^`]+)`", r"<span style=\"font-family:'DejaVu Sans Mono';"
                   r" color:#5FB3BB;\">\1</span>", t)
        t = re.sub(r"(?m)^\s*[-*] ", "&bull; ", t)
        saida.append(t.strip("\n").replace("\n", "<br>"))
    return "".join(saida)


class ProcessoAgente(QObject):
    """Um `claude -p` por mensagem, lendo o stream-json linha a linha."""

    texto = Signal(str)                  # trecho de resposta do agente
    ferramenta = Signal(str, dict)       # nome curto, argumentos
    resultado = Signal(str, str, bool)   # nome curto, texto, erro
    terminou = Signal(bool, str)         # ok, mensagem final (ou erro)

    def __init__(self, parent=None):
        super(ProcessoAgente, self).__init__(parent)
        self._proc = None
        self._buffer = b""
        self._ferramentas = {}           # tool_use_id -> nome
        self._fim_emitido = False

    def rodando(self):
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def iniciar(self, executavel, args, mensagem):
        self._buffer = b""
        self._ferramentas = {}
        self._fim_emitido = False
        os.makedirs(PASTA_TRABALHO, exist_ok=True)
        p = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        caminho = env.value("PATH", "")
        local = os.path.expanduser("~/.local/bin")
        if local not in caminho.split(":"):
            env.insert("PATH", local + ":" + caminho)
        p.setProcessEnvironment(env)
        p.setWorkingDirectory(PASTA_TRABALHO)
        p.readyReadStandardOutput.connect(self._ler)
        p.finished.connect(self._acabou)
        p.errorOccurred.connect(self._falhou)
        self._proc = p
        p.start(executavel, args)
        p.write(mensagem.encode("utf-8"))
        p.closeWriteChannel()

    def parar(self):
        if self.rodando():
            self._proc.kill()

    # ── leitura do stream-json ────────────────────────────────────────────
    def _ler(self):
        self._buffer += bytes(self._proc.readAllStandardOutput())
        while b"\n" in self._buffer:
            linha, self._buffer = self._buffer.split(b"\n", 1)
            linha = linha.strip()
            if linha:
                self.evento(linha.decode("utf-8", "replace"))

    def evento(self, linha):
        """Trata uma linha do stream-json (publico para os testes)."""
        try:
            ev = json.loads(linha)
        except ValueError:
            return
        tipo = ev.get("type")
        if tipo == "system" and ev.get("subtype") == "init":
            for s in ev.get("mcp_servers") or []:
                if s.get("name") == "torno" and s.get("status") not in (None, "connected"):
                    self.texto.emit(u"[o servidor do torno não conectou: {}]".format(s.get("status")))
        elif tipo == "assistant":
            for c in (ev.get("message") or {}).get("content") or []:
                if c.get("type") == "text" and c.get("text"):
                    self.texto.emit(c["text"])
                elif c.get("type") == "tool_use":
                    nome = c.get("name", "")
                    self._ferramentas[c.get("id")] = nome
                    self.ferramenta.emit(nome, c.get("input") or {})
        elif tipo == "user":
            for c in (ev.get("message") or {}).get("content") or []:
                if c.get("type") != "tool_result":
                    continue
                nome = self._ferramentas.get(c.get("tool_use_id"), "")
                conteudo = c.get("content")
                if isinstance(conteudo, list):
                    conteudo = "\n".join(x.get("text", "") for x in conteudo
                                         if isinstance(x, dict))
                self.resultado.emit(nome, conteudo or "", bool(c.get("is_error")))
        elif tipo == "result":
            self._fim_emitido = True
            erro = bool(ev.get("is_error")) or ev.get("subtype") != "success"
            self.terminou.emit(not erro, ev.get("result") or ev.get("subtype") or "")

    def _acabou(self, codigo, _status):
        if self._buffer.strip():
            self.evento(self._buffer.decode("utf-8", "replace"))
            self._buffer = b""
        if not self._fim_emitido:
            erro = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace").strip()
            self._fim_emitido = True
            self.terminou.emit(False, erro or u"O agente parou (código {}).".format(codigo))

    def _falhou(self, erro):
        if erro == QProcess.FailedToStart and not self._fim_emitido:
            self._fim_emitido = True
            self.terminou.emit(False, u"Não consegui iniciar o Claude Code.")


class Microfone(QObject):
    """Toque para gravar, toque para parar; o texto vem do Whisper local.

    O transcritor (torno_cam/agente/transcrever.py, no Python do Whisper)
    fica aberto depois do primeiro uso, com o modelo carregado: comeca a
    carregar quando a gravacao comeca, entao a primeira frase ja sai rapida."""

    estado = Signal(str)        # "parado", "gravando", "transcrevendo"
    texto = Signal(str)
    erro = Signal(str)

    def __init__(self, parent=None):
        super(Microfone, self).__init__(parent)
        self._entrada = None
        self._buffer = None
        self._formato = None
        self._proc = None
        self._pronto = False
        self._pendente = None
        self._saida = b""
        self._limite = QTimer(self)
        self._limite.setSingleShot(True)
        self._limite.timeout.connect(self.parar)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.encerrar)

    def gravando(self):
        return self._entrada is not None

    def alternar(self):
        if self.gravando():
            self.parar()
        else:
            self.gravar()

    def gravar(self):
        if QAudioInput is None:
            self.erro.emit(u"O Qt desta máquina não tem o módulo de áudio "
                           u"(pacote libqt5multimedia5-plugins).")
            return
        if not os.path.isfile(PYTHON_VOZ):
            self.erro.emit(u"O reconhecimento de voz não está instalado "
                           u"(ver torno_cam/agente/LEIA-ME.md).")
            return
        disp = QAudioDeviceInfo.defaultInputDevice()
        if disp.isNull():
            self.erro.emit(u"Nenhum microfone encontrado.")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleSize(16)
        fmt.setCodec("audio/pcm")
        fmt.setSampleType(QAudioFormat.SignedInt)
        fmt.setByteOrder(QAudioFormat.LittleEndian)
        if not disp.isFormatSupported(fmt):
            fmt = disp.nearestFormat(fmt)        # o Whisper reamostra
        self._formato = fmt
        self._buffer = QBuffer(self)
        self._buffer.open(QIODevice.WriteOnly)
        self._entrada = QAudioInput(disp, fmt, self)
        self._entrada.start(self._buffer)
        self._garantir_transcritor()
        self._limite.start(GRAVACAO_MAX_MS)
        self.estado.emit("gravando")

    def parar(self):
        if not self.gravando():
            return
        self._limite.stop()
        self._entrada.stop()
        dados = bytes(self._buffer.data())
        self._buffer.close()
        self._entrada.deleteLater()
        self._entrada = None
        fmt = self._formato
        largura = max(1, fmt.sampleSize() // 8)
        if len(dados) < fmt.sampleRate() * largura * fmt.channelCount() * 0.4:
            self.estado.emit("parado")
            self.erro.emit(u"Gravação curta demais: toque, fale e toque de novo.")
            return
        os.makedirs(PASTA_TRABALHO, exist_ok=True)
        caminho = os.path.join(PASTA_TRABALHO, "voz.wav")
        with wave.open(caminho, "wb") as w:
            w.setnchannels(fmt.channelCount())
            w.setsampwidth(largura)
            w.setframerate(fmt.sampleRate())
            w.writeframes(dados)
        self.estado.emit("transcrevendo")
        self._pendente = caminho
        self._garantir_transcritor()
        self._enviar_pendente()

    # ── transcritor (processo aberto) ─────────────────────────────────────
    def _garantir_transcritor(self):
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            return
        self._pronto = False
        self._saida = b""
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.SeparateChannels)
        p.readyReadStandardOutput.connect(self._ler)
        p.finished.connect(self._caiu)
        self._proc = p
        p.start(PYTHON_VOZ, [TRANSCRITOR, "--servidor"])

    def _enviar_pendente(self):
        if self._pronto and self._pendente:
            self._proc.write((self._pendente + "\n").encode("utf-8"))
            self._pendente = None

    def _ler(self):
        self._saida += bytes(self._proc.readAllStandardOutput())
        while b"\n" in self._saida:
            linha, self._saida = self._saida.split(b"\n", 1)
            try:
                d = json.loads(linha.decode("utf-8", "replace"))
            except ValueError:
                continue
            if "pronto" in d:
                if d["pronto"]:
                    self._pronto = True
                    self._enviar_pendente()
                else:
                    self._pendente = None
                    self.estado.emit("parado")
                    self.erro.emit(u"O reconhecimento de voz não carregou: {}".format(d.get("erro")))
            elif "texto" in d:
                self.estado.emit("parado")
                if d.get("erro"):
                    self.erro.emit(u"Não consegui transcrever: {}".format(d["erro"]))
                elif d["texto"]:
                    self.texto.emit(d["texto"])
                else:
                    self.erro.emit(u"Não entendi nada na gravação.")

    def _caiu(self, *_a):
        self._pronto = False
        if self._pendente:
            self._pendente = None
            self.estado.emit("parado")
            erro = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace").strip()
            self.erro.emit(u"O reconhecimento de voz parou. {}".format(erro.splitlines()[-1] if erro else ""))

    def cancelar(self):
        """Para a gravacao e joga o audio fora (ex.: o SHIFT era maiuscula)."""
        if not self.gravando():
            return
        self._limite.stop()
        self._entrada.stop()
        self._buffer.close()
        self._entrada.deleteLater()
        self._entrada = None
        self.estado.emit("parado")

    def encerrar(self):
        if self._entrada is not None:
            self._entrada.stop()
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1000)


_MIC_QSS = """
QToolButton {{
    background: {fundo}; color: {texto}; border: 2px solid {borda}; border-radius: 4px;
    font-family: "Bebas Neue"; font-size: 16px; padding: 4px;
}}
QToolButton:disabled {{ background: #3A4046; color: #7A8288; border-color: #2E343C; }}
"""
_MIC_ESTILOS = {
    "parado": (u"FALAR", "#5A6268", "#FFFFFF", "#2E343C"),
    "gravando": (u"GRAVANDO", "#C62828", "#FFFFFF", "#C62828"),
    "transcrevendo": (u"OUVINDO...", "#00838F", "#FFFFFF", "#00838F"),
}


class AgenteTab(QWidget):
    """Aba do chat. `UserTab` (user_tabs/agente_ia) e' esta classe."""

    def __init__(self, parent=None):
        super(AgenteTab, self).__init__(parent)
        self.setObjectName("AGENTE_IA")
        self._sessao = str(uuid.uuid4())
        self._continuar = False
        self._arquivo = None           # ultimo .ngc salvo pelo agente
        self._salvo_neste_pedido = None
        self._proc = ProcessoAgente(self)
        self._proc.texto.connect(self._ao_texto)
        self._proc.ferramenta.connect(self._ao_ferramenta)
        self._proc.resultado.connect(self._ao_resultado)
        self._proc.terminou.connect(self._ao_terminar)
        self._mic = Microfone(self)
        self._mic.estado.connect(self._ao_estado_mic)
        self._mic.texto.connect(self._ao_texto_mic)
        self._mic.erro.connect(self._ao_erro_mic)
        self._entrada_salvar = None      # operacoes do salvar_programa em andamento
        self._limpou_neste_pedido = False
        self._operacoes_salvas = None    # as do ultimo programa salvo
        self._filtro_ligado = False
        self._shift_gravando = False
        self._enviar_apos_transcrever = False
        self._shift_timer = QTimer(self)
        self._shift_timer.setSingleShot(True)
        self._shift_timer.timeout.connect(self._shift_inicia)
        self._build_ui()
        self._boas_vindas()

    # ── interface ─────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        conversa = QFrame()
        conversa.setObjectName("painelConversa")
        conversa.setStyleSheet(_PAINEL_QSS.format(nome="painelConversa"))
        col = QVBoxLayout(conversa)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(8)
        cab = QHBoxLayout()
        t = QLabel(u"AGENTE IA")
        t.setStyleSheet(_HEAD_QSS)
        espacamento(t, 2.0)
        cab.addWidget(t)
        cab.addStretch(1)
        self._estado = QLabel(u"")
        self._estado.setStyleSheet(_STATUS_QSS)
        cab.addWidget(self._estado)
        col.addLayout(cab)

        self._chat = QTextBrowser()
        self._chat.setOpenExternalLinks(False)
        self._chat.setStyleSheet(_CHAT_QSS)
        col.addWidget(self._chat, 1)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        # microfone: toque para falar, toque para parar; o texto cai na caixa
        self._botao_mic = QToolButton()
        self._botao_mic.setIcon(QIcon(ICONE_MIC))
        self._botao_mic.setIconSize(QSize(44, 44))
        self._botao_mic.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self._botao_mic.setFixedSize(110, 110)
        self._botao_mic.setToolTip(u"Toque para falar e toque de novo para parar")
        self._botao_mic.clicked.connect(self._clique_mic)
        self._ao_estado_mic("parado")
        linha.addWidget(self._botao_mic)
        self._entrada = QPlainTextEdit()
        self._entrada.setStyleSheet(_ENTRADA_QSS)
        self._entrada.setPlaceholderText(
            u"Peça um programa. Ex.: facear Ø50 até Z0 e desbastar externo até Ø38 "
            u"por 40 mm, chanfro 0,5")
        self._entrada.setFixedHeight(110)
        self._entrada.installEventFilter(self)
        linha.addWidget(self._entrada, 1)
        botoes = QVBoxLayout()
        botoes.setSpacing(8)
        self._enviar = _botao(u"ENVIAR", fundo="#2FBF5A", cor="#08130B",
                              borda="#2FBF5A", altura=60, fonte=24)
        self._enviar.clicked.connect(self._ao_enviar)
        self._parar = _botao(u"PARAR", fundo="#C62828", borda="#C62828", altura=42)
        self._parar.clicked.connect(self._proc.parar)
        self._parar.setEnabled(False)
        botoes.addWidget(self._enviar)
        botoes.addWidget(self._parar)
        linha.addLayout(botoes)
        col.addLayout(linha)

        rodape = QHBoxLayout()
        nova = _botao(u"NOVA CONVERSA", altura=44, fonte=16)
        nova.clicked.connect(self._nova_conversa)
        rodape.addWidget(nova)
        rodape.addStretch(1)
        dica = QLabel(u"SEGURE SHIFT PARA FALAR E SOLTE PARA ENVIAR, ENTER envia, SHIFT+ENTER quebra a linha")
        dica.setStyleSheet(_STATUS_QSS)
        rodape.addWidget(dica)
        col.addLayout(rodape)
        root.addWidget(conversa, 1)

        prog = QFrame()
        prog.setObjectName("painelProgramaAgente")
        prog.setStyleSheet(_PAINEL_QSS.format(nome="painelProgramaAgente"))
        col2 = QVBoxLayout(prog)
        col2.setContentsMargins(16, 16, 16, 16)
        col2.setSpacing(8)
        cab2 = QHBoxLayout()
        h = QLabel(u"PROGRAMA")
        h.setStyleSheet(_HEAD_QSS)
        espacamento(h, 2.0)
        cab2.addWidget(h)
        cab2.addStretch(1)
        self._nome = QLabel(u"")
        self._nome.setStyleSheet(_STATUS_QSS)
        cab2.addWidget(self._nome)
        col2.addLayout(cab2)
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(_PREVIEW_QSS)
        self._realce = RealceGcode(self._preview.document())
        col2.addWidget(self._preview, 1)
        self._msg_prog = QLabel(u"")
        self._msg_prog.setWordWrap(True)
        self._msg_prog.setStyleSheet(_STATUS_QSS)
        col2.addWidget(self._msg_prog)
        self._carregar = _botao(u"CARREGAR NO LINUXCNC", fundo="#2FBF5A", cor="#08130B",
                                borda="#2FBF5A", altura=60, fonte=22)
        self._carregar.clicked.connect(lambda: self._carregar_programa(manual=True))
        self._carregar.setEnabled(False)
        col2.addWidget(self._carregar)
        prog.setFixedWidth(470)
        root.addWidget(prog)

    # Na tela do agente o filtro e' da aplicacao inteira (instalado no
    # showEvent, removido no hideEvent): o SHIFT vale com o foco em qualquer
    # widget da aba.
    def showEvent(self, ev):
        super(AgenteTab, self).showEvent(ev)
        app = QApplication.instance()
        if app is not None and not self._filtro_ligado:
            app.installEventFilter(self)
            self._filtro_ligado = True

    def hideEvent(self, ev):
        super(AgenteTab, self).hideEvent(ev)
        app = QApplication.instance()
        if app is not None and self._filtro_ligado:
            app.removeEventFilter(self)
            self._filtro_ligado = False
        self._shift_timer.stop()
        if self._shift_gravando:
            self._shift_gravando = False
            self._mic.cancelar()

    def eventFilter(self, obj, ev):
        tipo = ev.type()
        if tipo in (QEvent.KeyPress, QEvent.KeyRelease) and self.isVisible():
            self._tecla_shift(tipo, ev)
        # ENTER envia; SHIFT+ENTER quebra a linha
        if obj is self._entrada and tipo == QEvent.KeyPress \
                and ev.key() in (Qt.Key_Return, Qt.Key_Enter) \
                and not (ev.modifiers() & Qt.ShiftModifier):
            self._ao_enviar()
            return True
        return super(AgenteTab, self).eventFilter(obj, ev)

    # ── SHIFT segurado = falar; soltar = parar e enviar ───────────────────
    # O SHIFT tambem serve para maiuscula e SHIFT+ENTER: so' grava com o
    # SHIFT sozinho por SHIFT_ESPERA_MS. Outra tecla junto descarta a
    # gravacao e segue normal. (O filtro da aplicacao ve o mesmo evento mais
    # de uma vez enquanto ele sobe pelos pais; tudo aqui e' idempotente.)
    SHIFT_ESPERA_MS = 350

    def _tecla_shift(self, tipo, ev):
        if ev.key() == Qt.Key_Shift:
            if ev.isAutoRepeat():
                return
            if tipo == QEvent.KeyPress:
                if not self._mic.gravando() and not self._shift_gravando:
                    self._shift_timer.start(self.SHIFT_ESPERA_MS)
            else:
                self._shift_timer.stop()
                if self._shift_gravando:
                    self._shift_gravando = False
                    self._enviar_apos_transcrever = True
                    self._mic.parar()
        elif tipo == QEvent.KeyPress:
            self._shift_timer.stop()
            if self._shift_gravando:          # era maiuscula / SHIFT+ENTER
                self._shift_gravando = False
                self._mic.cancelar()

    def _shift_inicia(self):
        if not self.isVisible() or self._mic.gravando():
            return
        self._mic.gravar()
        if self._mic.gravando():
            self._shift_gravando = True
            self._estado.setText(u"GRAVANDO: FALE E SOLTE O SHIFT PARA ENVIAR")

    def _clique_mic(self):
        # pelo botao o texto vai para a caixa, para conferir
        self._enviar_apos_transcrever = False
        self._mic.alternar()

    # ── microfone ─────────────────────────────────────────────────────────
    def _ao_estado_mic(self, estado):
        rotulo, fundo, texto, borda = _MIC_ESTILOS.get(estado, _MIC_ESTILOS["parado"])
        self._botao_mic.setText(rotulo)
        self._botao_mic.setStyleSheet(_MIC_QSS.format(fundo=fundo, texto=texto, borda=borda))
        self._botao_mic.setEnabled(estado != "transcrevendo")
        if hasattr(self, "_estado"):
            if estado == "gravando":
                self._estado.setText(u"GRAVANDO: FALE E TOQUE NO MICROFONE PARA PARAR")
            elif estado == "transcrevendo":
                self._estado.setText(u"TRANSCREVENDO...")
            elif not self._proc.rodando():
                self._estado.setText(u"PRONTO")

    def _ao_texto_mic(self, texto):
        atual = self._entrada.toPlainText().strip()
        self._entrada.setPlainText((atual + " " + texto).strip() if atual else texto)
        cursor = self._entrada.textCursor()
        cursor.movePosition(cursor.End)
        self._entrada.setTextCursor(cursor)
        self._entrada.setFocus()
        if self._enviar_apos_transcrever:       # veio do SHIFT: envia direto
            self._enviar_apos_transcrever = False
            if self._proc.rodando():
                self._estado.setText(u"O AGENTE AINDA ESTÁ RESPONDENDO: ENVIE DEPOIS")
            else:
                self._ao_enviar()
            return
        self._estado.setText(u"CONFIRA O TEXTO E TOQUE ENVIAR")

    def _ao_erro_mic(self, mensagem):
        self._enviar_apos_transcrever = False
        self._passo(mensagem)

    # ── conversa ──────────────────────────────────────────────────────────
    def _bloco(self, quem, cor, corpo_html):
        self._chat.append(
            u'<p style="margin-top:10px;"><span style="color:{};'
            u' font-weight:bold;">{}</span><br>{}</p>'.format(cor, quem, corpo_html))
        self._chat.verticalScrollBar().setValue(self._chat.verticalScrollBar().maximum())

    def _passo(self, texto):
        self._chat.append(u'<p style="color:#8A939B; font-size:13px;">&#9656; {}</p>'
                          .format(html.escape(texto)))

    def _boas_vindas(self):
        self._bloco(u"AGENTE", "#3DDC84", md_para_html(
            u"Olá! Me diga a peça e as operações, por exemplo:\n"
            u"- facear Ø50 de Z3 até Z0 com chanfro 0,5\n"
            u"- desbaste externo de Ø50 para Ø38 até Z-40\n"
            u"- furar Ø10 até Z-25 em aço 1045\n"
            u"- rosca M12x1,75 externa até Z-20\n"
            u"Eu monto pelo gerador do GERAR PGM, valido no LinuxCNC, salvo e carrego "
            u"o programa. O ciclo continua só no botão da máquina."))
        self._estado.setText(u"PRONTO")

    def _nova_conversa(self):
        if self._proc.rodando():
            return
        self._sessao = str(uuid.uuid4())
        self._continuar = False
        self._chat.clear()
        self._boas_vindas()

    def _ao_enviar(self):
        texto = self._entrada.toPlainText().strip()
        if not texto or self._proc.rodando():
            return
        executavel = achar_claude()
        if executavel is None:
            self._bloco(u"AGENTE", "#C62828", html.escape(
                u"O Claude Code não está instalado neste computador (comando `claude`)."))
            return
        try:
            with open(PROMPT, encoding="utf-8") as f:
                prompt_sistema = f.read()
        except OSError:
            prompt_sistema = ""
        self._entrada.clear()
        self._bloco(u"VOCÊ", "#5FB3BB", html.escape(texto).replace("\n", "<br>"))
        self._salvo_neste_pedido = None
        self._operacoes_salvas = None
        self._limpou_neste_pedido = False
        self._ocupado(True)
        self._proc.iniciar(executavel,
                           argumentos(self._sessao, self._continuar, prompt_sistema,
                                      os.environ.get("AGENTE_MODELO")),
                           texto)

    def _ocupado(self, sim):
        self._enviar.setEnabled(not sim)
        self._parar.setEnabled(sim)
        self._estado.setText(u"PENSANDO..." if sim else u"PRONTO")

    _PASSOS = {
        "listar_operacoes": u"consultando as operações do gerador",
        "buscar_rosca": u"procurando a rosca na tabela",
        "sugerir_furacao": u"consultando a tabela de furação",
        "gerar_programa": u"montando o programa",
        "salvar_programa": u"validando e salvando o programa",
    }

    def _ao_texto(self, texto):
        self._bloco(u"AGENTE", "#3DDC84", md_para_html(texto))

    def _ao_ferramenta(self, nome, args):
        curto = nome.split("__")[-1]
        if curto == "salvar_programa":
            self._entrada_salvar = args          # operacoes do salvar em andamento
        self._passo(self._PASSOS.get(curto, curto))
        if curto in ("gerar_programa", "salvar_programa") and not self._limpou_neste_pedido:
            self._limpou_neste_pedido = True
            self._limpar_programa_carregado()

    def _ao_resultado(self, nome, texto, erro):
        curto = nome.split("__")[-1]
        if erro:
            self._passo(u"{}: {}".format(curto, texto.splitlines()[0] if texto else u"erro"))
            return
        if nome == FERRAMENTA_SALVAR or curto == "salvar_programa":
            for l in texto.splitlines():
                if l.startswith(MARCA_ARQUIVO):
                    self._salvo_neste_pedido = l[len(MARCA_ARQUIVO):].strip()
                    self._operacoes_salvas = self._entrada_salvar

    # ── valores para a aba GERAR PGM (o operador assume de la) ────────────
    @staticmethod
    def _aba_gerar_pgm():
        for w in QApplication.allWidgets():
            try:
                if w.objectName() == "GERAR_PGM" and hasattr(w, "receber_do_agente"):
                    return w
            except RuntimeError:
                continue
        return None

    def _enviar_para_gerar_pgm(self, entrada):
        """Mesmos params do servidor (ferramentas.preparar) nos formularios da
        aba GERAR PGM: la' o programa sai igual ao do agente."""
        aba = self._aba_gerar_pgm()
        if aba is None or not entrada:
            return
        try:
            from torno_cam.agente.ferramentas import preparar
            ops = [preparar(o["tipo"], o.get("parametros") or {})
                   for o in entrada.get("operacoes") or []]
            aba.receber_do_agente(ops)
        except Exception as e:
            self._passo(u"não consegui passar os valores para a aba GERAR PGM: {}".format(e))
            return
        self._passo(u"valores passados para a aba GERAR PGM (para assumir de lá)")

    def _ao_terminar(self, ok, mensagem):
        self._ocupado(False)
        if ok:
            self._continuar = True       # a sessao existe: as proximas retomam
        else:
            baixo = mensagem.lower()
            if not self._continuar or "session" in baixo or "conversation" in baixo:
                # a sessao pode nem ter sido criada: a proxima mensagem abre outra
                self._sessao = str(uuid.uuid4())
                self._continuar = False
            if "authenticate" in baixo or "login" in baixo:
                mensagem = (u"O Claude Code não está logado neste computador. "
                            u"Num terminal, rode `claude` e use /login.")
            self._bloco(u"AGENTE", "#C62828", md_para_html(mensagem))
        if self._salvo_neste_pedido:
            self._mostrar_programa(self._salvo_neste_pedido)
            self._carregar_programa(manual=False)
            self._enviar_para_gerar_pgm(self._operacoes_salvas)

    # ── programa ──────────────────────────────────────────────────────────
    def _mostrar_programa(self, caminho):
        self._arquivo = caminho
        try:
            with open(caminho, encoding="utf-8") as f:
                self._preview.setPlainText(f.read())
        except OSError as e:
            self._msg_prog.setText(u"Não consegui ler {}: {}".format(caminho, e))
            return
        self._nome.setText(os.path.basename(caminho).upper())
        self._carregar.setEnabled(True)

    def _maquina_parada(self):
        """True se o interpretador esta parado (nao carrega com programa
        rodando ou em pausa)."""
        try:
            import linuxcnc
            from qtpyvcp.plugins import getPlugin
            status = getPlugin("status")
            return status.interp_state.value == linuxcnc.INTERP_IDLE
        except Exception:
            return True

    def _limpar_programa_carregado(self):
        """Pedido do Edson: quando o agente vai gerar ou modificar um programa,
        primeiro descarrega o que esta no LinuxCNC (program_actions.clear, o
        mesmo "novo programa" da tela) e limpa o painel PROGRAMA. Assim a versao
        velha nao fica carregada enquanto o agente trabalha. Com a maquina
        executando nao mexe."""
        self._arquivo = None
        self._preview.setPlainText(u"")
        self._nome.setText(u"")
        self._carregar.setEnabled(False)
        if program_actions is None:
            return
        if not self._maquina_parada():
            self._passo(u"a máquina está executando: o programa carregado não foi limpo")
            return
        try:
            program_actions.clear()
        except Exception as e:
            self._passo(u"não consegui limpar o programa carregado: {}".format(e))
            return
        self._msg_prog.setText(u"Programa anterior descarregado; aguardando o novo.")
        self._passo(u"programa anterior descarregado do LinuxCNC")

    def _carregar_programa(self, manual):
        if not self._arquivo:
            return
        if program_actions is None:
            self._msg_prog.setText(u"Salvo em {} (fora do LinuxCNC).".format(self._arquivo))
            return
        if not self._maquina_parada():
            self._msg_prog.setText(u"Programa salvo. A máquina está executando: "
                                   u"carregue depois em CARREGAR NO LINUXCNC.")
            return
        try:
            program_actions.load(self._arquivo)
        except Exception as e:
            self._msg_prog.setText(u"Salvo, mas falhou ao carregar: {}".format(e))
            return
        self._msg_prog.setText(u"Carregado no LinuxCNC: {}".format(os.path.basename(self._arquivo)))
        if not manual:
            self._passo(u"programa carregado no LinuxCNC (o ciclo é no botão da máquina)")


UserTab = AgenteTab
