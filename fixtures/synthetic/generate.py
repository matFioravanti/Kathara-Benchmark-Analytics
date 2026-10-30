"""Dati fittizi per verifica tecnica; non rappresentano risultati del benchmark."""
import csv
from pathlib import Path
import random


def main():
    rng = random.Random(42)
    runs, checks = [], []
    for model in ['Modello_fittizio_A', 'Modello_fittizio_B']:
        for s in range(1, 5):
            for p, prompt in enumerate(['sintetico', 'intermedio', 'dettagliato', 'json', 'yaml']):
                for repeat in range(6):
                    key = dict(scenario=f'SCENARIO_SINTETICO_{s}', prompt=prompt, model=model, run_id=f'r{repeat}')
                    outcomes = []
                    for c in range(8):
                        outcome = rng.choices(['pass', 'fail', 'error', 'skipped'], [65+p*3, 28-p*3, 4, 3])[0]
                        outcomes.append(outcome)
                        checks.append(dict(key, check_id=f'c{c}', check_type=['DNSAuthorityCheck', 'LocalNSCheck',
                                      'DNSRecordCheck', 'ReachabilityCheck'][c % 4], outcome=outcome))
                    evaluated = sum(o in ['pass', 'fail'] for o in outcomes)
                    runs.append(dict(key, category='CATEGORIA_FITTIZIA_' + str(1+(s % 3)),
                                     completed=str(all(o in ['pass', 'fail'] for o in outcomes)).lower(),
                                     passed_tests=outcomes.count('pass'), evaluated_tests=evaluated,
                                     expected_tests=8, devices=2+s, dns_zones=s,
                                     generation_seconds=round(rng.uniform(5, 35), 2),
                                     validation_seconds=round(rng.uniform(2, 8), 2),
                                     input_tokens=100+p*150, output_tokens=rng.randint(100, 1500)))
    for name, rows in [('runs.csv', runs), ('checks.csv', checks)]:
        with (Path(__file__).parent/name).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    print('Generati SOLO dati sintetici in fixtures/synthetic/')


if __name__ == '__main__':
    main()
