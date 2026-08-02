# 17 - Aba GERAR PGM: Conversational de Torno

Portado do app **EvoCAM** (`Evo-CNC-Guia/`, TypeScript) para dentro do
ProbeBasic como aba nativa Python/Qt. Feito em 2026-08-02. Nao e' webview:
o engine foi reescrito em Python puro e a UI e' Qt.

- Engine: `torno_cam/` (sem Qt, testavel sozinho)
- Interface: `torno_cam_ui/`
- **130 testes** (`python3 -m pytest torno_cam/tests -q`)

## Como a UI funciona (padrao Tormach)

O operador **digita dentro dos retangulos do desenho tecnico**, nao num
formulario ao lado. Cada operacao tem a sua imagem de fundo em
`torno_cam_ui/images/` e uma tabela de retangulos medidos (`FIELDS`) em
coordenadas relativas (0..1), pra escalar com a janela.

Se a imagem for reeditada e as caixas mudarem de lugar, **remedir** com:

```bash
python3 torno_cam_ui/tools/detecta_caixas.py <imagem-bg.png>
```

Ele acha os retangulos brancos e imprime a tabela `FIELDS` pronta.
Procedimento completo e armadilhas: `torno_cam_ui/README-novo-painel.md`.

**Desenhos em PT-BR:** a rosca EXTERNA ja esta traduzida (1819x865, retangulos
remedidos em 2026-08-02). A INTERNA continua em ingles — a versao traduzida que
chegou tinha o campo do X de cima marcado como "INICIO X" quando ali e' o FIM X,
e ainda ganhou uma caixa a mais embaixo ("X START" + "FIM X" empilhados, onde o
desenho so tem um). Digitar no campo errado da a rosca com profundidade errada,
entao ela nao foi instalada.

**Modo imersivo:** ao entrar na aba, a faixa inferior e o painel lateral
somem (`showEvent`/`hideEvent` em `tab.py`) — o desenho ocupa a tela quase
toda, pra acertar os campos com o dedo. Precisa levantar o teto de 680px do
`tabWidget`, senao esconder a faixa nao aumenta nada.

## As 7 operacoes

FACEAR, DESBASTE EXT, DESBASTE INT (basico/avancado), FURAR, CHANFRO/RAIO,
CANAL/CORTE, ROSCA.

## Tabelas de apoio

- **Furacao** (`torno_cam/engine/furacao.py`): brocas de 3 a 30 mm de 0,5 em
  0,5. ACO Vc25 / f=0.018·D / peck 3D; INOX Vc14 / 0.012 / 2D;
  ALUMINIO Vc70 / 0.025 / 4D. Teto de 2360 RPM (a caixa nao passa disso).
- **Roscas** (`torno_cam/engine/roscas.py`): metricas M2 a M50, 97 no total.
  Passo padrao em **verde**, passos finos em **amarelo**, com "Padrao"/"Fina"
  escrito em cinza ao lado. Broca = D - passo (~77% de filete, regra de
  oficina). Titulo do programa sai automatico: "Rosca M8 X 1.25 mm".

## Correcoes de usinagem feitas no porte

O EvoCAM gerava codigo que o LinuxCNC **recusa ou corta errado**. Cada uma
foi verificada rodando o interpretador de verdade (`rs274` com o ini da
maquina), nao no olho. Ficaram atras de flags (`fixArcOvercut`,
`compensarLargura`, `forcePeckCycle`) pra nao quebrar a paridade com o app.

| Problema no app | Efeito na maquina | Correcao |
|---|---|---|
| G83 dentro de G18 | "Y value unspecified", nao roda | G17 antes do ciclo, G18 depois |
| Dwell em milissegundos | pausa 1000x maior | P em segundos |
| P em G81/G83 | ignorado (so G82 pausa) | usa G82 quando ha pausa |
| Arco em modo RAIO nao fechava | LinuxCNC recusa o arco | recalcula o ponto final |
| G76 com I=-prof E K=prof | **rosca com o DOBRO da profundidade** | I = folga do pico, K = filete |
| G76 dentro de G7 | I/J/K lidos como diametro, rosca pela metade | embrulha em G8 e volta pra G7 |
| Sangria ignorava a largura | peca sai curta pela largura da pastilha | corte em -5 com pastilha de 3 = Z-8 |

Q do G76 e' em **graus** (29.5), nao em decimos.

## Coisas da maquina embutidas no post

`torno_cam/engine/post/linuxcnc_dino.py`:

- **G64 P0.01** no cabecalho de todo programa (tolerancia de trajetoria).
  Sem isso o programa herda o modo que a maquina estiver.
- Bloco de rotacao **auto-suficiente** (G96 D S + M3/M4 + refrigeracao numa
  tacada) pra o EXEC. DA LINHA funcionar a partir do acabamento.
- **M4 = rosca direita** nesta maquina (BACK_TOOL_LATHE=1). Aviso fixo no
  painel de rosca. Ver [[16 - Interface v2 Fanuc e Atalhos]].

## Pendente

- **Nada foi cortado de verdade ainda.** Validar na maquina, comecando pelo
  mais sensivel: ciclo de rosca G76 e ciclo de furacao.
- G71 (desbaste) e G75 (canal) nao existem no LinuxCNC 2.9 — os toggles de
  ciclo dessas operacoes estao travados; sai linha a linha.
- Remover o `torno_cam_diag.log` quando nao for mais preciso.
