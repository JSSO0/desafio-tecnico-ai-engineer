from app.core.text import brl
from app.guards.grounding import enforce_price_grounding, extract_amounts, grounded_values


def test_brl_formata_padrao_brasileiro() -> None:
    assert brl(2199) == "R$ 2.199,00"
    assert brl(323.1) == "R$ 323,10"
    assert brl(0) == "R$ 0,00"
    assert brl(1234567.89) == "R$ 1.234.567,89"


def test_extrai_valores_em_reais() -> None:
    assert extract_amounts("Sai por R$ 2.199,00 ou R$ 950") == [2199, 950]


def test_valor_ancorado_na_ferramenta_passa() -> None:
    response = "O Takamine GD20 custa R$ 2.199,00."
    ferramenta = '{"preco": "R$ 2.199,00", "price_brl": 2199.0}'

    final, guard = enforce_price_grounding(response, ferramenta)

    assert guard is None
    assert final == response


def test_valor_inventado_e_bloqueado() -> None:
    final, guard = enforce_price_grounding(
        "Sai por R$ 1.499,00.", '{"preco": "R$ 2.199,00"}'
    )

    assert guard == "preco_sem_ferramenta"
    assert "1.499" not in final


def test_resposta_sem_valor_passa() -> None:
    final, guard = enforce_price_grounding("Aceitamos pix com 5% de desconto.", "")

    assert guard is None
    assert final == "Aceitamos pix com 5% de desconto."


def test_parcela_calculada_pela_ferramenta_passa() -> None:
    final, guard = enforce_price_grounding(
        "Fica em 12x de R$ 100,00.", '{"valor_parcela": "R$ 100,00"}'
    )

    assert guard is None


def test_valor_parcialmente_ancorado_e_bloqueado() -> None:
    # basta um valor sem lastro para bloquear: o cliente pode tomar decisao com ele
    final, guard = enforce_price_grounding(
        "O violao sai por R$ 599,90, e o case por R$ 210,00.",
        '{"preco": "R$ 599,90"}',
    )

    assert guard == "preco_sem_ferramenta"
    assert "210" not in final


def test_valores_sao_deduplicados_na_saida_da_ferramenta() -> None:
    assert grounded_values('{"a": 10, "b": "10,00", "c": 2.5}') == {10, 2.5}


def test_valor_formatado_na_saida_da_ferramenta_e_reconhecido() -> None:
    """Regressao: "R$ 2.199,00" era lido como 2.199 + 00 e bloqueava a resposta correta."""
    assert grounded_values("{'preco': 'R$ 2.199,00'}") == {2199}
    assert grounded_values("{'preco': 'R$ 2.199,00', 'price_brl': 2199.0}") == {2199}
