from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from prompt_lab.pydantic_loader import load_model_entrypoint


def test_load_model_entrypoint_loads_class() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "from pydantic import BaseModel\n\nclass Demo(BaseModel):\n    name: str\n",
            encoding="utf-8",
        )

        model = load_model_entrypoint(root, "model.py", "model.Demo")

        assert issubclass(model, BaseModel)
        assert getattr(model.model_validate({"name": "Ada"}), "name") == "Ada"


def main() -> int:
    tests = [test_load_model_entrypoint_loads_class]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
