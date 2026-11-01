# Dove incollare i dati

Copia in questa cartella i file esportati da **Kathara-Skill-LLM/results/**:

- `runs.csv` — obbligatorio; una riga per run con modalità Skill, prompt, tempi, token, temperatura e controlli aggregati.
- `checks.csv` — obbligatorio; un record per singolo controllo del checker.
- `summary.csv` — facoltativo: il programma non lo ricalcola né lo usa nei punteggi, per evitare doppie aggregazioni.

**Non rinominare i file**. Dopo la copia, torna nella directory principale ed esegui `python3 genera_grafici.py` (prima installa le dipendenze da `requirements.txt`). Le figure e i CSV riepilogativi compariranno in `grafici/`.

I file sorgenti non vengono alterati. I risultati del benchmark non vanno confusi con `fixtures/synthetic/`, che contiene dati fittizi.
