# Asisten Operasional

Asisten Operasional is a local, Indonesian-language workspace for reviewing sales, inventory, and sensor readings. Use it to investigate anomalies, draft updates from source records, and prepare status reports and follow-ups.

The sample workspace uses synthetic records and example assignments. Escalation drafts stay in the app. A threshold crossing flags a record for review.

## Run locally

Use Python 3.10 or later and SQLite with window-function support. The model setup script is for Apple Silicon macOS and downloads about 2.52 GB. The dashboard and analytics work before model setup.

From the repository:

```sh
export PYTHONPYCACHEPREFIX="$PWD/../internal/runtime/pycache"
python3 -m ops init
python3 -m ops serve
```

Open http://127.0.0.1:8775. In a second terminal, start generation:

```sh
export PYTHONPYCACHEPREFIX="$PWD/../internal/runtime/pycache"
./scripts/setup-model.sh
python3 -m ops model
```

Both servers bind to loopback. The setup script verifies the pinned [llama.cpp archive](https://github.com/ggml-org/llama.cpp/releases/tag/b6760) and [Qwen3-4B weight file](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/a9a60d0/Qwen3-4B-Q4_K_M.gguf) by SHA-256. To use a different local data directory, pass it to the script and use `python3 -m ops --runtime /path/to/runtime <command>` for each command. Stop each foreground server with Ctrl+C.

## Walkthrough

1. View **Dasbor** for all sites. Review the weekly trend, anomaly sources, data quality, and daily distribution. Filter to one site and inspect the flagged record.
2. In **Bank prompt**, search for a task, inspect or copy its template, and select **Pilih untuk draf**. For a draft about a single anomaly, select its source ID. An empty brief uses the task example. Review any generated figures against the displayed source IDs before using the draft.
3. In **Tindak lanjut operasi**, review requests, the risk register, K3L program deadlines, and the HSE escalation draft.
4. Open **Laporan status** or **Paparan operasi** to print a status update or briefing from the same dataset.

### Sample workflows

- Sales in Barat on November 4. Open source S66, then draft a short weekly update with the 296-unit observation and the weekday reference.
- Inventory in Tengah on November 6. Open S152, then draft a request to verify the 379 counted units against 426 in book stock.
- Sensor review in Timur on November 9. Open and select S239, then brainstorm two checks of the reading. Review the HSE draft alongside the source record.

## Analysis

The generator fixes the seed and produces 84 days for three fictional sites. The SQL views keep the first row per site and date and report duplicates and missing sensor values separately. SQLite computes the dashboard figures and provides facts to the model. Missing readings are excluded from sensor averages.

- Sales flags a value at least 1.6 times the average of the prior four observations for the same site and weekday.
- Inventory flags a gap of 25 units or more between book and counted stock.
- Sensor flags a reading above the illustrative threshold of 49. The scenario assigns no physical unit or safety meaning to that threshold.

The project uses fixed rules and a small dataset. Different operating baselines, duplicate policies, missing-data patterns, or corroborating measurements can change the interpretation. The model summarizes selected facts and proposes lines of inquiry. Review its output before use.

## Verify and evaluate

```sh
export PYTHONPYCACHEPREFIX="$PWD/../internal/runtime/pycache"
export TMPDIR="$PWD/../internal/runtime"
python3 -m unittest discover -s tests -v
python3 -m ops eval
```

Run evaluation with the local model running. The command compares baseline and refined prompts on identical fixed examples with the same model and decoding settings. It saves outputs, individual checks, and timings to `evaluation.json` in the runtime directory. The status report reads that result when available.

### Observed run

On the 16 fixed Indonesian examples, the minimal baseline passed **0/16** and the refined prompt passed **12/16**, with three passes in each of the four task types. Eight baseline drafts were empty or truncated. The refined prompt completed all 16 drafts.

The rubric checks required format, known source IDs, preserved figures, and handling of missing information. Three refined cases failed the missing-information check. One of these acknowledged missing data in different wording, while two responded using irrelevant evidence. The remaining failure added a calculated figure outside the supplied facts and missed the required layout. The strict format and citation rubric favors prompts that state the expected contract. These results describe this dataset, model, and rubric. A matching source ID does not establish that the model interpreted its contents correctly.
