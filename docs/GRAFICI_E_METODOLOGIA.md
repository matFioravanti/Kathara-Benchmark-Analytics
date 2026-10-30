# Documentazione — Kathara Benchmark Analytics

## 1. Obiettivo

Analizzare i risultati di `Kathara-Skill-LLM` senza alterare i laboratori, il checker o il benchmark originale. Tutte le figure sono create con **pandas + Matplotlib**. Sono utilizzati soltanto i CSV prodotti dalla pipeline del benchmark; nessun dato sintetico viene caricato automaticamente.

## 2. Utilizzo in tre passaggi

1. Copia `results/runs.csv` e `results/checks.csv` dalla repository del benchmark nella cartella locale **`result/`** di questa repository. Puoi copiare anche `results/summary.csv`, che rimane un riferimento facoltativo.
2. Da questa repository esegui:

   ```bash
   python3 -m pip install -r requirements.txt
   python3 genera_grafici.py
   ```
3. Trovi grafici **PNG e PDF** e report CSV in `grafici/`. L'input non viene modificato. Puoi ripetere l'operazione dopo ogni esperimento aggiornando i CSV.

**Non servono modifiche a JSON di mapping, ID di laboratorio o modelli.** Il programma riconosce direttamente i nomi delle colonne reali. È possibile personalizzare percorsi e formati: `python3 genera_grafici.py --input /percorso/result --output /percorso/figure --format png`.

## 3. Dataset e colonne

`runs.csv` è la fonte delle metriche aggregate: `ID`, `lab_id`, `dns_tree_id`, `task_level`, `prompt_type`, `experiment_id`, `replicate`, `model`, `skill_mode`, `reasoning_effort`, `checks_passed`, `checks_total`, `pipeline_completed`, `checker_executed`, `task_success`, tempi, token, campi `sampling_*`, `llm_temperature`, `llm_top_p` e Skill gate.

`checks.csv` contiene `ID`, `category`, `test_description`, `passed`, `reason` e le dimensioni sperimentali. Il programma non assume che `test_description` sia unico: due controlli diversi possono avere la stessa descrizione. Le righe sono abbinate per `ID` e ricevono un ID progressivo per preservare i duplicati legittimi.

`summary.csv` può essere archiviato nella stessa cartella, ma **non è usato per determinare i tassi**: lo script calcola le aggregazioni direttamente dalle singole run e dai singoli check, evitando di sommare righe già aggregate.

### Condizioni preliminari di qualità

- Gli ID delle run devono essere unici e i check devono riferirsi a run presenti.
- Il numero di esiti `passed=True` e il numero di check valutati devono coincidere con `checks_passed` / `checks_total` delle run. In caso contrario, i punteggi discordanti sono esclusi dai grafici mentre le altre run vengono elaborate.
- Le percentuali non sono calcolate su denominatori uguali a zero; `NaN` rappresenta informazione assente, non zero.
- Non sono imputati valori di temperatura né ragioni di un errore che il checker non distingue.

## 4. Grafici: cosa mostrano e perché

| Cartella | Figura o output | X e raggruppamento | Y / metrica | Domanda scientifica |
|---|---|---|---|---|
| `01_correttezza` | Barre modalità Skill | `skill_mode` | Media del tasso per run: `checks_passed / checks_total × 100` | Quali modalità ottengono punteggi più alti? |
| `11_skill` | Confronto appaiato e differenze vs `no_skill` | Solo stesse condizioni sperimentali, ripetizione e correzione | Media percentuale, differenza in punti percentuali | Come cambia l'esito a condizioni condivise? |
| `02_prompt` | Barre formulazioni `T1`…`T6` | `prompt_type` | Media del tasso per run | Quali formulazioni risultano più difficili? |
| `03_laboratori` | Barre `small/medium/large`; heatmap lab×prompt, lab×Skill | `task_level`, lab/albero/livello | Media del tasso per run, scala 0–100% | Come varia l'esito tra scenari? |
| `04_dns_e_checker` | Barre orizzontali per categoria e Skill | `category`, `skill_mode` | `fail / (pass+fail) × 100` | In quali categorie del checker si concentrano i fallimenti? |
| `13_dns_diagnostics` | Conteggi errori per record DNS riconosciuto | Tipo `A/AAAA/MX/NS/SOA/CNAME` presente esplicitamente nella diagnostica `reason` | Conteggio check falliti | Quali record compaiono nei messaggi di fallimento? |
| `05_efficienza` | Barre di tempi e token | `skill_mode` | Medie di `total_seconds`, `agent_seconds`, `checker_seconds`, `total_tokens`, `input_tokens`, `output_tokens` | Quanto costano le diverse modalità in risorse? |
| `06_skill_gate` | Tempi lettura Skill + CSV stati | `skill_mode`, `skill_gate_status` | `skill_gate_read_seconds` e numero di run per stato | Il caricamento delle Skill è stato verificato e quanto dura? |
| `12_sampling` | Copertura telemetria; eventuale temperatura vs successo | `skill_mode`, `sampling_temperature_status`, temperatura osservata | Conteggi stato e scatter se almeno tre osservazioni con variazione | La temperatura è misurata? È associata al punteggio nel campione? |

Il generatore salva anche `normalized_runs.csv`, `normalized_checks.csv`, `skill_prompt_summary.csv`, `full_task_success.csv` e, se applicabili, `skill_matched_summary.csv`, `skill_paired_deltas.csv`, `sampling_coverage.csv`, `check_category_failure_rates.csv`, `dns_record_failures.csv` e `skill_gate_summary.csv`.

## 5. Formulazioni e modalità

Le sei formulazioni correnti sono: **T1 tecnico strutturato**, **T2 tecnico discorsivo**, **T3 non tecnico discorsivo**, **T4 non tecnico non strutturato**, **T5 albero grafico** e **T6 JSON strutturato**. Le modalità rilevate nel dataset sono confrontate rispettando il valore originale di `skill_mode`: `no_skill`, `creation_only`, `dns_only`, `both_forced`, `auto`.

Il grafico semplice per Skill/prompt è una descrizione del **campione disponibile** e potrebbe avere gruppi sbilanciati. Per valutare la differenza tra modalità a parità di altre condizioni usa `11_skill`: vengono appaiati esperimento, laboratorio + albero DNS + livello, prompt, modello, ripetizione, sforzo di ragionamento, correzione, versione di prompt, protocollo Skill e agente. Le differenze non dimostrano causalità e il numero di coppie è essenziale.

## 6. Risultati DNS e anomalie MX

`04_dns_e_checker` usa le categorie effettive del checker; non tenta di convertire automaticamente un controllo `custom` in autorità DNS, record o delega. `13_dns_diagnostics` interpreta solo i messaggi `reason` che includono esplicitamente il pattern `resolve TIPO`. Un check può dipendere da più condizioni, quindi il conteggio dei fallimenti **non equivale al numero di cause indipendenti**. Per i record MX, un punto finale nei nomi FQDN può generare discrepanze di confronto testuale: il programma li lascia falliti fino a revisione del checker/oracle, senza correggerli automaticamente.

## 7. Temperatura LLM e campi mancanti

Si tratta della **temperatura di campionamento del modello**, non della temperatura di CPU/GPU. `llm_temperature` e `sampling_temperature_status` devono provenire dal benchmark: valore vuoto con stato `unavailable` significa **non osservato**, non temperatura pari a 0. Il grafico di copertura conta gli stati effettivi; scatter temperatura-successo è generato solo con almeno tre misure numeriche osservate e almeno due temperature distinte. `reasoning_effort=low` non è una temperatura.

## 8. Interpretazione, limiti e riproducibilità

- La barra “test superati” è la **media dei tassi delle run**, non il tasso micro globale. I denominatori del checker possono variare tra laboratori; per confronti rigorosi verificare i CSV esportati.
- **`task_success` è un indicatore diverso**: richiede l'esito complessivo positivo della run. Viene riportato anche `full_task_success.csv` separatamente.
- Le heatmap sono limitate a 50 scenari per leggibilità, senza selezionare silenziosamente un sottoinsieme.
- Non vengono creati boxplot o inferenze statistiche da un'unica run per gruppo. Le etichette dei grafici indicano la numerosità `n`.
- Le aggregazioni di run incomplete o con check non eseguiti richiedono prudenza: `pipeline_completed` e `checker_executed` sono conservati, non sostituiti con la presenza di uno score.
- Il programma usa solo file locali, non invia dati all'esterno e non modifica le sorgenti. Rigenera le figure dopo ogni copia; elimina manualmente la vecchia cartella `grafici/` prima di una nuova esecuzione se vuoi evitare residui grafici di dataset precedenti.

## 9. Test

```bash
python3 -m unittest discover -s tests -v
```

Se il programma segnala ID o conteggi discordanti, **non modificare i numeri per far produrre il grafico**: verifica che `runs.csv` e `checks.csv` provengano dallo stesso export del benchmark.

## 10. Controlli di coerenza fra esportazioni

I file `runs.csv` e `checks.csv` possono essere stati copiati in momenti diversi. Lo script non si blocca più per una singola discordanza: conserva i conteggi originali, marca la run `count_mismatch` e la esclude dai grafici che dipendono da score o check. Le run non presenti nei dettagli sono marcate `no_detail` e possono contribuire alle sole analisi aggregate. Per trovare gli ID problematici consultare `grafici/data_quality_issues.csv` e `grafici/generation_log.txt`; `grafici/run_data_quality.csv` contiene tutti gli stati. Non correggere automaticamente i valori originali.
