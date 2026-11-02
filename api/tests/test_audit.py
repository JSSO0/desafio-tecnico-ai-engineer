import json
from pathlib import Path

from app.audit.log import audit_event, redact
from app.core.turn import TurnOutcome


def test_redige_telefone_formatado() -> None:
    assert redact("meu telefone é (67) 98432-1098") == "meu telefone é [telefone]"


def test_redige_telefone_sem_formatacao() -> None:
    assert "67984321098" not in redact("chama no 67984321098")


def test_redige_email() -> None:
    assert redact("manda em pedro.oliveira@jmail.com") == "manda em [email]"


def test_auditoria_grava_jsonl_com_campos_obrigatorios(tmp_path: Path) -> None:
    audit_event(
        logs_dir=tmp_path,
        request_id="abc123",
        session_id="sessao1",
        customer_id=3,
        message="meu telefone é (67) 98432-1098",
        outcome=TurnOutcome(
            answer="Vou verificar.",
            tools=("consultar_pedido",),
            tokens_in=100,
            tokens_out=20,
            latency_ms=900,
            prompt_version="v1abc",
            model="deepseek-chat",
        ),
    )

    arquivos = list(tmp_path.glob("audit-*.jsonl"))
    assert len(arquivos) == 1
    registro = json.loads(arquivos[0].read_text(encoding="utf-8").strip())

    assert registro["request_id"] == "abc123"
    assert registro["session_id"] == "sessao1"
    assert registro["customer_id"] == 3
    assert registro["tools"] == ["consultar_pedido"]
    assert registro["tokens_in"] == 100
    assert registro["prompt_version"] == "v1abc"
    assert "98432" not in json.dumps(registro)


def test_auditoria_acumula_uma_linha_por_turno(tmp_path: Path) -> None:
    for indice in range(3):
        audit_event(
            logs_dir=tmp_path,
            request_id=f"req{indice}",
            session_id="sessao1",
            customer_id=None,
            message="oi",
            outcome=TurnOutcome(
                answer="oi",
                tokens_in=1,
                tokens_out=1,
                latency_ms=1,
                prompt_version="v1",
                model="m",
            ),
        )

    arquivo = next(tmp_path.glob("audit-*.jsonl"))
    assert len(arquivo.read_text(encoding="utf-8").strip().splitlines()) == 3
