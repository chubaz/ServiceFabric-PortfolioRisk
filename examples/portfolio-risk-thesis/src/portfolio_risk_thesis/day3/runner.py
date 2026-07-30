from .contracts import ArchitectureComparison
from .treatments import b0,b1,a1
def run(bundle, provider): return ArchitectureComparison(context_digest=bundle.context_digest,runs=(b0(bundle),b1(bundle,provider),a1(bundle,provider)))
