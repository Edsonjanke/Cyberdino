"""Port de packages/postprocessor/src/PostProcessor.ts (Template Method).

NAO sobrescrever generate() nas subclasses — so os metodos format*."""

import re

from .format_utils import word

_G8x = re.compile(r"^G8[1-9]$")


class PostProcessor:
    name = ""
    controllerType = ""
    fileExtension = ""
    dialect = ""

    def __init__(self):
        self._last_feed = None

    # ── Feed modal ───────────────────────────────────────────────────────────
    def modal_feed(self, feed):
        if feed is None:
            return ""
        if feed == self._last_feed:
            return ""
        self._last_feed = feed
        return word("F", feed)

    def reset_modal_feed(self):
        self._last_feed = None

    # ── Cancelamento de ciclo (G80 por padrao) ───────────────────────────────
    def format_cycle_cancel(self):
        return "G80"

    # ── Ciclos fixos: por padrao nao suportado ───────────────────────────────
    def format_canned_rough_cycle(self, node):
        raise NotImplementedError(
            "Ciclo de desbaste automatico nao suportado por {}".format(self.name))

    def format_canned_groove_cycle(self, node):
        raise NotImplementedError(
            "Ciclo de canal automatico nao suportado por {}".format(self.name))

    def format_canned_thread_cycle(self, node):
        raise NotImplementedError(
            "Ciclo de rosca automatico nao suportado por {}".format(self.name))

    # ── Template method — NAO sobrescrever ───────────────────────────────────
    def generate(self, config, operations):
        lines = []
        self.reset_modal_feed()

        lines.extend(self.format_program_header(config))

        for op in operations:
            lines.append(self.format_comment("--- {} ---".format(op.title)))
            lines.append(self.format_tool_call(op.tool_call))
            for node in op.nodes:
                line = self._render_node(node)
                if line:
                    lines.append(line)

        lines.extend(self.format_program_footer())
        return "\n".join(l for l in lines if l)

    def _render_node(self, node):
        t = node.type
        if t == "RAPID":
            return self.format_rapid(node)
        if t == "LINEAR":
            return self.format_linear(node)
        if t == "ARC":
            return self.format_arc(node)
        if t == "SPINDLE_ON":
            return self.format_spindle_on(node)
        if t == "SPINDLE_OFF":
            return self.format_spindle_off()
        if t == "SPINDLE_SPEED":
            return self.format_spindle_speed(node)
        if t == "COOLANT_ON":
            return self.format_coolant_on(node.coolantType)
        if t == "COOLANT_OFF":
            return self.format_coolant_off()
        if t == "DWELL":
            return self.format_dwell(node.seconds)
        if t == "CYCLE":
            cycle_line = self.format_cycle_call(node)
            if _G8x.match(node.cycleCode or ""):
                return cycle_line + "\n" + self.format_cycle_cancel()
            return cycle_line
        if t == "COMMENT":
            return self.format_comment(node.text)
        if t == "TOOL_CALL":
            return self.format_tool_call(node)
        if t == "WORK_OFFSET":
            return self.format_work_offset(node)
        if t == "THREAD_FEED":
            return self.format_thread_feed(node)
        if t == "CANNED_ROUGH_CYCLE":
            self.reset_modal_feed()
            return self.format_canned_rough_cycle(node)
        if t == "CANNED_GROOVE_CYCLE":
            self.reset_modal_feed()
            return self.format_canned_groove_cycle(node)
        if t == "CANNED_THREAD_CYCLE":
            self.reset_modal_feed()
            return self.format_canned_thread_cycle(node)
        return ""
