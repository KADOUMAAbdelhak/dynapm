# Local research data

Place authorized Materna traces in `data/raw/Materna-Trace-{1,2,3}/`, preserving the original per-VM CSV filenames and trace metadata. This directory is ignored by Git. The loader defaults to these paths.

Dataset selection is provided by `dynapm.data.filter.filter_corpus`; bootstrap characterization is provided by `dynapm.scripts.run_bootstrap_characterization`. They write local selection and threshold artifacts under `dynapm/data/`. Generated JSONs and Parquets are ignored. Some tests require VM 501 from trace 1, VM 58 from trace 2, VM 238 from trace 3, and a generated `kept_vms.json`.

No raw corpus files or generated scientific artifacts belong in commits. Data preparation and corpus processing are explicit research jobs, not installation steps.
