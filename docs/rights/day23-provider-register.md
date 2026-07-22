# Day 2–3 provider register

| Provider class | Rights state | Access state | Phase 1 disposition |
| --- | --- | --- | --- |
| Reviewed synthetic local source | reviewed | available | May be used when labelled synthetic |
| Licensed local export | explicit confirmation required | importable after review | Must retain rights and publication restriction |
| WRDS, CRSP, Compustat network | restricted | disabled | Network-disabled |
| RavenPack, Accern, Bloomberg | restricted | disabled | Network-disabled |

No provider credential is stored in the repository. Any future credential is
an opaque local reference. Phase 1 makes no external API call. A failed or
incomplete query is not zero; missing observations remain missing or carry an
explicit quality flag. No provider access can create broker, order, trade, or
rebalance effects.
