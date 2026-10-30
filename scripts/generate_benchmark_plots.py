#!/usr/bin/env python3
"""Grafici descrittivi Kathara: contratto di ingresso e metodologia in README.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

os.environ.setdefault('MPLCONFIGDIR', '/tmp/kathara-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KEY = ['scenario', 'prompt', 'model', 'run_id']
PROMPTS = ['sintetico', 'intermedio', 'dettagliato', 'json', 'yaml']
LABELS = dict(zip(PROMPTS, ['Sintetico', 'Intermedio', 'Dettagliato', 'JSON', 'YAML']))
FOLDERS = dict(zip(['prompt', 'models', 'labs', 'categories', 'distribution', 'errors',
                    'dns', 'time', 'tokens', 'complexity'],
                  ['01_successo_prompt', '02_modelli', '03_laboratori', '04_categorie',
                   '05_distribuzioni', '06_errori', '07_dns', '08_tempi', '09_token', '10_scalabilita']))
TIMES = ['generation_seconds', 'benchmark_seconds', 'validation_seconds', 'total_seconds']
TOKENS = ['input_tokens', 'output_tokens', 'total_tokens']
COMPLEXITY = ['routers', 'devices', 'dns_zones', 'delegations', 'records', 'resolvers', 'expected_tests']
DNS = {'DNSAuthorityCheck', 'LocalNSCheck', 'DNSRecordCheck'}
COLORS = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9']


def number(value: Any) -> float:
    """Numeri finiti non negativi; i valori non validi restano mancanti."""
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 and not isinstance(value, (bool, np.bool_)) else np.nan
    except (TypeError, ValueError):
        return np.nan


def boolean(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    return pd.NA


def read_records(path: Path, mapping: dict) -> pd.DataFrame:
    """Legge solo formati espliciti; nessuna deduzione dello schema del checker."""
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path, dtype=str)
    elif path.suffix.lower() == '.json':
        obj = json.loads(path.read_text(encoding='utf-8'))
        for part in mapping.get('records_path', '').split('.'):
            if part:
                obj = obj[part]
        if not isinstance(obj, list) or not all(isinstance(x, dict) for x in obj):
            raise ValueError('JSON: attesa lista di oggetti; configurare records_path')
        df = pd.json_normalize(obj)
    else:
        raise ValueError('formato supportato: CSV o JSON')
    # Mapping: campo canonico -> campo effettivo (anche percorso JSON appiattito).
    columns = mapping.get('columns', {})
    missing = set(columns.values()) - set(df.columns)
    if missing:
        raise ValueError(f'campi della mappatura assenti: {sorted(missing)}')
    return df.rename(columns={v: k for k, v in columns.items()})


def load_data(source: Path, config: dict, log: list[str], excluded: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted(source.rglob('*')) if source.is_dir() else [source]
    buckets: dict[str, list[pd.DataFrame]] = {'runs': [], 'checks': []}
    for path in files:
        if not path.is_file() or path.suffix.lower() not in {'.csv', '.json'}:
            continue
        if excluded == path.resolve() or excluded in path.resolve().parents:
            continue
        matches = [s for s in config.get('sources', []) if path.match(s['glob'])]
        if config.get('sources') and not matches:
            continue
        if len(matches) > 1:
            log.append(f'ESCLUSO {path}: più mappature applicabili')
            continue
        spec = matches[0] if matches else {}
        try:
            df = read_records(path, spec)
            kind = spec.get('kind', 'checks' if 'check_id' in df.columns else 'runs')
            if kind not in buckets:
                raise ValueError(f'kind non valido: {kind}')
            missing = set(KEY) - set(df.columns)
            if missing:
                raise ValueError(f'identificatori obbligatori mancanti: {sorted(missing)}')
            df['_source'] = str(path)
            buckets[kind].append(df)
            log.append(f'LETTO {path}: {len(df)} righe ({kind})')
        except (ValueError, KeyError, OSError, TypeError) as exc:
            log.append(f'ESCLUSO {path}: {exc}')
    return tuple(pd.concat(buckets[k], ignore_index=True) if buckets[k] else pd.DataFrame()
                 for k in ['runs', 'checks'])


def validate_keys(df: pd.DataFrame, keys: list[str], log: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    valid = pd.Series(True, index=df.index)
    for k in keys:
        if k not in df:
            log.append(f'ESCLUSO dataset: manca {k}')
            return pd.DataFrame()
        df[k] = df[k].astype('string').str.strip()
        valid &= df[k].notna() & df[k].ne('')
    log.append(f'Identificatori mancanti: {int((~valid).sum())} righe escluse')
    df = df.loc[valid].copy()
    dup = df.duplicated(keys, keep=False)
    if dup.any():
        log.append(f'Identificatori duplicati: {int(dup.sum())} righe ambigue escluse (tutte le copie)')
    return df.loc[~dup].copy()


def normalize(runs: pd.DataFrame, checks: pd.DataFrame, log: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa controlli valutati, errori e omissioni; non imputa risultati."""
    checks = validate_keys(checks.copy(), KEY + ['check_id'], log)
    if not checks.empty:
        if not {'outcome', 'check_type'} <= set(checks):
            log.append('Controlli esclusi: mancano outcome o check_type')
            checks = pd.DataFrame()
        else:
            checks['outcome'] = checks['outcome'].astype('string').str.lower().str.strip()
            bad = ~checks['outcome'].isin(['pass', 'fail', 'error', 'skipped'])
            log.append(f'Esiti controlli sconosciuti: {int(bad.sum())}; conservati come unknown')
            checks.loc[bad, 'outcome'] = 'unknown'
    if runs.empty:
        log.append('Nessun record esecuzione: i controlli da soli non attestano completezza del laboratorio')
        runs = checks[KEY].drop_duplicates().copy() if not checks.empty else pd.DataFrame(columns=KEY)
    runs = validate_keys(runs.copy(), KEY, log)
    for col in ['passed_tests', 'evaluated_tests', *TIMES, *TOKENS, *COMPLEXITY]:
        if col not in runs:
            runs[col] = np.nan
        raw = runs[col]
        runs[col] = raw.map(number)
        if col not in TIMES:
            runs.loc[runs[col].mod(1).ne(0), col] = np.nan
        bad = raw.notna() & runs[col].isna()
        if bad.any():
            log.append(f'{col}: {int(bad.sum())} valori non validi ignorati')
    if 'completed' not in runs:
        runs['completed'] = pd.NA
    runs['completed'] = runs['completed'].map(boolean).astype('boolean')
    if 'category' not in runs:
        runs['category'] = pd.NA
    # Categoria e metadati di scenario devono essere stabili tra ripetizioni e prompt.
    for col in ['category', *COMPLEXITY]:
        ambiguous = runs.groupby('scenario')[col].nunique().gt(1)
        names = ambiguous[ambiguous].index
        if len(names):
            log.append(f'{col}: metadati incoerenti per {list(names)}; esclusi dalle analisi relative')
            runs.loc[runs.scenario.isin(names), col] = pd.NA if col == 'category' else np.nan
    if not checks.empty:
        old_count = len(checks)
        checks = checks.merge(runs[KEY], on=KEY, how='inner', validate='many_to_one')
        log.append(f'Controlli senza esecuzione valida corrispondente: {old_count-len(checks)} esclusi')
        counts = checks.assign(
            _passed=checks.outcome.eq('pass').astype(int),
            _evaluated=checks.outcome.isin(['pass', 'fail']).astype(int),
            _error=checks.outcome.eq('error').astype(int),
            _unresolved=checks.outcome.isin(['error', 'skipped', 'unknown']).astype(int),
        ).groupby(KEY)[['_passed', '_evaluated', '_error', '_unresolved']].sum().reset_index()
        runs = runs.merge(counts, on=KEY, how='left', validate='one_to_one')
        mismatch = pd.Series(False, index=runs.index)
        for col, detail in [('passed_tests', '_passed'), ('evaluated_tests', '_evaluated')]:
            mismatch |= runs[col].notna() & runs[detail].notna() & runs[col].ne(runs[detail])
            runs[col] = runs[col].fillna(runs[detail])
        log.append(f'Conteggi aggregati/dettagliati incoerenti: {int(mismatch.sum())}; metriche escluse')
        runs.loc[mismatch, ['passed_tests', 'evaluated_tests']] = np.nan
    else:
        runs['_unresolved'] = 0
        runs['_error'] = 0
    invalid = runs.passed_tests.gt(runs.evaluated_tests) | runs.evaluated_tests.gt(runs.expected_tests)
    log.append(f'Conteggi impossibili: {int(invalid.sum())}; metriche escluse')
    runs.loc[invalid, ['passed_tests', 'evaluated_tests']] = np.nan
    runs['test_rate'] = runs.passed_tests.div(runs.evaluated_tests.where(runs.evaluated_tests.gt(0)))
    # La dichiarazione completed è richiesta: una frazione 100% non prova completezza.
    known = runs.completed.fillna(False) & runs.test_rate.notna() & runs['_unresolved'].fillna(0).eq(0)
    known &= runs.expected_tests.isna() | runs.expected_tests.eq(runs.evaluated_tests)
    runs['full_success'] = np.where(known, runs.passed_tests.eq(runs.evaluated_tests).astype(float), np.nan)
    log.append(f'Esecuzioni con successo completo non determinabile: {int(runs.full_success.isna().sum())}')
    return runs, checks


def aggregate(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    """Macro: prima media ripetizioni di ciascuno scenario, poi media scenari."""
    rows = []
    for name, g in df.groupby(groups, dropna=False, sort=True):
        names = name if isinstance(name, tuple) else (name,)
        valid = g[g.test_rate.notna()]
        complete = g[g.full_success.notna()]
        scenario_rates = valid.groupby('scenario').test_rate.mean()
        full = complete.groupby('scenario').full_success.mean()
        n = valid.evaluated_tests.sum()
        rows.append(dict(zip(groups, names), scenarios=g.scenario.nunique(), runs=len(g),
                         scored_runs=len(valid), scored_scenarios=len(scenario_rates),
                         evaluated_tests=n, passed_tests=valid.passed_tests.sum(),
                         macro_rate=scenario_rates.mean(), micro_rate=valid.passed_tests.sum()/n if n else np.nan,
                         full_success_rate=full.mean(), full_known_runs=len(complete),
                         full_success_runs=complete.full_success.sum(),
                         macro_scenario_sd=scenario_rates.std(),
                         mean_within_scenario_sd=valid.groupby('scenario').test_rate.std().mean()))
    return pd.DataFrame(rows)


def safe_name(value: Any) -> str:
    label = re.sub(r'[^\w.-]+', '_', str(value)).strip('_')[:80] or 'dato'
    return label + '_' + hashlib.sha256(str(value).encode()).hexdigest()[:8]


class Plotter:
    def __init__(self, out: Path, formats: list[str], log: list[str]):
        self.out, self.formats, self.log = out, formats, log
        self.count = 0
        plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                             'axes.facecolor': 'white', 'figure.facecolor': 'white',
                             'axes.prop_cycle': matplotlib.cycler(color=COLORS), 'pdf.fonttype': 42})

    def save(self, fig, kind: str, name: str):
        folder = self.out / FOLDERS[kind]
        folder.mkdir(parents=True, exist_ok=True)
        try:
            for ext in self.formats:
                target = folder / f'{name}.{ext}'
                fig.savefig(target, dpi=300, bbox_inches='tight')
                self.log.append(f'GENERATO {target}')
            self.count += 1
        finally:
            plt.close(fig)

    def bars(self, table: pd.DataFrame, kind: str, name: str, title: str, ylabel='Percentuale (%)'):
        if table.empty or not table.notna().any().any():
            return
        originals = list(table.columns)
        table = table.rename(index=LABELS, columns=LABELS)
        fig, ax = plt.subplots(figsize=(max(7, len(table)*1.1), 4.8), layout='constrained')
        # Posizioni manuali: le combinazioni mancanti restano vuote, mai barre a zero.
        width = .8 / max(1, len(table.columns))
        x = np.arange(len(table))
        for i, col in enumerate(table):
            vals = table[col].to_numpy(dtype=float)
            original = originals[i]
            color_index = PROMPTS.index(original) if original in PROMPTS else i
            ax.bar(x - .4 + width*(i+.5), vals, width, label=str(col), color=COLORS[color_index % len(COLORS)])
        ax.set_xticks(x, table.index, rotation=25, ha='right')
        ax.set(title=title, ylabel=ylabel)
        if ylabel == 'Percentuale (%)':
            ax.set_ylim(0, 105)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(fontsize=8, loc='upper left', bbox_to_anchor=(1.01, 1))
        self.save(fig, kind, name)

    def heatmap(self, table: pd.DataFrame, kind: str, name: str, title: str):
        # Paginazione: leggibile anche con molti laboratori.
        for offset in range(0, len(table), 25):
            part = table.iloc[offset:offset+25]
            fig, ax = plt.subplots(figsize=(8, max(4, len(part)*.36)), layout='constrained')
            cmap = plt.get_cmap('viridis').copy()
            cmap.set_bad('#dddddd')
            im = ax.imshow(np.ma.masked_invalid(part.to_numpy(float)), vmin=0, vmax=100, cmap=cmap, aspect='auto')
            ax.set_xticks(range(len(part.columns)), [LABELS.get(x, x) for x in part.columns], rotation=25, ha='right')
            ax.set_yticks(range(len(part)), part.index)
            ax.set_title(title + '\nGrigio: dati mancanti')
            for y in range(len(part)):
                for x in range(len(part.columns)):
                    v = part.iloc[y, x]
                    ax.text(x, y, '—' if pd.isna(v) else f'{v:.0f}', ha='center', va='center',
                            fontsize=8, color='white' if pd.notna(v) and v < 55 else 'black')
            fig.colorbar(im, ax=ax, label='Controlli superati (%)')
            self.save(fig, kind, f'{name}_{offset//25+1:02d}')

    def box(self, df: pd.DataFrame, column: str, kind: str, title: str, unit: str):
        groups = [(f'{model} / {LABELS.get(prompt, prompt)}', g[column].dropna().to_numpy())
                  for (model, prompt), g in df.groupby(['model', 'prompt'])]
        groups = [(label, values) for label, values in groups if len(values) >= 5 and np.ptp(values) > 0]
        if not groups:
            self.log.append(f'ESCLUSO {kind}/{column}: servono ≥5 valori non costanti per gruppo modello/prompt')
            return
        fig, ax = plt.subplots(figsize=(max(7, len(groups)*.9), 5), layout='constrained')
        ax.boxplot([g[1] for g in groups], tick_labels=[g[0] + f' (n={len(g[1])})' for g in groups], patch_artist=True,
                   boxprops={'facecolor': COLORS[0], 'alpha': .6})
        ax.tick_params(axis='x', rotation=35)
        ax.set(title=title + '\nDistribuzione delle esecuzioni osservate', ylabel=unit)
        ax.grid(axis='y', alpha=.2)
        self.save(fig, kind, column)

    def scatter(self, df: pd.DataFrame, column: str, kind: str, unit: str):
        # Un punto per scenario/modello/prompt, con ripetizioni mediate.
        data = df.groupby(['scenario', 'model', 'prompt'])[[column, 'test_rate']].mean().dropna()
        if len(data) < 3 or data[column].nunique() < 2:
            self.log.append(f'ESCLUSO {kind}/{column}: coppie numeriche insufficienti o ascissa costante')
            return
        fig, ax = plt.subplots(figsize=(7, 4.8), layout='constrained')
        models = list(data.index.get_level_values('model').unique())
        for (model, prompt), g in data.groupby(['model', 'prompt']):
            color_index = PROMPTS.index(prompt) if prompt in PROMPTS else 0
            marker = ['o', 's', '^', 'D', 'v', 'P', 'X'][models.index(model) % 7]
            ax.scatter(g[column], 100*g.test_rate, alpha=.65, color=COLORS[color_index], marker=marker,
                       label=f'{model} / {LABELS.get(prompt, prompt)}')
        ax.set(xlabel=f'{column} ({unit})', ylabel='Controlli superati (%)', ylim=(-3, 103),
               title='Relazione osservata con il successo\nMedie per scenario; nessuna interpretazione causale')
        ax.legend(fontsize=7, bbox_to_anchor=(1.01, 1))
        ax.grid(alpha=.2)
        self.save(fig, kind, column + '_successo')


def prompt_order(columns) -> list:
    return [x for x in PROMPTS if x in columns] + sorted(set(columns) - set(PROMPTS))


def generate(kind: str, runs: pd.DataFrame, checks: pd.DataFrame, p: Plotter):
    """Ogni analisi è isolata: un errore grafico non interrompe le altre."""
    if kind == 'prompt':
        a = aggregate(runs, ['prompt']).set_index('prompt')
        a = a.reindex(prompt_order(a.index))
        table = a[['full_success_rate', 'macro_rate', 'micro_rate']]*100
        table.columns = ['Successo completo (macro)', 'Controlli: macro scenari', 'Controlli: micro test']
        table.index = [f'{LABELS.get(x, x)}\nS={int(a.loc[x, "scenarios"])}; R={int(a.loc[x, "runs"])}' for x in table.index]
        p.bars(table, kind, 'successo_prompt', 'Successo per prompt — campione osservato\nS: scenari; R: esecuzioni (numerosità per metrica in summary.csv)')
    elif kind == 'models':
        if runs.model.nunique() < 2:
            p.log.append('ESCLUSO models: presente meno di due modelli')
            return
        sets = [set(zip(g.scenario, g.prompt)) for _, g in runs[runs.test_rate.notna()].groupby('model')]
        if len(sets) != runs.model.nunique():
            p.log.append('ESCLUSO models: un modello non ha risultati valutabili')
            return
        common = set.intersection(*sets)
        p.log.append(f'Confronto modelli: {len(common)} coppie scenario/prompt comuni; campioni originari {[len(s) for s in sets]}; confronto descrittivo, ripetizioni non necessariamente bilanciate')
        if not common:
            p.log.append('ESCLUSO models: nessuna coppia scenario/prompt comune')
            return
        selected = runs[[pair in common for pair in zip(runs.scenario, runs.prompt)]]
        a = aggregate(selected, ['model', 'prompt'])
        a.to_csv(p.out / 'model_comparison.csv', index=False)
        p.bars(a.pivot(index='model', columns='prompt', values='macro_rate')*100, kind,
               'modelli_campione_comune', 'Modelli: media macro dei controlli\nSolo coppie scenario/prompt comuni')
    elif kind == 'labs':
        for model, g in runs.groupby('model'):
            table = g.pivot_table(index='scenario', columns='prompt', values='test_rate', aggfunc='mean')*100
            if not table.empty:
                p.heatmap(table.reindex(columns=prompt_order(table.columns)), kind, safe_name(model), f'{model}: controlli superati, media ripetizioni')
    elif kind == 'categories':
        data = runs.dropna(subset=['category'])
        for model, g in data.groupby('model'):
            a = aggregate(g, ['category', 'prompt'])
            p.bars(a.pivot(index='category', columns='prompt', values='macro_rate')*100, kind,
                   safe_name(model), f'{model}: media macro per categoria\nCampioni osservati; numerosità in summary.csv')
    elif kind == 'distribution':
        p.box(runs.assign(test_percent=100*runs.test_rate), 'test_percent', kind,
              'Variabilità dei controlli superati', 'Controlli superati (%)')
    elif kind in ['errors', 'dns']:
        if checks.empty:
            p.log.append(f'ESCLUSO {kind}: report dettagliati dei controlli assenti')
            return
        data = checks.copy()
        data['evaluated'] = data.outcome.isin(['pass', 'fail']).astype(int)
        data['failed'] = data.outcome.eq('fail').astype(int)
        data['passed'] = data.outcome.eq('pass').astype(int)
        data['execution_error'] = data.outcome.eq('error').astype(int)
        data['skipped'] = data.outcome.eq('skipped').astype(int)
        data['unknown'] = data.outcome.eq('unknown').astype(int)
        if kind == 'dns':
            explicit = data.get('component', pd.Series('', index=data.index)).eq('dns')
            data = data[data.check_type.isin(DNS) | explicit]
        if data.empty:
            p.log.append(f'ESCLUSO {kind}: nessun controllo classificato disponibile')
            return
        a = data.groupby(['model', 'prompt', 'check_type'])[['evaluated', 'failed', 'passed', 'execution_error', 'skipped', 'unknown']].sum().reset_index()
        a['pass_rate'] = a.passed / a.evaluated.where(a.evaluated.gt(0))
        a['failure_rate'] = a.failed / a.evaluated.where(a.evaluated.gt(0))
        a.to_csv(p.out / f'{kind}_summary.csv', index=False)
        for model, g in a.groupby('model'):
            if kind == 'dns':
                p.bars(g.pivot(index='check_type', columns='prompt', values='pass_rate')*100,
                       kind, safe_name(model), f'{model}: componenti DNS\nQuota micro dei controlli valutati')
                selected = data[data.model.eq(model) & data.outcome.isin(['pass', 'fail'])]
                if not selected.empty:
                    table = selected.pivot_table(index='scenario', columns='prompt', values='passed', aggfunc='mean')*100
                    p.heatmap(table, kind, safe_name(model) + '_laboratori', f'{model}: controlli DNS, quota micro')
            else:
                counts = g.groupby('check_type')[['failed', 'execution_error', 'skipped', 'unknown']].sum()
                counts = counts.loc[counts.sum(axis=1).sort_values().index]
                if counts.sum().sum() == 0:
                    p.log.append(f'ESCLUSO errors/{model}: nessun fallimento, errore od omissione')
                    continue
                fig, ax = plt.subplots(figsize=(8, max(4, len(counts)*.5)), layout='constrained')
                left = np.zeros(len(counts))
                for col, label, color in zip(counts, ['Controlli falliti', 'Errori di esecuzione', 'Non eseguiti', 'Esito sconosciuto'], COLORS):
                    ax.barh(counts.index, counts[col], left=left, label=label, color=color)
                    left += counts[col].to_numpy()
                ax.set(title=f'{model}: esiti per tipo di controllo', xlabel='Numero di controlli')
                ax.legend(fontsize=8, bbox_to_anchor=(1.01, 1))
                p.save(fig, kind, safe_name(model))
    elif kind == 'time':
        for col in TIMES:
            p.box(runs, col, kind, col.replace('_', ' '), 'Tempo (s)')
    elif kind == 'tokens':
        for col in TOKENS:
            p.box(runs, col, kind, col.replace('_', ' '), 'Token (numero)')
            p.scatter(runs, col, kind, 'token')
    elif kind == 'complexity':
        for col in COMPLEXITY:
            p.scatter(runs, col, kind, 'numero')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--input', type=Path, default=Path('benchmark_results'), help='File CSV/JSON o directory ricorsiva')
    parser.add_argument('--output', type=Path, default=Path('benchmark_plots'), help='Directory dedicata degli artefatti')
    parser.add_argument('--mapping', type=Path, help='Configurazione JSON: glob, kind, records_path, columns')
    parser.add_argument('--format', nargs='+', choices=['png', 'pdf'], default=['png', 'pdf'], help='Formati di esportazione (PNG 300 DPI)')
    for key in ['model', 'category', 'scenario']:
        parser.add_argument('--' + key, action='append', help='Filtro esatto, ripetibile')
    parser.add_argument('--analysis', nargs='+', choices=['all', *FOLDERS], default=['all'], help='Analisi selezionate')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    log: list[str] = []
    if not args.input.exists():
        print(f'Input inesistente: {args.input}')
        return 2
    # Impedisce di sovrascrivere un input con nomi riservati agli output.
    if args.output.resolve() == args.input.resolve() or args.output.resolve() in args.input.resolve().parents:
        print('Output deve essere una directory dedicata distinta dall’input e dai suoi antenati.')
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        config = json.loads(args.mapping.read_text()) if args.mapping else {}
        runs, checks = load_data(args.input, config, log, args.output.resolve())
        runs, checks = normalize(runs, checks, log)
        for col in ['model', 'category', 'scenario']:
            values = getattr(args, col)
            if values:
                runs = runs[runs[col].isin(values)]
        if not checks.empty:
            checks = checks.merge(runs[KEY], on=KEY, how='inner', validate='many_to_one')
        tables = []
        if not runs.empty:
            for groups in [['prompt'], ['model', 'prompt'], ['model', 'category', 'prompt'], ['model', 'scenario', 'prompt']]:
                data = runs.dropna(subset=groups)
                if not data.empty:
                    a = aggregate(data, groups)
                    a.insert(0, 'aggregation', '+'.join(groups))
                    tables.append(a)
        summary = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame(columns=['aggregation', 'scenarios', 'runs', 'macro_rate', 'micro_rate', 'full_success_rate'])
        summary.to_csv(args.output / 'summary.csv', index=False)
        p = Plotter(args.output, list(dict.fromkeys(args.format)), log)
        for kind in FOLDERS:
            (args.output / FOLDERS[kind]).mkdir(exist_ok=True)
            if 'all' not in args.analysis and kind not in args.analysis:
                log.append(f'ESCLUSO {kind}: analisi non richiesta')
                continue
            if runs.empty:
                log.append(f'ESCLUSO {kind}: nessuna esecuzione utilizzabile')
                continue
            before = p.count
            try:
                generate(kind, runs, checks, p)
                if before == p.count:
                    log.append(f'ESCLUSO {kind}: dati assenti o insufficienti; dettagli nelle voci precedenti')
            except Exception as exc:
                plt.close('all')
                log.append(f'ERRORE grafico {kind}: {type(exc).__name__}: {exc}')
        description = [
            '# Analisi descrittiva del benchmark Kathara con Skill', '',
            f'Input: `{args.input}`. Scenari: {runs.scenario.nunique()}; esecuzioni: {len(runs)}; figure: {p.count}.',
            'Le cinque formulazioni sono collegate dal campo scenario. I gruppi possono avere campioni differenti.',
            'Un risultato del 100% sui controlli valutati non attesta da solo il successo completo.',
            'Successo completo: completed=true, conteggi coerenti, nessun controllo omesso/errore noto e tutti i test superati.',
            'Esecuzioni incomplete: frazione dei controlli osservati disponibile; successo completo non determinato.',
            'Macro: media delle ripetizioni per scenario, poi media degli scenari. Micro: totale superati / totale valutati.',
            'Le percentuali nel CSV sono frazioni [0,1]. Il denominatore del successo completo comprende solo esecuzioni con esito completo noto.',
            'full_success_rate assegna uguale peso agli scenari con esito completo noto. full_success_runs conta le esecuzioni riuscite.',
            'I controlli skipped/error/unknown non appartengono al denominatore dei test valutati.',
            'Errori e DNS: tassi micro, separati per modello/prompt/tipo di controllo; nessuna causa dedotta dal tipo.',
            'I boxplot richiedono almeno cinque valori non costanti per gruppo; osservazioni ripetute possono essere dipendenti.',
            'Le deviazioni standard sono descrittive. Non sono prodotti intervalli di confidenza né test inferenziali: il campionamento non è noto.',
            'Il confronto modelli usa solo coppie scenario/prompt comuni. Le altre aggregazioni descrivono il campione disponibile.',
            'La Skill resta parte del benchmark. Questi dati non stimano il suo effetto causale rispetto alla sua assenza.', '',
            '## Risultati osservati', '']
        if not runs.empty:
            a = aggregate(runs, ['prompt'])
            for row in a.itertuples():
                def pct(v):
                    return 'non determinabile' if pd.isna(v) else f'{100*v:.1f}%'
                description.append(f'- {row.prompt}: {row.scenarios} scenari, {row.runs} esecuzioni; '
                                   f'controlli macro {pct(row.macro_rate)}, micro {pct(row.micro_rate)}; '
                                   f'successo completo {pct(row.full_success_rate)} ({row.full_known_runs} esiti completi noti).')
        else:
            description.append('Nessun risultato utilizzabile. Non sono state formulate conclusioni sul benchmark.')
        description += ['', '## Registro di generazione', '', *['- ' + x for x in log]]
        (args.output / 'summary.md').write_text('\n'.join(description) + '\n', encoding='utf-8')
        (args.output / 'generation_log.txt').write_text('\n'.join(log) + '\n', encoding='utf-8')
        print(f'{p.count} figure; riepiloghi in {args.output}')
        return 0 if not runs.empty else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.append(f'ERRORE input/configurazione: {exc}')
        (args.output / 'generation_log.txt').write_text('\n'.join(log) + '\n', encoding='utf-8')
        print(log[-1])
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
