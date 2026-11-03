import sqlite3

import pytest

from app.agent.session import SessionContext
from app.tools import build_tools
from app.tools.catalog import CatalogFilter, _where

PII_KEYS = {"email", "phone", "cpf", "endereco", "city", "customer_id"}


@pytest.fixture
def toolset(conn: sqlite3.Connection):
    session = SessionContext()
    return session, {tool.name: tool for tool in build_tools(session, conn)}


# --- catalogo ---------------------------------------------------------------


def test_violoes_ate_mil_traz_doze_disponiveis(toolset) -> None:
    _, tools = toolset

    out = tools["search_products"].invoke({"category": "violoes", "max_price": 1000})

    assert out["total_encontrado"] == 12
    ids = {item["product_id"] for item in out["produtos"]}
    assert not ids & {96, 113}, "esgotado e descontinuado nao podem aparecer"


def test_inclui_indisponiveis_quando_pedido(toolset) -> None:
    _, tools = toolset

    out = tools["search_products"].invoke(
        {"category": "5", "max_price": 1000, "only_available": False}
    )

    assert out["total_encontrado"] == 14


def test_busca_sem_resultado_orienta_ajuste(toolset) -> None:
    _, tools = toolset

    out = tools["search_products"].invoke({"query": "saxofone"})

    assert out["total_encontrado"] == 0
    assert out["produtos"] == []
    assert out["observacao"]


def test_limite_da_busca_e_limitado_entre_1_e_20(toolset) -> None:
    _, tools = toolset

    assert tools["search_products"].invoke({"limit": 0})["retornados"] == 1
    assert tools["search_products"].invoke({"limit": 99})["retornados"] <= 20


def test_card_de_produto_nao_expoe_pii(toolset) -> None:
    _, tools = toolset

    out = tools["search_products"].invoke({"category": "violoes"})

    assert out["produtos"]
    for card in out["produtos"]:
        assert not PII_KEYS & card.keys()


def test_detalhe_do_takamine_gd20(toolset) -> None:
    _, tools = toolset

    out = tools["product_detail"].invoke({"name_or_id": "Takamine GD20"})

    assert out["encontrado"] is True
    assert out["preco"] == "R$ 2.199,00"
    assert "promocao" not in out, "a promocao do produto 95 esta inativa"


def test_detalhe_ignora_acento_e_caixa(toolset) -> None:
    _, tools = toolset

    out = tools["product_detail"].invoke({"name_or_id": "takamine gd20"})

    assert out["encontrado"] is True
    assert out["product_id"] == 95


def test_detalhe_por_id_aplica_promocao_ativa(toolset) -> None:
    _, tools = toolset

    out = tools["product_detail"].invoke({"name_or_id": "127"})

    assert out["desconto_percent"] == 10
    assert out["preco_com_desconto"] == "R$ 323,10"


def test_detalhe_inexistente_nao_inventa(toolset) -> None:
    _, tools = toolset

    out = tools["product_detail"].invoke({"name_or_id": "Saxofone Selmer"})

    assert out["encontrado"] is False
    assert "preco" not in out


# --- identificacao e pedidos ------------------------------------------------


def test_identifica_cliente_pelo_telefone(toolset) -> None:
    session, tools = toolset

    out = tools["identify_customer"].invoke({"phone": "(67) 98432-1098"})

    assert out["identificado"] is True
    assert out["primeiro_nome"] == "Pedro"
    assert session.customer_id == 3


def test_aceita_telefone_com_codigo_do_pais(toolset) -> None:
    _, tools = toolset

    out = tools["identify_customer"].invoke({"phone": "5567984321098"})

    assert out["identificado"] is True


def test_telefone_curto_nao_identifica(toolset) -> None:
    session, tools = toolset

    out = tools["identify_customer"].invoke({"phone": "98432"})

    assert out["identificado"] is False
    assert out["motivo"] == "telefone incompleto"
    assert session.identified is False


def test_telefone_desconhecido_limpa_a_sessao(toolset) -> None:
    session, tools = toolset
    tools["identify_customer"].invoke({"phone": "(67) 98432-1098"})

    out = tools["identify_customer"].invoke({"phone": "(11) 90000-0000"})

    assert out["identificado"] is False
    assert session.customer_id is None


def test_pedido_exige_cliente_identificado(toolset) -> None:
    _, tools = toolset

    out = tools["lookup_order"].invoke({})

    assert out["erro"] == "cliente_nao_identificado"


def test_pedido_de_outro_cliente_nao_e_revelado(toolset) -> None:
    _, tools = toolset
    tools["identify_customer"].invoke({"phone": "(67) 98432-1098"})  # cliente 3

    out = tools["lookup_order"].invoke({"order_id": 6})  # pedido 6 e do cliente 9

    assert out["encontrado"] is False


def test_pedido_inexistente_recebe_a_mesma_resposta_de_pedido_alheio(toolset) -> None:
    _, tools = toolset
    tools["identify_customer"].invoke({"phone": "(67) 98432-1098"})

    alheio = tools["lookup_order"].invoke({"order_id": 6})
    inexistente = tools["lookup_order"].invoke({"order_id": 999})

    assert alheio == inexistente, "nao confirmar a existencia de pedido de outro cliente"


def test_lista_pedidos_do_cliente(toolset) -> None:
    _, tools = toolset
    tools["identify_customer"].invoke({"phone": "(67) 98432-1098"})

    out = tools["lookup_order"].invoke({})
    orders = {item["pedido"]: item for item in out["pedidos"]}

    assert set(orders) == {1, 19}
    assert orders[1]["status"] == "entregue"
    assert orders[1]["rastreio"] == "BRAB1234567BR"
    assert orders[19]["status"] == "cancelado"


def test_total_divergente_e_sinalizado_nao_corrigido(toolset) -> None:
    _, tools = toolset
    tools["identify_customer"].invoke({"phone": "(67) 98321-6543"})  # cliente 7

    out = tools["lookup_order"].invoke({"order_id": 20})
    order = out["pedido"]

    assert order["total"] == "R$ 1.400,00"
    assert order["total_divergente"] is True
    assert "instrucao" in order


# --- politicas --------------------------------------------------------------


def test_politica_de_devolucao_com_proveniencia(toolset) -> None:
    _, tools = toolset

    out = tools["lookup_policy"].invoke({"question": "me arrependi, posso devolver?"})
    topo = out["trechos"][0]

    assert out["encontrado"] is True
    assert topo["secao"] == "4.1"
    assert topo["citacao"] == "Politica §4.1"
    assert "7 (sete) dias corridos" in topo["texto"]


def test_politica_fora_do_manual_nao_inventa(toolset) -> None:
    _, tools = toolset

    out = tools["lookup_policy"].invoke({"question": "receita de bolo de cenoura"})

    assert out["encontrado"] is False
    assert "instrucao" in out


# --- pagamento --------------------------------------------------------------


def test_pix_aplica_cinco_por_cento(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 1000, "method": "pix"})

    assert out["valor_final"] == "R$ 950,00"


def test_pix_nao_acumula_com_preco_promocional(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke(
        {"amount": 359, "method": "pix", "promo_price": True}
    )

    assert out["desconto_percent"] == 0
    assert out["valor_final"] == "R$ 359,00"


def test_pix_acima_de_dois_mil_avisa_sobre_combinacao(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 2199, "method": "pix"})

    assert any("2.000" in nota for nota in out["observacoes"])


def test_forma_de_pagamento_desconhecida_e_recusada(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 500, "method": "cheque"})

    assert out["permitido"] is False
    assert "cheque" not in out["formas_aceitas"]


def test_valor_invalido_e_recusado(toolset) -> None:
    _, tools = toolset

    assert tools["simulate_payment"].invoke({"amount": 0, "method": "pix"})["permitido"] is False


def test_doze_vezes_bloqueado_abaixo_da_parcela_minima(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 849, "method": "credito", "installments": 12})

    assert out["permitido"] is False
    assert "70,75" in out["motivo"]


def test_doze_vezes_permitido_no_limite(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke(
        {"amount": 1200, "method": "credito", "installments": 12}
    )

    assert out["permitido"] is True
    assert out["valor_parcela"] == "R$ 100,00"


def test_parcelas_acima_de_doze_sao_recusadas(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke(
        {"amount": 5000, "method": "credito", "installments": 13}
    )

    assert out["permitido"] is False


def test_seis_vezes_exige_parcela_de_oitenta(toolset) -> None:
    _, tools = toolset

    bloqueado = tools["simulate_payment"].invoke(
        {"amount": 400, "method": "credito", "installments": 6}
    )
    liberado = tools["simulate_payment"].invoke(
        {"amount": 480, "method": "credito", "installments": 6}
    )

    assert bloqueado["permitido"] is False
    assert liberado["permitido"] is True


def test_tres_vezes_exige_compra_minima_de_cinquenta(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 49.9, "method": "credito", "installments": 3})

    assert out["permitido"] is False


def test_debito_nao_parcela(toolset) -> None:
    _, tools = toolset

    out = tools["simulate_payment"].invoke({"amount": 500, "method": "debito", "installments": 3})

    assert out["permitido"] is False


# --- montagem da clausula (sem banco) ---------------------------------------


def test_where_vazio_quando_nao_ha_filtro() -> None:
    assert _where(CatalogFilter(only_available=False)) == ("", [])


def test_where_compoe_clausulas_e_parametros_na_ordem() -> None:
    where, params = _where(CatalogFilter("violao", "5", 100.0, 1000.0, True))

    assert where.startswith(" WHERE ")
    assert "stock_quantity > 0" in where
    assert params == ["violao", "violao", "5", "5", 100.0, 1000.0]


def test_where_tem_um_parametro_para_cada_marcador() -> None:
    """Regressao: marcador sem parametro (ou o contrario) quebra a consulta em runtime."""
    for catalog_filter in (
        CatalogFilter("violao"),
        CatalogFilter(category="violoes", only_available=False),
        CatalogFilter(min_price=500.0, max_price=1000.0),
        CatalogFilter("aço", "5", 100.0, 2000.0, False),
    ):
        where, params = _where(catalog_filter)
        assert where.count("?") == len(params)
