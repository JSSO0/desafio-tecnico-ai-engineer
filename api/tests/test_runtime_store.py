from pathlib import Path

from app.runtime.store import RuntimeStore


def test_contador_de_criacao_separa_origens(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.db")

    assert store.creations_by_ip("1.2.3.4") == 0
    for _ in range(3):
        store.register_creation("1.2.3.4")

    assert store.creations_by_ip("1.2.3.4") == 3
    assert store.creations_by_ip("5.6.7.8") == 0


def test_contador_ignora_criacoes_fora_da_janela(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.db")
    store.register_creation("9.9.9.9")

    assert store.creations_by_ip("9.9.9.9", window_minutes=60) == 1
    assert store.creations_by_ip("9.9.9.9", window_minutes=0) == 0