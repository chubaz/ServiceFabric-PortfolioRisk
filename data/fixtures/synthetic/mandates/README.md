# Synthetic mandate references

These fixtures are reviewed-synthetic ServiceFabric-PR research inputs. They
adapt structural ideas from public institutional investment-policy materials;
they are not legal documents, investment advice, or copies of the referenced
policies. Public references have `reference_only` authority and produce no
runtime effect.

Each file contains a `MandateVersion` payload and a separate `RiskPolicySet`
payload. Rule extraction, interpretation, data/capability binding and human
approval occur before an experiment selects either immutable version. During a
run the mandate and policy are read-only. Compliance observations, breach
episodes, decisions and experimental failure labels belong to evaluation and
decision records rather than to the mandate.

The first three archetypes are:

- institutional diversified growth;
- liability-aware pension;
- European corporate-bond income.

They intentionally exercise current ServiceFabric capability families for
portfolio exposure, point-in-time context, returns and reviewed scenarios.
Some semantic metrics are declared design requirements and remain unavailable
until the corresponding capability is registered and validated. Missing data
roles are bound by an experiment assignment to exact dataset revisions; private
values are never embedded in the mandate or portfolio. Missing or ineligible
bindings or missing capabilities must produce `unable_to_assess`, never compliance,
and do not receive constant or synthetic defaults.
