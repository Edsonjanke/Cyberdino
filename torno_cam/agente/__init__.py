"""Agente de IA do torno: servidor MCP com as ferramentas do gerador.

O Claude Code (`claude -p`, chamado pela aba AGENTE IA) conversa com o
servidor por stdio. As ferramentas so' montam programas pelo mesmo motor da
aba GERAR PGM, validam no interpretador do LinuxCNC e salvam o .ngc; quem
carrega o programa na maquina e' a aba. Puro Python, sem Qt.
"""
