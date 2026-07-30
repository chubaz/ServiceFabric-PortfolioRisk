from pathlib import Path
from .contracts import PromptReference, digest
def prompt_reference(path: Path, role: str) -> PromptReference: return PromptReference(prompt_id=path.stem,version="v1",digest=digest(path.read_text()),role=role)
