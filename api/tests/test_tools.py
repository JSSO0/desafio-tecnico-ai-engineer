import sqlite3

import pytest

from app.agent.session import SessionContext
from app.tools import build_tools
from app.tools.catalog import _where

PII_KEYS = {"email", "phone", "cpf", "endereco", "city", "customer_id"}


@pytest.fixture
def ferramentas(conn: sqlite3.Connection):
    sessao = SessionContext()
    return sessao, {tool.name: tool for tool in build_tools(sessao, conn)}


# --- catalogo ---------------------------------------------------------------


def test_violoes_ate_mil_traz_doze_disponiveis(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["buscar_produtos"].invoke({"categoria": "violoes", "preco_max": 1000})

    assert out["total_encontrado"] == 12
    ids = {item["product_id"] for item in out["produtos"]}
    assert not ids & {96, 113}, "esgotado e descontinuado nao podem aparecer"


def test_inclui_indisponiveis_quando_pedido(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["buscar_produtos"].invoke(
        {"categoria": "5", "preco_max": 1000, "somente_disponiveis": False}
    )

    assert out["total_encontrado"] == 14


def test_busca_sem_resultado_orienta_ajuste(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["buscar_produtos"].invoke({"termo": "saxofone"})

    assert out["total_encontrado"] == 0
    assert out["produtos"] == []
    assert out["observacao"]


def test_limite_da_busca_e_limitado_entre_1_e_20(ferramentas) -> None:
    _, tools = ferramentas

    assert tools["buscar_produtos"].invoke({"limite": 0})["retornados"] == 1
    assert tools["buscar_produtos"].invoke({"limite": 99})["retornados"] <= 20


def test_card_de_produto_nao_expoe_pii(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["buscar_produtos"].invoke({"categoria": "violoes"})

    assert out["produtos"]
    for card in out["produtos"]:
        assert not PII_KEYS & card.keys()


def test_detalhe_do_takamine_gd20(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["detalhe_produto"].invoke({"nome_ou_id": "Takamine GD20"})

    assert out["encontrado"] is True
    assert out["preco"] == "R$ 2.199,00"
    assert "promocao" not in out, "a promocao do produto 95 esta inativa"


def test_detalhe_ignora_acento_e_caixa(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["detalhe_produto"].invoke({"nome_ou_id": "takamine gd20"})

    assert out["encontrado"] is True
    assert out["product_id"] == 95


def test_detalhe_por_id_aplica_promocao_ativa(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["detalhe_produto"].invoke({"nome_ou_id": "127"})

    assert out["desconto_percent"] == 10
    assert out["preco_com_desconto"] == "R$ 323,10"


def test_detalhe_inexistente_nao_inventa(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["detalhe_produto"].invoke({"nome_ou_id": "Saxofone Selmer"})

    assert out["encontrado"] is False
    assert "preco" not in out


# --- identificacao e pedidos ------------------------------------------------


def test_identifica_cliente_pelo_telefone(ferramentas) -> None:
    sessao, tools = ferramentas

    out = tools["identificar_cliente"].invoke({"telefone": "(67) 98432-1098"})

    assert out["identificado"] is True
    assert out["primeiro_nome"] == "Pedro"
    assert sessao.customer_id == 3


def test_aceita_telefone_com_codigo_do_pais(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["identificar_cliente"].invoke({"telefone": "5567984321098"})

    assert out["identificado"] is True


def test_telefone_curto_nao_identifica(ferramentas) -> None:
    sessao, tools = ferramentas

    out = tools["identificar_cliente"].invoke({"telefone": "98432"})

    assert out["identificado"] is False
    assert out["motivo"] == "telefone incompleto"
    assert sessao.identified is False


def test_telefone_desconhecido_limpa_a_sessao(ferramentas) -> None:
    sessao, tools = ferramentas
    tools["identificar_cliente"].invoke({"telefone": "(67) 98432-1098"})

    out = tools["identificar_cliente"].invoke({"telefone": "(11) 90000-0000"})

    assert out["identificado"] is False
    assert sessao.customer_id is None


def test_pedido_exige_cliente_identificado(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["consultar_pedido"].invoke({})

    assert out["erro"] == "cliente_nao_identificado"


def test_pedido_de_outro_cliente_nao_e_revelado(ferramentas) -> None:
    _, tools = ferramentas
    tools["identificar_cliente"].invoke({"telefone": "(67) 98432-1098"})  # cliente 3

    out = tools["consultar_pedido"].invoke({"order_id": 6})  # pedido 6 e do cliente 9

    assert out["encontrado"] is False


def test_pedido_inexistente_recebe_a_mesma_resposta_de_pedido_alheio(ferramentas) -> None:
    _, tools = ferramentas
    tools["identificar_cliente"].invoke({"telefone": "(67) 98432-1098"})

    alheio = tools["consultar_pedido"].invoke({"order_id": 6})
    inexistente = tools["consultar_pedido"].invoke({"order_id": 999})

    assert alheio == inexistente, "nao confirmar a existencia de pedido de outro cliente"


def test_lista_pedidos_do_cliente(ferramentas) -> None:
    _, tools = ferramentas
    tools["identificar_cliente"].invoke({"telefone": "(67) 98432-1098"})

    out = tools["consultar_pedido"].invoke({})
    pedidos = {item["pedido"]: item for item in out["pedidos"]}

    assert set(pedidos) == {1, 19}
    assert pedidos[1]["status"] == "entregue"
    assert pedidos[1]["rastreio"] == "BRAB1234567BR"
    assert pedidos[19]["status"] == "cancelado"


def test_total_divergente_e_sinalizado_nao_corrigido(ferramentas) -> None:
    _, tools = ferramentas
    tools["identificar_cliente"].invoke({"telefone": "(67) 98321-6543"})  # cliente 7

    out = tools["consultar_pedido"].invoke({"order_id": 20})
    pedido = out["pedido"]

    assert pedido["total"] == "R$ 1.400,00"
    assert pedido["total_divergente"] is True
    assert "instrucao" in pedido


# --- politicas --------------------------------------------------------------


def test_politica_de_devolucao_com_proveniencia(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["consultar_politicas"].invoke({"pergunta": "me arrependi, posso devolver?"})
    topo = out["trechos"][0]

    assert out["encontrado"] is True
    assert topo["secao"] == "4.1"
    assert topo["citacao"] == "Politica §4.1"
    assert "7 (sete) dias corridos" in topo["texto"]


def test_politica_fora_do_manual_nao_inventa(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["consultar_politicas"].invoke({"pergunta": "receita de bolo de cenoura"})

    assert out["encontrado"] is False
    assert "instrucao" in out


# --- pagamento --------------------------------------------------------------


def test_pix_aplica_cinco_por_cento(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 1000, "forma": "pix"})

    assert out["valor_final"] == "R$ 950,00"


def test_pix_nao_acumula_com_preco_promocional(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke(
        {"valor": 359, "forma": "pix", "preco_ja_promocional": True}
    )

    assert out["desconto_percent"] == 0
    assert out["valor_final"] == "R$ 359,00"


def test_pix_acima_de_dois_mil_avisa_sobre_combinacao(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 2199, "forma": "pix"})

    assert any("2.000" in nota for nota in out["observacoes"])


def test_forma_de_pagamento_desconhecida_e_recusada(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 500, "forma": "cheque"})

    assert out["permitido"] is False
    assert "cheque" not in out["formas_aceitas"]


def test_valor_invalido_e_recusado(ferramentas) -> None:
    _, tools = ferramentas

    assert tools["simular_pagamento"].invoke({"valor": 0, "forma": "pix"})["permitido"] is False


def test_doze_vezes_bloqueado_abaixo_da_parcela_minima(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 849, "forma": "credito", "parcelas": 12})

    assert out["permitido"] is False
    assert "70,75" in out["motivo"]


def test_doze_vezes_permitido_no_limite(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 1200, "forma": "credito", "parcelas": 12})

    assert out["permitido"] is True
    assert out["valor_parcela"] == "R$ 100,00"


def test_parcelas_acima_de_doze_sao_recusadas(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 5000, "forma": "credito", "parcelas": 13})

    assert out["permitido"] is False


def test_seis_vezes_exige_parcela_de_oitenta(ferramentas) -> None:
    _, tools = ferramentas

    bloqueado = tools["simular_pagamento"].invoke(
        {"valor": 400, "forma": "credito", "parcelas": 6}
    )
    liberado = tools["simular_pagamento"].invoke(
        {"valor": 480, "forma": "credito", "parcelas": 6}
    )

    assert bloqueado["permitido"] is False
    assert liberado["permitido"] is True


def test_tres_vezes_exige_compra_minima_de_cinquenta(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 49.9, "forma": "credito", "parcelas": 3})

    assert out["permitido"] is False


def test_debito_nao_parcela(ferramentas) -> None:
    _, tools = ferramentas

    out = tools["simular_pagamento"].invoke({"valor": 500, "forma": "debito", "parcelas": 3})

    assert out["permitido"] is False


# --- montagem da clausula (sem banco) ---------------------------------------


def test_where_vazio_quando_nao_ha_filtro() -> None:
    assert _where(None, None, None, None, False) == ("", [])


def test_where_compoe_clausulas_e_parametros_na_ordem() -> None:
    where, params = _where("violao", "5", 100.0, 1000.0, True)

    assert where.startswith(" WHERE ")
    assert "stock_quantity > 0" in where
    assert params == ["violao", "violao", "5", "5", 100.0, 1000.0]


def test_where_tem_um_parametro_para_cada_marcador() -> None:
    """Regressao: marcador sem parametro (ou o contrario) quebra a consulta em runtime."""
    for filtros in (
        ("violao", None, None, None, True),
        (None, "violoes", None, None, False),
        (None, None, 500.0, 1000.0, True),
        ("aço", "5", 100.0, 2000.0, False),
    ):
        where, params = _where(*filtros)
        assert where.count("?") == len(params)
