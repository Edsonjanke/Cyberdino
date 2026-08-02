"""Port FIEL de controllers/linuxcnc/LinuxCNCPost.ts.

Este porte reproduz o TS byte-a-byte, INCLUSIVE as emissoes que o LinuxCNC
2.9.7 rejeita nos ciclos fixos (G32/G75/G71 com palavras invalidas/G76 com Q
em decimos de grau). Serve so de alvo de paridade. A UI usa LinuxCNCDinoPost,
que corrige esses casos. Modos linha-a-linha (manuais) sao validos."""

from .base import PostProcessor
from .format_utils import fmt, word, gline
from ..jsutil import js_num


class LinuxCNCPost(PostProcessor):
    name = "LinuxCNC Lathe"
    controllerType = "linuxcnc"
    fileExtension = ".ngc"
    dialect = "linuxcnc"

    def format_program_header(self, c):
        return [
            "({})".format(c.title),
            "G20" if c.unitSystem == "imperial" else "G21",
            "G18 G40 G80 {}".format("G94" if c.feedMode == "MIN" else "G95"),
            "G7  (DIAMETER MODE)",
        ]

    def format_program_footer(self):
        return ["M2", "%"]

    def format_tool_call(self, t):
        s = "T{} M6 G43 H{}".format(str(t.toolNumber).zfill(2), js_num(t.toolOffset))
        if t.description:
            s += " ({})".format(t.description)
        return s

    def format_work_offset(self, w):
        return w.offset

    def format_spindle_on(self, s):
        m = "M3" if s.dir == "CW" else "M4"
        if s.cssMode:
            max_rpm = s.maxRPM if s.maxRPM is not None else 5000
            sfm = s.sfm if s.sfm is not None else 0
            return "G96 D{} S{} {}".format(js_num(max_rpm), js_num(sfm), m)
        rpm = s.rpm if s.rpm is not None else 0
        return "G97 S{} {}".format(js_num(rpm), m)

    def format_spindle_off(self):
        return "M5"

    def format_spindle_speed(self, s):
        if s.cssMode:
            val = s.sfm if s.sfm is not None else s.rpm
            return "G96 S{}".format(js_num(val))
        return "G97 S{}".format(js_num(s.rpm))

    def format_rapid(self, m):
        return gline("G0", word("X", m.x), word("Z", m.z))

    def format_linear(self, m):
        return gline("G1", word("X", m.x), word("Z", m.z), self.modal_feed(m.feed))

    def format_arc(self, m):
        return gline("G2" if m.dir == "CW" else "G3",
                     word("X", m.x), word("Z", m.z),
                     word("I", m.i), word("K", m.k), self.modal_feed(m.feed))

    def format_coolant_on(self, coolant_type):
        return "M7" if coolant_type == "MIST" else "M8"

    def format_coolant_off(self):
        return "M9"

    def format_dwell(self, seconds):
        return "G4 P{}".format(js_num(seconds))

    def format_cycle_call(self, cycle):
        return gline(cycle.cycleCode, word("X", cycle.x), word("Z", cycle.z),
                     word("R", cycle.r), word("F", cycle.f),
                     word("Q", cycle.q), word("P", cycle.p))

    def format_comment(self, text):
        return "({})".format(text)

    def format_thread_feed(self, node):
        return gline("G32", word("X", node.x), word("Z", node.z),
                     word("F", node.pitch))

    def format_canned_rough_cycle(self, node):
        lines = []
        SUB_NUM = 100
        lines.append("G18 G40")

        profile = node.profile
        last_move = profile[-1] if profile else None
        first_move = profile[0] if profile else None
        final_x = (last_move.x if last_move is not None and last_move.x is not None
                   else (first_move.x if first_move is not None else None))
        final_z = (last_move.z if last_move is not None and last_move.z is not None
                   else (first_move.z if first_move is not None else None))

        d_val = node.finishStockX / 2 if node.finishStockX is not None else 0
        lines.append(gline(
            "G71",
            "Q{}".format(SUB_NUM),
            word("X", final_x),
            word("Z", final_z),
            word("D", d_val),
            word("I", node.depthOfCut),
            word("R", node.retract),
            word("F", node.roughFeed),
        ))

        if node.generateFinish:
            lines.append(gline("G70", "Q{}".format(SUB_NUM)))

        lines.append("")
        lines.append("O{} sub".format(SUB_NUM))

        for i, move in enumerate(profile):
            if move.type == "LINEAR":
                g_code = "G0" if i == 0 else "G1"
                line = gline(g_code, word("X", move.x), word("Z", move.z),
                             self.modal_feed(move.feed) if i > 0 else "")
            else:
                g_code = "G2" if move.dir == "CW" else "G3"
                line = gline(g_code, word("X", move.x), word("Z", move.z),
                             word("I", move.i), word("K", move.k),
                             self.modal_feed(move.feed))
            lines.append("  " + line)

        lines.append("O{} endsub".format(SUB_NUM))
        return "\n".join(lines)

    def format_canned_groove_cycle(self, node):
        from ..jsutil import js_round
        p_microns = js_round(node.peckX * 1000)
        q_microns = js_round(node.stepZ * 1000)
        line1 = gline("G75", word("R", node.retract))
        line2 = gline("G75", word("X", node.finalX), word("Z", node.finalZ),
                      "P{}".format(js_num(p_microns)), "Q{}".format(js_num(q_microns)),
                      word("F", node.feed))
        return line1 + "\n" + line2

    def format_canned_thread_cycle(self, node):
        thread_peak_offset = -node.threadDepth
        return gline(
            "G76",
            word("P", node.pitch),
            word("Z", node.finalZ),
            word("I", thread_peak_offset),
            word("J", node.firstCutDepth),
            word("K", node.threadDepth),
            word("Q", node.threadAngle * 10),
            word("H", node.springPasses),
            "L0",
        )
