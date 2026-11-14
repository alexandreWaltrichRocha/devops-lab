#!/usr/bin/env python3
"""Gera k8s/monitoring/prometheusrule.yml a partir de prometheus/alerts.yml.

Uso:
  python scripts/sync_rules.py          # reescreve o PrometheusRule
  python scripts/sync_rules.py --check  # falha (exit 1) se estiver desatualizado
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "prometheus" / "alerts.yml"
DST = ROOT / "k8s" / "monitoring" / "prometheusrule.yml"

HEADER = (
    "# GERADO por scripts/sync_rules.py a partir de prometheus/alerts.yml.\n"
    "# NÃO edite à mão: altere prometheus/alerts.yml e rode `python scripts/sync_rules.py`.\n"
    "# Ajuste o label `release` como no ServiceMonitor.\n"
)


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str)


def render() -> str:
    groups = yaml.safe_load(SRC.read_text(encoding="utf-8"))["groups"]
    doc = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PrometheusRule",
        "metadata": {"name": "devops-lab", "labels": {"release": "kube-prometheus-stack"}},
        "spec": {"groups": groups},
    }
    return HEADER + yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)


def main() -> int:
    out = render()
    if "--check" in sys.argv:
        if not DST.exists() or DST.read_text(encoding="utf-8") != out:
            print("k8s/monitoring/prometheusrule.yml desatualizado. "
                  "Rode: python scripts/sync_rules.py", file=sys.stderr)
            return 1
        print("prometheusrule.yml em sincronia com alerts.yml")
        return 0
    DST.write_text(out, encoding="utf-8")
    print(f"Gerado {DST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
