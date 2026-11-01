# -*- coding: utf-8 -*-
"""Seletor de rosca (artboard "LinuxCNC, seletor de rosca"): os numeros do
painel saem das mesmas regras do gerador e batem com o desenho."""

from torno_cam.engine import roscas as R
from torno_cam_ui.seletor_rosca import diametro, medidas, nome_curto, rotulo_passo


def test_m5_fina_igual_ao_artboard():
    it = R.buscar("M5 x 0.5")
    m = medidas(it)
    assert nome_curto(it) == (u"M5 × 0.5", u"FINA")
    assert round(m["flanco"], 3) == 4.675
    assert round(m["menor_ext"], 3) == 4.387 and round(m["prof_ext"], 3) == 0.307
    assert round(m["menor_int"], 3) == 4.459 and round(m["prof_int"], 3) == 0.271
    assert m["broca"] == 4.5


def test_passo_normal_e_o_primeiro_do_diametro():
    """AO TROCAR O DIAMETRO, O PASSO NORMAL JA VEM MARCADO: o painel marca o
    primeiro item do diametro, entao a tabela tem que trazer o normal antes."""
    grupos = {}
    for it in R.lista(R.TAB_METRICA):
        grupos.setdefault(diametro(it), []).append(it)
    assert len(grupos) == 28
    for nome, itens in grupos.items():
        assert rotulo_passo(itens[0])[1] == u"NORMAL", nome
        assert all(rotulo_passo(i)[1] == u"FINA" for i in itens[1:]), nome


def test_polegada_e_npt_pelos_fios():
    unc = R.buscar('1/2" - 13 UNC')
    assert diametro(unc) == u'1/2"' and nome_curto(unc) == (u'1/2" × 13', u"UNC")
    npt = R.buscar('NPT 1/2" - 14')
    assert nome_curto(npt) == (u'NPT 1/2" × 14', u"CÔNICA")
    m = medidas(npt)
    assert abs(m["prof_ext"] - 0.8 * 25.4 / 14) < 1e-9       # 1.451, como no gerador
