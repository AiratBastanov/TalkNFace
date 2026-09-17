# Untouched local Qwen3 baseline

This R&D directory runs the original local Qwen3-4B BF16 checkpoint on the **HOLDOUT_EVAL_ONLY** A01–A16 asset. Training is forbidden for this asset. There are no training splits, datasets, adapters, quantization, model downloads or application routes here.

The model input is an English system instruction, a public scenario context, the exact Russian utterance and the existing `PlayerMoveInterpretationSchema`. The worker receives no expected labels, planning documents, utility/state data or raw datasets. `sys.addaudithook` blocks dataset opens and network connections; Hugging Face offline flags and `local_files_only=True` also apply. The separate integrity process reads dataset bytes only for hashes.

From the repository root, on the recorded Windows hardware and installed Python 3.12:

```powershell
python -m venv .venv-ml
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:PIP_CACHE_DIR = Join-Path (Get-Location) '.tmp/pip-cache'
.venv-ml/Scripts/python.exe -m pip install --only-binary=:all: -r ml/baseline/requirements.txt
.venv-ml/Scripts/python.exe -m pip check
./ml/baseline/preflight.ps1 -OutputPath .tmp/qwen-hardware.json
.venv-ml/Scripts/python.exe ml/baseline/integrity.py --output .tmp/qwen-integrity-before.json
.venv-ml/Scripts/python.exe -m unittest discover -s ml/baseline -p 'test_*.py' -v
.tools/node-v24.21.0-win-x64/node.exe ml/baseline/verify_contract.mjs
.venv-ml/Scripts/python.exe ml/baseline/run.py sanity --output .tmp/qwen-sanity-auto
.venv-ml/Scripts/python.exe ml/baseline/run.py eval --output .tmp/qwen-a01-a16-run1
.venv-ml/Scripts/python.exe ml/baseline/integrity.py --output .tmp/qwen-integrity-after.json --compare .tmp/qwen-integrity-before.json
.venv-ml/Scripts/python.exe ml/baseline/report.py --run .tmp/qwen-a01-a16-run1
```

Use new output paths for a separately authorized reproduction; the runner refuses to overwrite a run directory. Do not rerun an unchanged expensive campaign just to check it. The local `.tools` Node path is the previously verified project runtime; an equivalent existing Node 24 installation can run the read-only contract check. Neither Node dependencies nor the lockfile are modified.

The versioned eval asset is already materialized. `freeze_assets.mjs` documents its extraction from planning rows and S1/S2 public catalogs. Do not regenerate or change labels during an evaluation. The frozen asset documents the pre-run choices where the planning prose was underspecified (A05 primary intent, A13 own-BATNA reference, A14 concrete active offer, optional topics). No primary-intent alternatives are silently accepted.

`config.json` fixes sampling (0.7/0.8/20, min_p=0), seeds 101/202/303, 512 output tokens, a 4096-token input cap, eager attention and original BF16 with automatic CPU offload. Seeds reset immediately before each case through Transformers `set_seed`, which seeds Python, NumPy and torch CPU/CUDA. Deterministic torch algorithms, CUBLAS configuration and disabled TF32 make the mechanism explicit. Bitwise reproducibility across different hardware or library versions is not asserted. No additional full inference campaign is used to claim it.

The gate owns a single child model process per run, with a four-hour evaluation watchdog and a ten-minute generation time cap. The separate sanity run uses one generic English JSON request, excluded from the 48 scores. Only the gate-owned child is terminated on watchdog expiry. CPU-offload hooks can show parameters on `meta` between calls; the backing tensors remain BF16 and all computation runs without adapters or quantization. On RTX 2060, torch reports emulated rather than native BF16 support.

Each generated output is retained verbatim after removing only its terminal EOS token, along with token IDs, input hash, counts and timing. JSON uses strict parsing (no duplicate keys, NaN, wrappers, repairs or second model calls). Schema validation is checked against the exported Zod contract. Public-context validation checks IDs, values, evidence bounds, argument bindings, current offer references, completeness and conditions. Frozen oracle checks add negation and commitment safety. Unknown domain IDs and invented but otherwise legal offer terms are reported separately, including identifiable emissions in JSON objects that fail another schema field. Invalid JSON remains unassessable for IDs and is counted as a failure.

Primary intent accuracy measures the parsed intent even when another schema field fails. JSON, schema and semantic validity retain separate denominators over every generation. Critical commitment accuracy requires valid schema and safe expected commitment fields. The ambiguity denominator is A05; A16 refusal/clarification is reported separately. Unnecessary clarification uses cases other than A05/A16. Full expected structure match checks all contract fields: set ordering is immaterial, spans must be valid and argument spans must contain the claim, and clarification wording need not match an invented gold sentence. All such rules and classification thresholds are fixed before holdout generation.

Exact dependencies are pinned in `requirements.txt`, including normal transitive dependencies. PyTorch is the prebuilt official CUDA 12.6 wheel; no CUDA Toolkit or compiler is required. Sources consulted: [PyTorch Windows installation](https://pytorch.org/get-started/locally/), [official wheel commands](https://pytorch.org/get-started/previous-versions/), [Qwen3 model card and non-thinking settings](https://huggingface.co/Qwen/Qwen3-4B), [Qwen3 Transformers documentation](https://huggingface.co/docs/transformers/model_doc/qwen3), and [Accelerate CPU offload](https://huggingface.co/docs/accelerate/usage_guides/big_modeling).
