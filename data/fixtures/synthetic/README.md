# Synthetic fixtures

Only generated, non-provider, explicitly labelled synthetic fixtures belong
here.

`day23/` contains three fictional CSV exports and their explicit mapping
manifests: a CRSP-like daily market export, a Compustat-like annual export,
and a date-effective link export. Names, identifiers, observations, and values
are synthetic and do not reproduce provider data. Parquet coverage is created
ephemerally by tests so no Parquet or database artifact enters Git.
