"""IR ToolpathNode + ToolpathBuilder — port de toolpath/ToolpathNode.ts e
toolpath/ToolpathBuilder.ts.

Cada no e um dataclass com um campo `type` (string) usado no dispatch do
pos-processador. Coordenadas opcionais ausentes = None (equivale a
`undefined` no TS: a palavra G-code correspondente e omitida)."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ─── Primitivas de movimento ────────────────────────────────────────────────

@dataclass
class Rapid:
    x: Optional[float] = None
    z: Optional[float] = None
    y: Optional[float] = None
    type: str = "RAPID"


@dataclass
class Linear:
    feed: float = 0.0
    x: Optional[float] = None
    z: Optional[float] = None
    y: Optional[float] = None
    type: str = "LINEAR"


@dataclass
class Arc:
    x: float = 0.0
    z: float = 0.0
    i: float = 0.0
    k: float = 0.0
    feed: float = 0.0
    dir: str = "CW"
    type: str = "ARC"


# ─── Estado da maquina ──────────────────────────────────────────────────────

@dataclass
class SpindleOn:
    cssMode: bool = False
    dir: str = "CW"
    rpm: Optional[float] = None
    sfm: Optional[float] = None
    maxRPM: Optional[float] = None
    type: str = "SPINDLE_ON"


@dataclass
class SpindleOff:
    type: str = "SPINDLE_OFF"


@dataclass
class SpindleSpeed:
    rpm: float = 0.0
    cssMode: bool = False
    sfm: Optional[float] = None
    type: str = "SPINDLE_SPEED"


@dataclass
class CoolantOn:
    coolantType: str = "FLOOD"
    type: str = "COOLANT_ON"


@dataclass
class CoolantOff:
    type: str = "COOLANT_OFF"


@dataclass
class Dwell:
    seconds: float = 0.0
    type: str = "DWELL"


@dataclass
class Cycle:
    cycleCode: str = ""
    z: float = 0.0
    r: float = 0.0
    f: float = 0.0
    x: Optional[float] = None
    q: Optional[float] = None
    p: Optional[float] = None
    k: Optional[float] = None
    extra: Optional[Dict[str, float]] = None
    type: str = "CYCLE"


@dataclass
class ThreadFeed:
    z: float = 0.0
    pitch: float = 0.0
    x: Optional[float] = None
    type: str = "THREAD_FEED"


@dataclass
class Comment:
    text: str = ""
    type: str = "COMMENT"


@dataclass
class ToolCall:
    toolNumber: int = 1
    toolOffset: int = 1
    description: str = ""
    type: str = "TOOL_CALL"


@dataclass
class WorkOffset:
    offset: str = "G54"
    type: str = "WORK_OFFSET"


# ─── Ciclos fixos (usados nas fases posteriores / paridade) ──────────────────

@dataclass
class CannedRoughCycle:
    depthOfCut: float = 0.0
    retract: float = 0.0
    finishStockX: float = 0.0
    finishStockZ: float = 0.0
    roughFeed: float = 0.0
    finishFeed: float = 0.0
    profile: List[object] = field(default_factory=list)
    generateFinish: bool = False
    cycleCode: Optional[str] = None
    type: str = "CANNED_ROUGH_CYCLE"


@dataclass
class CannedGrooveCycle:
    retract: float = 0.0
    finalX: float = 0.0
    finalZ: float = 0.0
    peckX: float = 0.0
    stepZ: float = 0.0
    feed: float = 0.0
    type: str = "CANNED_GROOVE_CYCLE"


@dataclass
class CannedThreadCycle:
    finishPasses: float = 0.0
    springPasses: float = 0.0
    threadAngle: float = 0.0
    minCutDepth: float = 0.0
    finishAllowance: float = 0.0
    finalX: float = 0.0
    finalZ: float = 0.0
    threadDepth: float = 0.0
    firstCutDepth: float = 0.0
    pitch: float = 0.0
    # Deslocamento do pico da rosca em relacao a linha de referencia (raio).
    # Negativo = externa, positivo = interna. So o dialeto do LinuxCNC usa.
    peakOffset: float = 0.0
    type: str = "CANNED_THREAD_CYCLE"


class ToolpathBuilder:
    """Builder fluente que espelha ToolpathBuilder.ts."""

    def __init__(self):
        self._nodes = []

    def comment(self, text):
        self._nodes.append(Comment(text=text))
        return self

    def workOffset(self, offset):
        self._nodes.append(WorkOffset(offset=offset))
        return self

    def toolCall(self, tool_number, tool_offset, description=""):
        self._nodes.append(ToolCall(toolNumber=tool_number, toolOffset=tool_offset,
                                    description=description))
        return self

    def spindleOn(self, cssMode, dir, rpm=None, sfm=None, maxRPM=None):
        self._nodes.append(SpindleOn(cssMode=cssMode, dir=dir, rpm=rpm, sfm=sfm,
                                     maxRPM=maxRPM))
        return self

    def spindleOff(self):
        self._nodes.append(SpindleOff())
        return self

    def spindleSpeed(self, rpm, sfm=None, cssMode=False):
        self._nodes.append(SpindleSpeed(rpm=rpm, sfm=sfm, cssMode=cssMode))
        return self

    def coolantOn(self, coolant_type="FLOOD"):
        self._nodes.append(CoolantOn(coolantType=coolant_type))
        return self

    def coolantOff(self):
        self._nodes.append(CoolantOff())
        return self

    def rapid(self, x=None, z=None, y=None):
        self._nodes.append(Rapid(x=x, z=z, y=y))
        return self

    def linear(self, feed, x=None, z=None, y=None):
        self._nodes.append(Linear(feed=feed, x=x, z=z, y=y))
        return self

    def arc(self, x, z, i, k, feed, dir):
        self._nodes.append(Arc(x=x, z=z, i=i, k=k, feed=feed, dir=dir))
        return self

    def dwell(self, seconds):
        self._nodes.append(Dwell(seconds=seconds))
        return self

    def cycle(self, cycleCode, z, r, f, x=None, q=None, p=None, k=None, extra=None):
        self._nodes.append(Cycle(cycleCode=cycleCode, z=z, r=r, f=f, x=x, q=q,
                                 p=p, k=k, extra=extra))
        return self

    def threadFeed(self, z, pitch, x=None):
        self._nodes.append(ThreadFeed(z=z, pitch=pitch, x=x))
        return self

    def cannedRoughCycle(self, **kw):
        self._nodes.append(CannedRoughCycle(**kw))
        return self

    def cannedGrooveCycle(self, **kw):
        self._nodes.append(CannedGrooveCycle(**kw))
        return self

    def cannedThreadCycle(self, **kw):
        self._nodes.append(CannedThreadCycle(**kw))
        return self

    def build(self):
        return list(self._nodes)
