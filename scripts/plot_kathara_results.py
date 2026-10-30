#!/usr/bin/env python3
"""Read real Kathara-Skill-LLM CSV reports and render descriptive analyses."""
from __future__ import annotations
import argparse
import os
import re
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", "/tmp/kathara-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

MODES = ["no_skill", "creation_only", "dns_only", "both_forced", "auto"]
PAIR = ["experiment_id", "scenario", "prompt", "model", "replicate", "reasoning_effort", "correction_sha256"]

def read_benchmark(src: Path):
    folder = src / "results" if (src / "results" / "runs.csv").exists() else src
    r = pd.read_csv(folder / "runs.csv", dtype=str, keep_default_na=False)
    c = pd.read_csv(folder / "checks.csv", dtype=str, keep_default_na=False)
    for df, required in [(r, {"ID","lab_id","dns_tree_id","task_level","prompt_type","model",
                              "skill_mode","checks_passed","checks_total","pipeline_completed","checker_executed"}),
                         (c, {"ID","lab_id","dns_tree_id","task_level","prompt_type","model",
                              "test_description","passed","reason","category"})]:
        missing = required - set(df)
        if missing:
            raise ValueError(f"Colonne mancanti: {sorted(missing)}")
    if r.ID.eq("").any() or r.ID.duplicated().any():
        raise ValueError("ID delle run mancanti o duplicati")
    if c.ID.eq("").any() or (set(c.ID)-set(r.ID)):
        raise ValueError("Controlli con ID senza run corrispondente")
    def common(df):
        return pd.DataFrame({"run_id":df.ID, "scenario":df.lab_id+"/"+df.dns_tree_id+"/"+df.task_level,
                             "prompt":df.prompt_type, "model":df.model}, index=df.index)
    runs = common(r)
    runs["category"] = r.task_level
    runs["skill_mode"] = r.skill_mode
    runs["passed_tests"] = pd.to_numeric(r.checks_passed, errors="coerce")
    runs["evaluated_tests"] = pd.to_numeric(r.checks_total, errors="coerce")
    runs["completed"] = (r.pipeline_completed.str.lower().eq("true") &
                         r.checker_executed.str.lower().eq("true"))
    runs["test_rate"] = runs.passed_tests.div(runs.evaluated_tests.where(runs.evaluated_tests.gt(0)))
    for column in PAIR + ["llm_temperature","llm_top_p","sampling_temperature_status",
                          "sampling_top_p_status","total_seconds","agent_seconds","checker_seconds",
                          "input_tokens","output_tokens","total_tokens","task_success"]:
        if column in ("scenario","prompt","model"):
            continue
        runs[column] = r[column] if column in r else ""
    checks = common(c)
    checks["check_id"] = (c.groupby("ID",sort=False).cumcount()+1).astype(str)
    checks["check_type"] = c.category.where(c.category.ne(""),"unknown")
    checks["description"], checks["reason"] = c.test_description, c.reason
    checks["outcome"] = c.passed.str.strip().str.lower().map({"true":"pass","false":"fail"}).fillna("unknown")
    # Diagnostic-only classification; failed results are not automatically reinterpreted.
    checks["record_type"] = (c.reason.str.extract(r"\bresolve\s+(A|AAAA|MX|NS|SOA|CNAME)\b",
                              flags=re.IGNORECASE, expand=False).fillna("").str.upper())
    checks.loc[checks.check_type.ne("dns_record"),"record_type"] = ""
    if runs.test_rate.dropna().gt(1).any() or runs.test_rate.dropna().lt(0).any():
        raise ValueError("Conteggi checker incoerenti")
    counts = checks.assign(p=checks.outcome.eq("pass").astype(int),
                           e=checks.outcome.isin(["pass","fail"]).astype(int)).groupby("run_id")[["p","e"]].sum()
    aligned = runs.set_index("run_id").join(counts)
    mismatch = (aligned.p.notna() & aligned.p.ne(aligned.passed_tests)) | (aligned.e.notna() & aligned.e.ne(aligned.evaluated_tests))
    if mismatch.any():
        raise ValueError(f"Conteggi aggregati e dettagliati discordanti per {int(mismatch.sum())} run")
    return runs, checks

def export_figure(fig, root, folder, name, formats):
    out=root/folder
    out.mkdir(parents=True,exist_ok=True)
    for ext in formats:
        fig.savefig(out/f"{name}.{ext}", dpi=300, bbox_inches="tight")
    plt.close(fig)

def produce(runs, checks, out, formats):
    out.mkdir(parents=True, exist_ok=True)
    runs.to_csv(out/"normalized_runs.csv", index=False)
    checks.to_csv(out/"normalized_checks.csv",index=False)
    log=[]
    figures=0
    modes=[x for x in MODES if x in set(runs.skill_mode)]
    valid=runs.dropna(subset=["test_rate"]).copy()
    for key in PAIR:
        if key not in valid:
            valid[key]=""
    if len(modes)>1:
        if valid.duplicated(PAIR+["skill_mode"]).any():
            raise ValueError("Chiavi appaiate duplicate")
        counts=valid.groupby(PAIR,dropna=False).skill_mode.nunique()
        common=counts[counts.eq(len(modes))].index
        matched=valid.set_index(PAIR).loc[common].reset_index() if len(common) else valid.iloc[0:0]
        if not matched.empty:
            agg=matched.groupby("skill_mode").test_rate.agg(["mean","count"]).reindex(modes)
            agg.to_csv(out/"skill_matched_summary.csv")
            fig,ax=plt.subplots(figsize=(9,5),layout="constrained")
            ax.bar(agg.index,100*agg["mean"],color=plt.get_cmap("tab10").colors[:len(agg)])
            ax.set(ylabel="Test superati (%)",ylim=(0,105),title="Modalità Skill a parità di scenario e prompt")
            ax.tick_params(axis="x",rotation=20)
            export_figure(fig,out,"11_skill","confronto_appaiato",formats)
            figures+=1
            if "no_skill" in modes:
                base=valid[valid.skill_mode.eq("no_skill")][PAIR+["test_rate"]]
                deltas=[]
                for mode in modes:
                    if mode=="no_skill": continue
                    other=valid[valid.skill_mode.eq(mode)][PAIR+["test_rate"]]
                    pair=base.merge(other,on=PAIR,suffixes=("_base","_skill"))
                    if len(pair):
                        deltas.append({"skill_mode":mode,"n_pairs":len(pair),
                                       "mean_delta_pp":100*(pair.test_rate_skill-pair.test_rate_base).mean()})
                if deltas:
                    deltas=pd.DataFrame(deltas)
                    deltas.to_csv(out/"skill_paired_deltas.csv",index=False)
                    fig,ax=plt.subplots(figsize=(9,4),layout="constrained")
                    ax.barh(deltas.skill_mode,deltas.mean_delta_pp)
                    ax.axvline(0,color="black",linewidth=.8)
                    ax.set(xlabel="Differenza rispetto a no_skill (punti percentuali)",title="Confronto appaiato")
                    export_figure(fig,out,"11_skill","delta_rispetto_baseline",formats)
                    figures+=1
        else:
            log.append("Confronto Skill non disponibile: nessuna combinazione comune.")
    if "sampling_temperature_status" in runs:
        coverage=pd.crosstab(runs.skill_mode,runs.sampling_temperature_status.replace("","missing"))
        coverage.to_csv(out/"sampling_coverage.csv")
        fig,ax=plt.subplots(figsize=(9,4.5),layout="constrained")
        coverage.plot(kind="bar",stacked=True,ax=ax)
        ax.set(ylabel="Numero di run",xlabel="",title="Disponibilità temperatura LLM")
        ax.tick_params(axis="x",rotation=20)
        export_figure(fig,out,"12_sampling","temperatura_copertura",formats)
        figures+=1
        observed=runs[runs.sampling_temperature_status.eq("observed")].copy()
        observed["temp"]=pd.to_numeric(observed.llm_temperature,errors="coerce")
        observed=observed.dropna(subset=["temp","test_rate"])
        if len(observed)>=3 and observed.temp.nunique()>=2:
            fig,ax=plt.subplots(figsize=(8,5),layout="constrained")
            for mode,g in observed.groupby("skill_mode"):
                ax.scatter(g.temp,100*g.test_rate,label=f"{mode} (n={len(g)})")
            ax.set(xlabel="Temperatura osservata",ylabel="Test superati (%)",
                   title="Temperatura e correttezza (associazione descrittiva)")
            ax.legend()
            export_figure(fig,out,"12_sampling","temperatura_vs_successo",formats)
            figures+=1
        else:
            log.append("Grafico temperatura vs successo omesso: mancano valori osservati sufficienti.")
    f=checks[(checks.outcome=="fail") & checks.record_type.ne("")]
    if not f.empty:
        counts=f.groupby(["check_type","record_type"]).size().reset_index(name="failed_checks")
        counts.to_csv(out/"dns_record_failures.csv",index=False)
        fig,ax=plt.subplots(figsize=(8,4.5),layout="constrained")
        f.record_type.value_counts().sort_values().plot(kind="barh",ax=ax)
        ax.set(xlabel="Controlli falliti, non errori indipendenti",
               title="Tipi DNS desunti dalle diagnostiche dei fallimenti")
        export_figure(fig,out,"13_dns_diagnostics","record_failure_counts",formats)
        figures+=1
        if f.record_type.eq("MX").any():
            log.append("I fallimenti MX richiedono verifica del checker/FQDN; non riclassificati.")
    (out/"generation_log.txt").write_text("\n".join(log)+"\n",encoding="utf-8")
    return figures

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=Path("benchmark_plots_real"))
    parser.add_argument("--format",choices=["png","pdf"],nargs="+",default=["png","pdf"])
    args=parser.parse_args(argv)
    if args.input.resolve()==args.output.resolve() or args.output.resolve() in args.input.resolve().parents:
        parser.error("L'output deve essere separato dall'input.")
    try:
        runs,checks=read_benchmark(args.input)
        n=produce(runs,checks,args.output,args.format)
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(2,f"Errore: {exc}\n")
    print(f"Analizzate {len(runs)} run, {len(checks)} controlli; prodotte {n} figure")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
