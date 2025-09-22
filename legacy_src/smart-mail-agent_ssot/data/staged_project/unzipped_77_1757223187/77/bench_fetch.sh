#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -euo pipefail
ROOT="${SMA_ROOT:-$PWD}"

# 1) SpamAssassin public corpus
cd "$ROOT/data/bench_raw/spamassassin"
base="https://spamassassin.apache.org/old/publiccorpus"
for f in 20030228_easy_ham.tar.bz2 20030228_easy_ham_2.tar.bz2 20030228_hard_ham.tar.bz2 20030228_spam.tar.bz2 20030228_spam_2.tar.bz2; do
  [ -s "$f" ] || wget -q "$base/$f"
  tar -xjf "$f" 2>/dev/null || true
done

# 2) TREC 2007 public spam corpus
cd "$ROOT/data/bench_raw/trec07p"
[ -s trec07p.tgz ] || wget -q "https://plg.uwaterloo.ca/~gvcormac/treccorpus07/trec07p.tgz"
tar -xzf trec07p.tgz 2>/dev/null || true

# 3) Enron-Spam（AUEB）
cd "$ROOT/data/bench_raw/enron"
base_e="https://nlp.cs.aueb.gr/software_and_datasets/Enron-Spam"
for i in 1 2 3 4 5 6; do
  f="enron${i}.tar.gz"
  [ -s "$f" ] || wget -q "$base_e/$f"
  tar -xzf "$f" 2>/dev/null || true
done
echo "[OK] Downloads ready under data/bench_raw/"
