# Environment
## Python
Python 3.10.12

## Pip Freeze (top 200)
annotated-types==0.7.0
beautifulsoup4==4.13.5
certifi==2025.8.3
chardet==5.2.0
charset-normalizer==3.4.3
click==8.2.1
coverage==7.10.5
defusedxml==0.7.1
diff_cover==9.2.0
exceptiongroup==1.3.0
genbadge==1.1.2
html5lib==1.1
idna==3.10
iniconfig==2.1.0
Jinja2==3.1.6
lxml==6.0.1
MarkupSafe==3.0.2
packaging==25.0
pillow==11.3.0
pluggy==1.6.0
pydantic==2.11.7
pydantic_core==2.33.2
Pygments==2.19.2
pytest==8.4.1
pytest-cov==6.2.1
python-dotenv==1.1.1
PyYAML==6.0.2
reportlab==4.4.3
requests==2.32.5
six==1.17.0
smart-mail-agent==1.0.0
soupsieve==2.7
tomli==2.2.1
tqdm==4.67.1
typing-inspection==0.4.1
typing_extensions==4.14.1
urllib3==2.5.0
webencodings==0.5.1

## Key Environment Variables (masked)
OFFLINE=1
PATH=/home/youjie/projects/smart-mail-agent/.venv/bin:/home/youjie/.local/bin:/home/youjie/projects/smart-mail-agent/bin:/home/youjie/.local/bin:/home/youjie/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/usr/lib/wsl/lib:/mnt/c/Users/hurry/AppData/Local/Programs/Python/Python310/:/mnt/c/Users/hurry/AppData/Local/Programs/Python/Python310/Scripts/:/mnt/c/Users/hurry/AppData/Local/Programs/Python/Python312/:/mnt/c/Users/hurry/AppData/Local/Programs/Python/Python312/Scripts/:/mnt/c/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8/bin:/mnt/c/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v11.8/libnvvp:/mnt/c/Windows/System32:/mnt/c/Program Files/Git/cmd:/mnt/c/Users/hurry/OneDrive/桌面/cudnn-windows-x86_64-8.9.6.50_cuda11-archive/bin:/mnt/c/Program Files/NVIDIA Corporation/Nsight Compute 2022.3.0/:/mnt/c/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.2/bin:/mnt/c/Users/hurry/OneDrive/桌面/ffmpeg-7.1.1-essentials_build/bin:/mnt/c/Users/hurry/TikTokDownload-1.4.2.2/TikTokTool.exe:/mnt/c/Program Files (x86)/Windows Kits/10/Windows Performance Toolkit/:/mnt/c/WINDOWS/system32:/mnt/c/WINDOWS:/mnt/c/WINDOWS/System32/Wbem:/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/:/mnt/c/WINDOWS/System32/OpenSSH/:/mnt/c/Program Files/Docker/Docker/resources/bin:/mnt/c/Users/hurry/anaconda3:/mnt/c/Users/hurry/anaconda3/Library/mingw-w64/bin:/mnt/c/Users/hurry/anaconda3/Library/usr/bin:/mnt/c/Users/hurry/anaconda3/Library/bin:/mnt/c/Users/hurry/anaconda3/Scripts:/mnt/c/Users/hurry/.cargo/bin:/mnt/c/Users/hurry/AppData/Local/Programs/Microsoft VS Code/bin:/mnt/c/Users/hurry/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Anaconda (anaconda3):/mnt/c/Users/hurry/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Anaconda3 (64-bit):/mnt/c/Users/hurry/AppData/Local/Programs/Eclipse Adoptium/jdk-17.0.8.101-hotspot/bin:/mnt/c/Users/hurry/AppData/Local/Muse Hub/lib:/mnt/c/Users/hurry/OneDrive/桌面/cudnn-windows-x86_64-9.5.0.50_cuda12-archive/bin:/mnt/c/users/hurry/.local/bin:/mnt/c/Users/hurry/AppData/Local/Microsoft/WindowsApps:/snap/bin
PYTHONPATH=/home/youjie/projects/smart-mail-agent:/home/youjie/projects/smart-mail-agent/src

## Git
main
aeb3082 test: provide robust normalize_result shim; refresh coverage [skip ci]
74792b8 chore(badge): update coverage.svg [skip ci]
3e4dc5c apply autostash
3f1a8b0 chore(badge): update coverage.svg [skip ci]
8fec46e chore: ignore and untrack backup .bak files
## main...origin/main
MM .coverage
 M .coveragerc
R  modules/_spam_core.py -> archive/legacy_modules/_spam_core.py
R  modules/apply_diff.py -> archive/legacy_modules/apply_diff.py
R  modules/features_sales_notifier.py -> archive/legacy_modules/features_sales_notifier.py
R  modules/inference_classifier.py -> archive/legacy_modules/inference_classifier.py
R  modules/intent_classifier.py -> archive/legacy_modules/intent_classifier.py
R  modules/log_writer_db.py -> archive/legacy_modules/log_writer_db.py
R  modules/pdf_safe.py -> archive/legacy_modules/pdf_safe.py
R  modules/quote_logger.py -> archive/legacy_modules/quote_logger.py
R  modules/sales_notifier.py -> archive/legacy_modules/sales_notifier.py
R  modules/spam.py -> archive/legacy_modules/spam.py
R  modules/spam_filter.py -> archive/legacy_modules/spam_filter.py
R  modules/spamcheck.py -> archive/legacy_modules/spamcheck.py
M  badges/coverage.svg
M  coverage.xml
 M modules/quotation.py
 M pytest.ini
 M src/ai_rpa/actions.py
 M src/ai_rpa/main.py
 M src/ai_rpa/nlp.py
 M src/ai_rpa/scraper.py
A  src/ai_rpa/utils/__init__.py
MM src/smart_mail_agent/cli/spamcheck.py
 M src/smart_mail_agent/core/classifier.py
 M src/smart_mail_agent/core/utils/jsonlog.py
M  src/smart_mail_agent/policy_engine.py
M  src/smart_mail_agent/sma_types.py
M  src/smart_mail_agent/spam/spam_llm_filter.py
M  src/smart_mail_agent/utils/__init__.py
M  src/smart_mail_agent/utils/spam_filter.py
AM tests/boost/test_core_shims_and_utils.py
?? .coveragerc.bak.1756161987
?? CHANGELOG.md
?? CHANGES.md
?? CODE_DUMP.txt
?? REPORT/
?? archive/legacy_modules/README.md
?? configs/actions_playbook.yaml
?? constraints-dev.txt
?? data/leads.db
?? docs/legacy_isolation.md
?? modules/README.md
?? reports/ALL_FILES.20250826T024644.md
?? reports/MANIFEST.20250826T024644.txt
?? reports/STATUS_REPORT.md
?? reports/archive/
?? requirements-dev.txt
?? scripts/_apply_patch_boost.sh
?? scripts/boost_coverage_now.sh
?? scripts/bootstrap_and_boost.sh
?? smart_mail_agent/core/
?? src/ai_rpa/actions_playbook.py
?? src/ai_rpa/actions_router.py
?? src/ai_rpa/intent_map.py
?? src/ai_rpa/mailguard/
?? src/ai_rpa/nlp_rules/
?? src/ai_rpa/spam_adapter.py
?? src/ai_rpa/utils/json_safe.py
?? tests/ai_rpa_unit/
?? tests/boost/test_cli_help.py
?? tests/boost/test_importlib_sanity.py
?? tests/boost/test_reflective_execution.py
?? tests/coverage/
?? tests/sma_core/
?? tools/bootstrap.sh
?? tools/ci-guard.sh
?? tools/dev-check.sh
?? tools/env.sh

## Pytest (summary)
................................................s....................... [ 39%]
........................................................................ [ 78%]
........................................                                 [100%]
=============================== warnings summary ===============================
tests/boost/test_reflective_execution.py::test_reflective_sweep
  /home/youjie/projects/smart-mail-agent/tests/boost/test_reflective_execution.py:41: PydanticDeprecatedSince20: The `__fields__` attribute is deprecated, use `model_fields` instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    for mname, mobj in ((n, getattr(inst, n)) for n in dir(inst)):

tests/boost/test_reflective_execution.py::test_reflective_sweep
  /home/youjie/projects/smart-mail-agent/tests/boost/test_reflective_execution.py:41: PydanticDeprecatedSince20: The `__fields_set__` attribute is deprecated, use `model_fields_set` instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.11/migration/
    for mname, mobj in ((n, getattr(inst, n)) for n in dir(inst)):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================================ tests coverage ================================
_______________ coverage: platform linux, python 3.10.12-final-0 _______________

Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
src/ai_rpa/actions.py                  26      0   100%
src/ai_rpa/actions_playbook.py         35     28    20%   8, 12-20, 23-40
src/ai_rpa/actions_router.py           28      6    79%   20-21, 24-25, 28-29
src/ai_rpa/file_classifier.py          24      0   100%
src/ai_rpa/intent_map.py               15      0   100%
src/ai_rpa/mailguard/detector.py       61      2    97%   38-39
src/ai_rpa/main.py                    173     18    90%   51-53, 73, 86, 93, 99-100, 116, 118, 120, 221-222, 260-278
src/ai_rpa/nlp.py                      91      5    95%   41, 69, 77, 80-81
src/ai_rpa/nlp_llm.py                  21      6    71%   25-32
src/ai_rpa/ocr.py                      27      0   100%
src/ai_rpa/scraper.py                  21      1    95%   22
src/ai_rpa/spam_adapter.py              8      0   100%
src/ai_rpa/utils/config_loader.py      14      0   100%
src/ai_rpa/utils/json_safe.py          21      2    90%   23-24
src/ai_rpa/utils/logger.py              1      0   100%
-----------------------------------------------------------------
TOTAL                                 566     68    88%
Required test coverage of 85% reached. Total coverage: 87.99%

## Coverage (last run)
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
src/ai_rpa/actions.py                  26      0   100%
src/ai_rpa/actions_playbook.py         35     28    20%   8, 12-20, 23-40
src/ai_rpa/actions_router.py           28      6    79%   20-21, 24-25, 28-29
src/ai_rpa/file_classifier.py          24      0   100%
src/ai_rpa/intent_map.py               15      0   100%
src/ai_rpa/mailguard/detector.py       61      2    97%   38-39
src/ai_rpa/main.py                    173     18    90%   51-53, 73, 86, 93, 99-100, 116, 118, 120, 221-222, 260-278
src/ai_rpa/nlp.py                      91      5    95%   41, 69, 77, 80-81
src/ai_rpa/nlp_llm.py                  21      6    71%   25-32
src/ai_rpa/ocr.py                      27      0   100%
src/ai_rpa/scraper.py                  21      1    95%   22
src/ai_rpa/spam_adapter.py              8      0   100%
src/ai_rpa/utils/config_loader.py      14      0   100%
src/ai_rpa/utils/json_safe.py          21      2    90%   23-24
src/ai_rpa/utils/logger.py              1      0   100%
-----------------------------------------------------------------
TOTAL                                 566     68    88%
