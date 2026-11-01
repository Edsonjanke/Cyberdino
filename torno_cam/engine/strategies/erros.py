# -*- coding: utf-8 -*-
"""Erro de geracao (mensagem em PT-BR que a UI mostra na linha de status).

Fica num modulo proprio para as estrategias poderem levantar o erro sem
importar o pacote `strategies` (que importa as estrategias)."""


class EngineError(Exception):
    """Erro de geracao com mensagem em PT-BR para exibir na UI."""
