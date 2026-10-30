#!/usr/bin/env python3
"""Zero-configuration entry point: copy benchmark CSVs into result/ and run this file."""
from __future__ import annotations

import argparse
from pathlib import Path
import os
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.plot_kathara_results import read_benchmark, produce, export_figure

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "result"
OUTPUT = ROOT / "grafici"
PROMPT_LABELS = {"T1": "T1 · tecnico strutturato", "T2": "T2 · tecnico discorsivo",
                 "T3": "T3 · non tecnico discorsivo", "T4": "T4 · non tecnico libero",
                 "T5": "T5 · albero grafico", "T6": "T6 · JSON"}
NUMERIC = ["total_seconds","agent_seconds","checker_seconds","total_tokens",
           "input_tokens","output_tokens","skill_gate_read_seconds"]
ORDER = ["no_skill","creation_only","dns_only","both_forced","auto"]


def _numeric(r):
    for col in NUMERIC:
        r[col] = pd.to_numeric(r[col], errors="coerce") if col in r else np.nan
    return r


def _bar(df, labels, column, title, ylabel, out, section, name, formats, pct=False):
    data=df.dropna(subset=[column])
    if data.empty:
        return 0
    g=data.groupby(labels,dropna=False)[column].agg(["mean","count"])
    if g.empty:
        return 0
    if isinstance(g.index,pd.MultiIndex):
        names=[" | ".join(map(str,i)) for i in g.index]
    else:
        names=[str(x) for x in g.index]
    values=g["mean"]*(100 if pct else 1)
    fig,ax=plt.subplots(figsize=(max(8, min(len(names)*.9,20)),5),layout="constrained")
    bars=ax.bar(range(len(names)),values)
    ax.set_xticks(range(len(names)),[f"{x}\nn={int(n)}" for x,n in zip(names,g["count"])],
                  rotation=35,ha="right")
    ax.set(title=title,ylabel=ylabel)
    if pct:
        ax.set_ylim(0,105)
    if len(names)<=15:
        ax.bar_label(bars,fmt="%.1f",padding=3,fontsize=8)
    export_figure(fig,out,section,name,formats)
    return 1


def _heatmap(r,col,by,out,section,name,formats):
    data=r.dropna(subset=["test_rate"])
    if data.empty:
        return 0
    table=data.pivot_table(index="scenario",columns=by,values="test_rate",aggfunc="mean")*100
    if table.empty or len(table)>50:
        return 0
    fig,ax=plt.subplots(figsize=(max(8,table.shape[1]*1.2),max(4,table.shape[0]*.47)),
                        layout="constrained")
    cmap=plt.get_cmap("viridis").copy()
    cmap.set_bad("#d9d9d9")
    im=ax.imshow(np.ma.masked_invalid(table.to_numpy()),vmin=0,vmax=100,aspect="auto",cmap=cmap)
    ax.set_xticks(range(len(table.columns)),table.columns,rotation=35,ha="right")
    ax.set_yticks(range(len(table.index)),table.index)
    ax.set(title=col)
    fig.colorbar(im,ax=ax,label="Test superati (%)")
    export_figure(fig,out,section,name,formats)
    return 1


def _failure_groups(c,r,out,formats):
    c=c[c.data_quality_status.ne("count_mismatch")].copy()
    c=c.merge(r[["run_id","skill_mode"]],on="run_id",how="inner")
    evaluated=c[c.outcome.isin(["pass","fail"])]
    if evaluated.empty:
        return 0
    g=evaluated.assign(failed=evaluated.outcome.eq("fail").astype(int)).groupby(
        ["skill_mode","check_type"]).agg(failed=("failed","sum"),evaluated=("failed","size"))
    g["failure_pct"]=100*g.failed/g.evaluated
    g.to_csv(out/"check_category_failure_rates.csv")
    fig,ax=plt.subplots(figsize=(10,max(4,min(len(g)*.3,14))),layout="constrained")
    g["failure_pct"].sort_values().plot.barh(ax=ax)
    ax.set(xlabel="Controlli falliti / controlli valutati (%)",
           title="Tassi di fallimento per categoria e Skill")
    export_figure(fig,out,"04_dns_e_checker","categorie_fallimento",formats)
    return 1


def render(runs,checks,out,formats):
    runs=_numeric(runs.copy())
    out.mkdir(parents=True,exist_ok=True)
    n=0
    scored=runs.dropna(subset=["test_rate"])
    n+=_bar(scored,["skill_mode"],"test_rate","Correttezza per modalità Skill",
            "Controlli superati (%)",out,"01_correttezza","skill",formats,pct=True)
    n+=_bar(scored,["prompt"],"test_rate","Correttezza per formulazione del prompt",
            "Controlli superati (%)",out,"02_prompt","prompt",formats,pct=True)
    n+=_bar(scored,["category"],"test_rate","Correttezza per livello di difficoltà",
            "Controlli superati (%)",out,"03_laboratori","livelli",formats,pct=True)
    n+=_heatmap(runs,"Laboratori × prompt","prompt",out,"03_laboratori","lab_prompt",formats)
    n+=_heatmap(runs,"Laboratori × Skill","skill_mode",out,"03_laboratori","lab_skill",formats)
    if not checks.empty:
        n+=_failure_groups(checks,runs,out,formats)
    for metric in ["total_seconds","agent_seconds","checker_seconds"]:
        n+=_bar(runs,["skill_mode"],metric,f"{metric} per modalità Skill",
                "Secondi medi",out,"05_efficienza",metric,formats)
    for metric in ["total_tokens","input_tokens","output_tokens"]:
        n+=_bar(runs,["skill_mode"],metric,f"{metric} per modalità Skill",
                "Token medi",out,"05_efficienza",metric,formats)
    gate=runs.copy()
    if "skill_gate_status" in gate:
        gate["skill_gate_status"]=gate.skill_gate_status.replace("","non registrato")
        gate.groupby(["skill_mode","skill_gate_status"]).size().rename("run_count").to_csv(
            out/"skill_gate_summary.csv")
    if "skill_gate_read_seconds" in gate:
        n+=_bar(gate,["skill_mode"],"skill_gate_read_seconds",
                "Tempo verificato di lettura delle Skill","Secondi medi",
                out,"06_skill_gate","lettura_skill",formats)
    scored.groupby(["skill_mode","prompt"],dropna=False).agg(
        runs=("run_id","count"),mean_pass_rate=("test_rate","mean"),
        total_passed=("passed_tests","sum"),total_evaluated=("evaluated_tests","sum")
    ).to_csv(out/"skill_prompt_summary.csv")
    if "task_success" in runs:
        reliable=runs[runs.data_quality_status.ne("count_mismatch")].copy()
        reliable.assign(success=reliable.task_success.astype(str).str.lower().eq("true")).groupby(
            "skill_mode").agg(runs=("run_id","count"),fully_successful=("success","sum")).to_csv(
                out/"full_task_success.csv")
    return n


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=INPUT,help="Cartella con runs.csv e checks.csv")
    parser.add_argument("--output",type=Path,default=OUTPUT,help="Cartella che conterrà i grafici")
    parser.add_argument("--format",nargs="+",choices=["png","pdf"],default=["png","pdf"])
    args=parser.parse_args(argv)
    if not (args.input/"runs.csv").exists():
        parser.error(f"Manca {args.input/'runs.csv'}. Copia qui results/runs.csv dal benchmark.")
    if not (args.input/"checks.csv").exists():
        parser.error(f"Manca {args.input/'checks.csv'}. Copia anche results/checks.csv.")
    if args.output.resolve()==args.input.resolve() or args.output.resolve() in args.input.resolve().parents:
        parser.error("La cartella di output deve essere separata dall'input")
    try:
        runs,checks=read_benchmark(args.input)
        if runs.empty:
            parser.error("Nessuna esecuzione valida.")
        n=produce(runs,checks,args.output,list(dict.fromkeys(args.format)))
        n+=render(runs,checks,args.output,list(dict.fromkeys(args.format)))
        (args.output/"LEGGIMI.txt").write_text(
            f"Run analizzate: {len(runs)}\nControlli analizzati: {len(checks)}\n"
            f"Grafici generati: {n}\n"
            f"Run con conteggi discordanti: {int(runs.data_quality_status.eq('count_mismatch').sum())}\n"
            "Controllare data_quality_issues.csv per i dettagli.\n"
            "La temperatura LLM non è stimata: le figure dipendono dai dati osservati.\n"
            "Le percentuali medie sono descrittive; verificare composizione dei gruppi.\n"
            "Leggere docs/GRAFICI_E_METODOLOGIA.md per interpretazione e limiti.\n",
            encoding="utf-8")
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(2,f"Errore: {exc}\n")
    print(f"OK: {len(runs)} run, {len(checks)} controlli, {n} grafici in {args.output}")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
