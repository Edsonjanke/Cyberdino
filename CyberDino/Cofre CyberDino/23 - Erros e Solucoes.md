# Erros e Solucoes

## Placa Chinesa Mesa 7i92

### Pinos P2 (DB25) nao funcionam como entrada
**Problema:** Optoacopladores no P2 sao unidirecionais - so saida.
**Solucao:** Usar DB15 (P1) ou pontos soldados para entradas.

### Conectores mortos na placa
**Problema:** Pontos soldados para GPIOs podem NAO estar conectados ao FPGA.
**Solucao:** Sempre testar GPIO com `halcmd setp/getp` antes de confiar.

## ProbeBasic / QtPyVCP

### Crash ao importar linuxcnc
**Problema:** ProbeBasic crashava ao importar modulo linuxcnc fora do ambiente CNC.
**Solucao:** Import lazy do linuxcnc + deteccao de processos ativos.

### POSTGUI_HALFILE so carrega 1
**Problema:** QtPyVCP usa `ini.find()` (retorna primeiro), nao `findall()`.
**Solucao:** Colocar tudo em um unico `probe_basic_postgui_fix.hal`.

### Pins HAL usam hifen, nao underscore
**Problema:** Widget name `mpg_indicator` no Qt gera pin `mpg-indicator` no HAL.
**Solucao:** Sempre usar hifen nos nomes de sinal HAL: `qtpyvcp.mpg-indicator.in`

### HalButton permite click mesmo com pin controlado
**Problema:** HalButton padrao aceita click do mouse, sobreescrevendo o estado do pin.
**Solucao:** Criar widget custom `ReadOnlyAction` que bloqueia mouse.

## PLC AMS32 / Comunicacao

### CLP nao funciona / sem resposta ao LinuxCNC
**Sintoma:** `ams32_hal.py` em loop de reconexao, `/tmp/ams32_hal.log` mostra `could not open port /dev/ttyAMS32`, coolant/jog/servo-fault mortos.

**Causa comum:** cabo USB do CH340 mudou de porta fisica. A regra udev em `/etc/udev/rules.d/99-ams32.rules` esta ancorada em `ID_PATH` hardcoded (ex.: `pci-0000:00:1d.0-usb-0:X.Y:1.0`). Se o cabo sair da porta, o symlink `/dev/ttyAMS32` nao e criado.

**Diagnostico:**
```bash
ls -la /dev/ttyAMS32                               # symlink existe?
tail /tmp/ams32_hal.log                            # erros de conexao?
udevadm info -q all -n /dev/ttyUSB0 | grep ID_PATH # porta atual
cat /etc/udev/rules.d/99-ams32.rules               # porta esperada
```

**Fix (atualizar a regra pra porta atual):**
```bash
sudo sed -i 's|usb-0:OLD:1.0|usb-0:NEW:1.0|' /etc/udev/rules.d/99-ams32.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty
ls -la /dev/ttyAMS32   # deve mostrar -> ttyUSB0
```

**Teste rapido (sem mexer em udev) — verificar se e o CLP mesmo:**
```python
from pymodbus.client import ModbusSerialClient
c = ModbusSerialClient(port="/dev/ttyUSB0", framer="ascii",
                      baudrate=9600, bytesize=7, parity="E", stopbits=1,
                      timeout=0.5)
c.connect()
r = c.read_holding_registers(address=0x1000, count=1, device_id=1)
print(r.registers if not r.isError() else "sem resposta")
```

**Historico:**
- 2026-04-17 (proj): regra criada pra porta `1.5`
- 2026-04-24: cabo foi pra porta `1.2` (porta `1.5` parece nao existir fisicamente nessa maquina). Regra atualizada para `1.2`.

## CFW-07

### Saida analogica da placa nao chega em 10V
**Problema:** PWM0 a 100% gera ~6.7V na saida analogica (RC filter da BOB). Inversor recebe 40Hz em vez de 60Hz.
**Solucao:** P234 (Ganho AI1) = 1.50. Compensa: 6.7V x 1.5 = 10V equivalente = 60Hz = 1700 RPM.


### Motor nao gira mesmo com referencia
**Verificar:**
1. DI1 (borne 09) esta em 0V? (Habilita Geral)
2. DI4 (borne 12) esta em 0V? (Habilita Rampa)
3. P220 = 1? (modo REMOTO)
4. Display mostra "rdy"?
5. AI1 (borne 02) tem tensao proporcional?

### Display mostra erro
Ver [[20 - Parametros CFW-07#Mensagens de Erro]]

## Rede

### IPv4 morto parece bloqueio do GitHub
**Problema:** "parte da internet funciona, o GitHub nao". O IPv4 estava com
endereco fixo numa faixa que nao existe mais (a rede mudou de 192.168.0.x
para 192.168.1.x em 2026-08-01). O IPv6 continuava bom, entao tudo que tem
AAAA passava — e o github.com, que e' **so IPv4**, nao.
**Cuidado:** `ping` mente nessa rede (ICMP bloqueado). Comparar `curl -4`
com `curl -6`. ARP FAILED pro gateway confirma.
**Solucao:** voltar a interface pra DHCP.
```bash
nmcli con mod "Conexao cabeada 1" ipv4.method auto ipv4.addresses "" ipv4.gateway ""
```
PC do torno hoje: **192.168.1.32** por DHCP; roteador 192.168.1.1.

## HAL

### Mudanca no custom.hal nao da' pra testar no sim
O sim usa `custom_sim.hal`, que **bypassa** o `custom.hal` inteiro (Mesa,
botoes, chaves, fim de curso). Entao mexer na logica dos botoes e abrir o
sim nao prova nada.

Dois jeitos que funcionam, sem a maquina:

**1. Bancada no `halrun`.** Repetir o circuito num arquivo so', com as
entradas que viriam do 7i92 e do halui como sinais soltos, e andar passo a
passo com `sets` / `gets`:

```bash
halrun -U                       # o sim segura o realtime; derrubar antes
halrun -f bancada.hal
```

Nao existe `sleep` no halcmd — o jeito de deixar a thread rodar entre um
passo e outro e' `loadusr -w sleep 0.08`. E `print` aceita **um** argumento
so'. Foi assim que o [[07 - Botoes de Modo e Refrigerante]] foi conferido
(28 passos) e que o defeito do `toggle2nist` apareceu.

**2. Carregar o custom.hal de verdade, sem os pinos externos.** Gerar uma
copia tirando todo token que comeca com `hm2_7i92.`, `halui.`, `joint.`,
`axis.`, `iocontrol.`, `motion.`, `qtpyvcp.` e rodar no `halrun`. Nao testa
logica, mas pega **nome de pino errado, addf faltando e loadrt
incompleto** — que e' o tipo de erro que impede a maquina de subir.

### Comportamento dos pinos do halui: BORDA, nao nivel
Os pinos de comando (`halui.mode.auto`, `halui.flood.off`, ...) so' agem na
**borda de subida**. Segurar um deles em TRUE nao prende nada: medido no
sim, com `halui.flood.off` preso em TRUE um `flood.on` depois liga a bomba
do mesmo jeito, e com `halui.mode.manual` preso a tela ainda vai pra MDI.
E' o que torna seguro mandar nivel continuo nesses pinos.

### Volante do Z ficou mudo depois de remapear o pino
**Problema:** na reforma do painel (2026-10-16) o volante do Z foi
configurado nos GPIO.028/029 e simplesmente **nao fez nada** — sem erro,
sem aviso, HAL carregando normal. Entrada de GPIO sem fio nao reclama:
fica parada em TRUE pelo pull-up.

**Causa:** o volante do Z sempre esteve no **GPIO.016/026**. O comentario
do `custom.hal` chamava esse par de "encoder FYSETC EC11 de feed
override", como se fosse um botaozinho separado do painel, e a reforma foi
desenhada em cima dessa descricao em vez da fiacao de verdade. O sintoma
que entregou: *"antes ele tava funcionando pra aumentar ou diminuir o
feed"* — era exatamente o que o 016/026 fazia.

**Licao:** comentario de arquivo nao e' fiacao. Para saber onde um botao
ou volante esta ligado, com o LinuxCNC rodando:

```bash
python3 tools/acha_gpio.py        # 15 s; aperte/gire o que quer achar
```

Ele lista so' as entradas que mudaram. Volante aparece como **dois** pinos
com contagem parecida (fases A e B); botao aparece como **um** pino com 2
trocas por aperto.

### `halrun -U` derruba a HAL do LinuxCNC que esta aberto
**Problema (2026-10-16, com a maquina ligada):** para validar o
`custom.hal` num `halrun` e' preciso uma sessao de realtime limpa, e o
`halrun -U` que isso exige **matou a HAL da sessao em andamento**. Os
processos `linuxcncsvr` e `probe_basic_lathe` continuaram na tela, mas
sem HAL nenhuma por tras.

**O que salvou:** o `salva_posicao.py` recebe SIGTERM e gravou a posicao
final normalmente (`motivo: encerramento`) — nada de referencia se perdeu.
Mas nao da' pra contar com isso.

**Solucao:** `tools/valida_hal.sh`, que **recusa rodar** se achar um
`linuxcncsvr` no ar:

```bash
tools/valida_hal.sh custom.hal
```

Ele tambem acusa linha solta (nem comentario nem comando) com o numero da
linha, antes mesmo de tentar carregar.

### `hal.get_value` nao funciona sem criar um componente
Qualquer processo Python que leia pinos precisa de
`hal.component("algumnome").ready()` antes. Sem isso **toda** leitura
levanta `RuntimeError: Cannot call before creating component`.

E' traicoeiro quando se descobre os pinos por tentativa dentro de
try/except: o erro vira "nenhum pino existe", e a ferramenta diz que nao
achou nada em vez de dizer que nao conseguiu entrar na HAL. Foi o que
aconteceu com a primeira versao do `tools/acha_gpio.py` — e o teste com
HAL de mentira nao pegou, porque o dublê nao exigia o componente.
