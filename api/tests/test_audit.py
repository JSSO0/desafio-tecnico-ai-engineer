import json
from pathlib import Path

from app.audit.log import AuditEntry, audit_event, redact
from app.core.turn import TurnOutcome


def test_redige_telefone_formatado() -> None:
    assert redact("meu telefone é (67) 98432-1098") == "meu telefone é [telefone]"


def test_redige_telefone_sem_formatacao() -> None:
    assert "67984321098" not in redact("chama no 67984321098")


def test_redige_email() -> None:
    assert redact("manda em pedro.oliveira@jmail.com") == "manda em [email]"


def test_auditoria_grava_jsonl_com_campos_obrigatorios(tmp_path: Path) -> None:
    audit_event(
        tmp_path,
        AuditEntry(
            request_id="abc123",
            session_id="sessao1",
            customer_id=3,
            message="meu telefone é (67) 98432-1098",
        ),
        TurnOutcome(
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
    record = json.loads(arquivos[0].read_text(encoding="utf-8").strip())

    assert record["request_id"] == "abc123"
    assert record["session_id"] == "sessao1"
    assert record["customer_id"] == 3
    assert record["tools"] == ["consultar_pedido"]
    assert record["tokens_in"] == 100
    assert record["prompt_version"] == "v1abc"
    assert "98432" not in json.dumps(record)


def test_auditoria_acumula_uma_linha_por_turno(tmp_path: Path) -> None:
    for indice in range(3):
        audit_event(
            tmp_path,
            AuditEntry(
                request_id=f"req{indice}",
                session_id="sessao1",
                customer_id=None,
                message="oi",
            ),
            TurnOutcome(
                answer="oi",
                tokens_in=1,
                tokens_out=1,
                latency_ms=1,
                prompt_version="v1",
                model="m",
            ),
        )

    audit_file = next(tmp_path.glob("audit-*.jsonl"))
    assert len(audit_file.read_text(encoding="utf-8").strip().splitlines()) == 3
