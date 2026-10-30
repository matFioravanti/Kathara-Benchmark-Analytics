<<<<<<< HEAD
# Grafici del benchmark Kathara-Skill-LLM

Strumento Python con Matplotlib, pandas e NumPy. Il benchmark resta eseguito con
la Skill; questo programma legge risultati e non modifica laboratori o checker.

## Stato dei dati e verifica

La cartella di progetto era vuota: non erano disponibili repository, schema del
checker o risultati reali. L'utente inserirà i risultati in `benchmark_results/`.
Il contratto qui descritto è **un formato di importazione**, non una dichiarazione
sullo schema effettivo di Kathara-Skill-LLM. Non sono stati inventati nomi delle
categorie reali, traduzioni degli esiti del checker o classificazioni degli errori.

CSV e JSON sono supportati. Per YAML/Excel, esportare in CSV/JSON oppure aggiungere
un adattatore dopo aver esaminato il formato effettivo; non sono necessarie librerie
aggiuntive nel programma. I file originali possono restare in una cartella separata.
I CSV devono usare virgole e punto decimale; JSON usa numeri nativi.

Il codice è stato verificato sintatticamente. L'esecuzione dei test numerici e il
controllo visivo dei grafici non sono stati completati nell'ambiente iniziale:
le dipendenze non erano installate e il download non è stato autorizzato.
I comandi sotto consentono di completare queste verifiche.

## Installazione ed esecuzione

Python 3.10 o successivo:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_benchmark_plots.py --help
.venv/bin/python scripts/generate_benchmark_plots.py
```

Inserire i CSV/JSON in `benchmark_results/` anche in sottocartelle. Nessun dato
sintetico viene usato automaticamente quando l'input reale è vuoto.

```sh
.venv/bin/python scripts/generate_benchmark_plots.py --input benchmark_results --output benchmark_plots --format png pdf
.venv/bin/python scripts/generate_benchmark_plots.py --model 'nome esatto' --category 'categoria reale' --scenario 'lab01' --analysis prompt labs dns
.venv/bin/python scripts/generate_benchmark_plots.py --mapping mapping.example.json
.venv/bin/python -m unittest discover -s tests -v
```

I filtri `--model`, `--category`, `--scenario` sono ripetibili; fra filtri diversi
si applica l'intersezione. Le scelte di `--analysis` sono mostrate da `--help`.
Exit code 2 segnala input assente/non utilizzabile o configurazione non valida;
il fallimento di un grafico è registrato senza interrompere le altre analisi.
Il codice 0 indica esecuzioni caricate, non che ogni grafico sia stato prodotto.

## Contratto delle esecuzioni

Una riga = un'esecuzione di una formulazione di uno scenario con un modello.
La chiave unica è **scenario, prompt, model, run_id**. `run_id` identifica la
ripetizione e può essere riutilizzato in scenari/prompt/modelli differenti.
Lo stesso scenario funzionale deve mantenere lo stesso `scenario` per tutti i
prompt. Identificatori ambigui duplicati vengono esclusi, comprese tutte le copie.
Distinguere run reali diversi con ID diversi; non duplicare un risultato aggregato
come se fosse una nuova esecuzione.

| Campo | Significato |
|---|---|
| `scenario`, `prompt`, `model`, `run_id` | Identificatori obbligatori, testo |
| `prompt` | Valori consigliati: `sintetico`, `intermedio`, `dettagliato`, `json`, `yaml`; altri nomi mantenuti senza inferenze |
| `passed_tests` | Intero non negativo: controlli superati |
| `evaluated_tests` | Intero non negativo: **solo pass + fail** |
| `expected_tests` | Numero di controlli previsti, se noto |
| `completed` | Booleano JSON oppure testo `true`/`false`; attestazione esplicita di valutazione completata |
| `category` | Categoria reale del progetto, facoltativa; nessuna categoria ricavata dal nome del laboratorio |
| `generation_seconds`, `benchmark_seconds`, `validation_seconds`, `total_seconds` | Tempi in secondi, facoltativi; non sommati, possono sovrapporsi |
| `input_tokens`, `output_tokens`, `total_tokens` | Interi non negativi, facoltativi; nessuna deduzione di costi monetari |
| `routers`, `devices`, `dns_zones`, `delegations`, `records`, `resolvers` | Metadati di complessità interi, facoltativi |

Esempio di **formato**, non risultato reale:

```csv
scenario,prompt,model,run_id,passed_tests,evaluated_tests,expected_tests,completed,category
lab01,json,modelloA,r1,8,10,10,true,categoria_definita_dal_progetto
```

I metadati si inseriscono nelle righe delle esecuzioni. Categoria e complessità
incoerenti per lo stesso scenario sono segnalate e ignorate per quel campo.
Le categorie non presenti non vengono sostituite con etichette inventate.
Il programma non ricava topologia o complessità da nomi o testi liberi.

## Contratto dei controlli dettagliati (facoltativo)

Un secondo file `checks.csv` o JSON può fornire una riga per controllo.
Obbligatori: la chiave dell'esecuzione, `check_id`, `check_type`, `outcome`.
`check_id` deve essere unico all'interno dell'esecuzione.

```csv
scenario,prompt,model,run_id,check_id,check_type,outcome
lab01,json,modelloA,r1,c1,DNSAuthorityCheck,pass
lab01,json,modelloA,r1,c2,DNSRecordCheck,fail
lab01,json,modelloA,r1,c3,ReachabilityCheck,error
```

Gli unici esiti normalizzati sono `pass`, `fail`, `error`, `skipped`.
`error` indica un impedimento all'esecuzione del controllo; `fail` un controllo
eseguito con esito negativo. Altri esiti restano `unknown` e vengono conteggiati
separatamente. Occorre tradurre esplicitamente gli esiti dei report reali nel
formato documentato: il programma non indovina cosa significhino numeri o stringhe.
Non deduce errori IP, deleghe o resolver da un generico controllo DNS fallito.
Gli errori infrastrutturali senza test valutati restano esecuzioni senza score;
la loro origine non può essere classificata senza metadati espliciti.

I conteggi dettagliati devono contenere **tutti i controlli** dell'esecuzione,
non solo i fallimenti. Se contraddicono i conteggi aggregati, lo score della
relativa esecuzione è escluso e l'anomalia viene registrata. In assenza di conteggi
aggregati vengono calcolati dai dettagli; questi ultimi da soli non attestano
la completezza del laboratorio. Controlli senza esecuzione corrispondente non
sono inclusi se è presente una tabella delle esecuzioni.

Analisi DNS: riconosce esattamente `DNSAuthorityCheck`, `LocalNSCheck`,
`DNSRecordCheck`. I controlli personalizzati richiedono `component=dns` assegnato
esplicitamente sulla base del report/configurazione: non viene analizzato
arbitrariamente il testo di `custom_commands`.

## Importazione di campi con nomi differenti

`mapping.example.json` mostra l'importazione esplicita tramite glob di percorso,
tipo `runs`/`checks`, percorso della lista in JSON e mappa
**nome canonico → campo sorgente**. La configurazione va adattata ai propri report.
Le regole devono essere disgiunte; un file con più regole viene escluso.
Con una configurazione presente, i file non corrispondenti sono ignorati.
I JSON annidati vengono appiattiti (`metrics.passed`); `records_path` seleziona
una lista dentro un oggetto JSON. Non sono supportati indici di array nel percorso.
Senza mappatura, un file con `check_id` è una tabella controlli; gli altri sono
esecuzioni. Servono i nomi canonici sopra indicati.

## Metodologia

- Percentuale controlli = superati / valutati. Denominatore zero o conteggi mancanti/non validi producono dati mancanti.
- Macro = media delle ripetizioni per scenario, poi media degli scenari con score noto nel gruppo. Gli scenari hanno uguale peso.
- Micro = somma controlli superati / somma controlli valutati nelle esecuzioni con score noto.
- Successo completo = tutti i controlli superati, `completed=true`, nessuna omissione/errore noto e, se noto, numero previsto uguale a quello valutato. Con valutazione completa, un controllo fallito produce successo completo pari a zero.
- Esecuzioni incomplete, saltate o infrastrutturalmente bloccate non sono imputate come successi o fallimenti completi. Si riportano le numerosità: il successo calcolato solo sui casi completi può essere selettivo e va letto insieme agli esiti non determinabili.
- Confronto modelli: solo coppie scenario/prompt comuni con risultati valutabili. Nessuna coppia comune significa nessun grafico comparativo. Numeri di ripetizioni differenti sono segnalati, non automaticamente bilanciati.
- Le statistiche sono descrittive. `macro_scenario_sd` descrive la variabilità fra scenari; `mean_within_scenario_sd` la media delle deviazioni standard delle ripetizioni. Non sono intervalli di confidenza. Non si assume indipendenza fra formulazioni e ripetizioni.
- Le aggregazioni per prompt accorpano i modelli presenti; se i campioni sono diversi, non dimostrano l'effetto isolato della formulazione. Usare il filtro modello e scenari comuni per approfondire.
- La Skill è parte del processo: non è possibile stimarne un effetto causale rispetto a un'esecuzione senza Skill da questi soli dati.

## Analisi e domande affrontate

| Directory | Domanda e grafico |
|---|---|
| `01_successo_prompt` | Quali formulazioni mostrano successo maggiore nel campione? Barre distinte per successo completo, controlli macro e micro; scenari/esecuzioni indicati |
| `02_modelli` | Come differiscono i modelli sugli stessi scenari/formulazioni? Barre raggruppate sul campione comune |
| `03_laboratori` | Quali scenari hanno score più basso, per prompt e modello? Heatmap paginate ogni 25 scenari, scala fissa 0–100, grigio per dati mancanti |
| `04_categorie` | Come varia il successo fra categorie reali? Barre macro per prompt, separate per modello |
| `05_distribuzioni` | Quanto variano gli score osservati? Boxplot per modello/prompt con almeno 5 valori non costanti |
| `06_errori` | Quali tipi di controllo accumulano fallimenti, errori o omissioni? Barre orizzontali e tassi di fallimento nel CSV |
| `07_dns` | Quali componenti DNS hanno più controlli falliti? Barre micro per tipo/prompt e heatmap per scenario |
| `08_tempi` | Come variano i tempi disponibili? Boxplot separati per metrica, modello/prompt |
| `09_token` | Quanto variano i token e come si associano allo score? Boxplot e scatter, nessuna interpretazione causale |
| `10_scalabilita` | Come si associa la complessità allo score? Scatter separati, medie delle ripetizioni per scenario/modello/prompt |

Non vengono prodotte linee temporali: non esiste un asse temporale verificato.
Le variabili di complessità sono visualizzate come scatter senza interpolare
un andamento non dimostrato. Nessun boxplot per gruppi piccoli o costanti.
I motivi delle esclusioni sono registrati. Nessun grafico a torta, 3D o Seaborn.
I PNG sono a 300 DPI, i PDF vettoriali, con etichette prevalentemente italiane.
I nomi tecnici delle metriche restano visibili per risalire ai campi sorgenti.

## Artefatti e aggiornamenti

- `summary.csv`: più livelli identificati da `aggregation`; non sommare righe di livelli differenti. Rapporti in [0,1], conteggi espliciti di scenari/esecuzioni/test/esiti completi noti.
- `summary.md`: risultati descrittivi per prompt, limiti metodologici e registro delle esclusioni.
- `generation_log.txt`: file letti, anomalie, grafici prodotti, esclusioni.
- `model_comparison.csv`: sole aggregazioni usate dal confronto su campione comune.
- `errors_summary.csv`, `dns_summary.csv`: conteggi e tassi per modello/prompt/tipo, quando disponibili.

Rieseguire lo stesso comando dopo aver aggiunto risultati con ID univoci.
I file originali sono letti senza modifiche. L'output deve essere dedicato e
distinto dall'input. I grafici con lo stesso nome vengono aggiornati; eventuali
vecchi grafici non più applicabili **restano sul disco**: il registro corrente
elenca quelli prodotti dall'ultima esecuzione. Per consegne della tesi usare
una nuova cartella `--output` e verificarne i grafici.

## Verifica con dati esclusivamente sintetici

`fixtures/synthetic/` è separata dai dati reali e contiene scenari, modelli e
categorie esplicitamente fittizi (240 esecuzioni, 1.920 controlli). Il generatore
ha seed fisso, usa solo la libreria standard e non scrive nella cartella reale.

```sh
python3 fixtures/synthetic/generate.py
.venv/bin/python scripts/generate_benchmark_plots.py --input fixtures/synthetic --output synthetic_plots
.venv/bin/python -m unittest discover -s tests -v
```

I test coprono macro/micro, peso delle ripetizioni, completezza, conteggi invalidi,
controlli non eseguiti, discrepanze fra report, duplicati, metadati incoerenti,
mappatura JSON, file corrotti, input vuoto, input immutato, export PNG/PDF e
confronto modelli limitato al campione comune. Aprire inoltre alcuni PNG/PDF
per verificare etichette, legende e heatmap con i nomi reali dei laboratori.
=======
# Kathara-Benchmark-Analytics
Python-based analytics and visualization framework for Kathara-Skill-LLM benchmark results, using Pandas and Matplotlib to evaluate LLM performance, DNS configuration accuracy, execution efficiency, and Skill effectiveness.
>>>>>>> e69840388b1fb34357b9ca8259f5457e1118b2d6
