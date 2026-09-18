# WINDOWS_RTX3070_PYTHON_LAUNCHER_CORRECTION

**VERDICT: WINDOWS_RTX3070_PYTHON_LAUNCHER_CORRECTION_PASS**

The handoff now resolves Python once through the existing launcher, validates the exact interpreter as **3.12.10 x64**, and uses that interpreter for setup and `-m venv`. No Python/ML package, system setting or driver was installed or changed locally. No CUDA operation, Qwen load, inference, training or evaluation ran. The remote corrected setup has not been executed by this gate.

## Root cause and reproduced evidence

The user reported Windows 10 Pro 19045, RTX 3070 Ti with 8192 MiB, and a passed script 00. `where.exe py` / `Get-Command py` resolve to `C:\Windows\py.exe`; both that launcher and the direct per-user interpreter report Python 3.12.10. A second launcher installation was blocked with MSI `0x80070659`; its log reports `launcher_AllUsers = Present`. These are user-provided remote observations, not a diagnosis of broken Python.

At original commit `ef1fc27a1f0bcb934e9003dc4f44faf11ce3b631`, script 01 passed `-3.12` through `Invoke-Bounded`. The helper quoted **every** argument, yielding `py.exe "-3.12" ...`. The launcher did not consume the quoted selector; it reached `python.exe`, which rejected it as `Unknown option: -3` (exit 2). The old Python helper also selected `py -3.12` again for venv creation instead of retaining the resolved interpreter.

The failure was reproduced locally before editing using only version probes: direct `py -3.12 --version` returned **Python 3.12.10 / exit 0**; the original wrapper with the same argument array produced **Unknown option: -3 / exit 2**. This reproduces the real-machine symptom without installing an environment. The earlier handoff's cheap tests did not cover the launcher's raw-command-line selector handling. Its completed receipt/evidence are preserved unchanged, not rewritten as proof that this branch worked.

The [official Python Windows launcher documentation](https://docs.python.org/3.12/using/windows.html#python-launcher-for-windows) distinguishes launcher version selection from interpreter invocation, supports per-user runtimes selected by an existing launcher, and documents possible launcher install-on-demand preferences. Probe child processes disable those install preferences without changing the parent environment, PATH or registry.

## Correction

- `Remote.Common.ps1` now has explicit launcher/interpreter command construction. Only `py.exe` receives launcher selectors; any attempt to pass `-3`, `-3.12` or `-V:...` to `python.exe` fails before process launch. Launcher selectors remain unquoted on its raw command line; paths and other arguments retain Windows quoting.
- `Resolve-FrozenPython` obtains JSON-escaped `sys.executable`, version and bitness through the launcher, then verifies `--version`, bitness and path identity using that exact interpreter. Version must equal **3.12.10** and bitness **64**. Probes are bounded to 15 seconds and create no venv.
- Script 01 invokes `<resolved python.exe> -B environment.py setup`; the Python helper creates the venv with `[sys.executable, '-m', 'venv', target]`. There is no second launcher selection and no selector in interpreter arguments. Reused environments also have their exact version and bitness checked.
- Script 05's pre-venv packaging fallback used the same faulty launcher path, so it now uses the same resolver. This keeps diagnostics available after a pre-venv failure.
- The Russian README now says a working `py -3.12 --version` is sufficient evidence of a healthy launcher; a second launcher, policy/registry changes, administrator access and CUDA Toolkit are unnecessary. It gives the correction pull/rerun commands.

## Incomplete environment policy

An absent `.venv-qlora-remote` is created exclusively. Before venv bootstrap, the gate records matching ownership nonces in its scratch journal and the new directory. A recognized completed environment retains the previous verify-and-reuse behavior without reinstalling packages.

A gate-owned interruption before package installation can resume the same `python.exe -m venv` bootstrap, without `--clear` or deletion. Recovery requires the exact repository-relative directory, matching owner/path/nonce/stage records, no reparse points, no unexpected top-level contents, no non-bootstrap site-packages and no package-install evidence. The journal records package-install start before launching pip; such a partial install is never treated as a clean bootstrap failure.

No directory is automatically deleted. An unmarked partial directory from the old implementation cannot be positively attributed to this gate and is preserved with instructions to run script 05 and request review. Unknown ownership, mismatched markers or unexpected contents fail closed. No Python reinstall or directory deletion is requested merely because the old launcher wrapper failed.

## Validation and protected state

**18 focused checks passed:** 15 new launcher/environment regressions and 3 existing shared-helper checks. They cover the exact launcher/interpreter version and venv command matrices, `C:\Windows\py.exe`, the Cyrillic fixture path `C:\Users\Булат\AppData\Local\Programs\Python\Python312\python.exe`, paths with spaces, PS 5.1 quoting, exact-version/x64 rejection, script 01 dispatch, owned pre-install recovery, unknown-directory preservation, package-state refusal and completed-environment reuse. Shared-helper tests cover all six read-only dry runs, parsing, native quoting/exit codes and the owned-child watchdog. Venv/package/CUDA actions in fixtures are mocked; no full ML environment was created.

Real corrected version probes on **Windows PowerShell 5.1.26100.9444** passed for both the launcher and the resolved interpreter. These probes did not create a venv, install packages or execute ML code. Runtime tests and source hashes are recorded in the companion JSON evidence.

**313 pre-existing files remain byte-identical**; the only five modified existing files are script 01, script 05, their common helper, environment helper and README. Original model/data/eval artifacts, application/G1/G2/contracts, historical receipts/evidence, training configuration, model pins and ML package pins are unchanged. Both existing environment inventories are unchanged; `.venv-qlora-remote` remains absent locally. Evaluation content exposure is zero; the integrity supervisor only hashes protected bytes. G3 and application/browser smoke were not started.

## Git delivery and remote action

Before writes, `main` was clean at `ef1fc27a1f0bcb934e9003dc4f44faf11ce3b631`, exact origin was `https://github.com/AiratBastanov/TalkNFace.git`, and a fresh fetch confirmed ahead/behind **0/0**. Delivery contains the five corrections, the new regression test and this new receipt/evidence only. The delivery commit is discoverable with `git log -1 --format=%H -- docs/gates/WINDOWS_RTX3070_PYTHON_LAUNCHER_CORRECTION.md`; normal push, clean status and HEAD/origin/main/remote-main equality are verified after committing and reported to the user. No model, data, venv, scratch or result archive is staged.

On the friend's PC, from the clean repository folder:

```powershell
git pull --ff-only
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-rtx3070\01-setup-python-env.ps1
```

Keep the existing working system launcher. If an unrecognized partial environment is reported, preserve it and package diagnostics with script 05; do not delete it blindly. Script 01 still ends with its previously authorized tiny CUDA/NF4 check on the target. It does not load Qwen or start training.

STOP — REMOTE TRAINING SMOKE NOT STARTED.
