"""Duração por etapa do deploy e a decisão de parar o serviço só quando o pip tem o que instalar.

Os trechos são extraídos do próprio deploy.sh e executados em bash com um pip falso, então o teste vale para o texto real.
"""
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'deploy.sh').read_text()


def section(start, end):
    first = SCRIPT.index(start)
    return SCRIPT[first:SCRIPT.index(end, first)]


TIMING_CODE = section('DEPLOY_STARTED=$SECONDS', 'restore_service_on_error() {')
PIP_CODE = section('PIP_UPGRADE_FLAG=""', 'cleanup_pip_orphans "$VENV_PIP"\nVENV_NAME=')


def bash(script, cwd, **env):
    import os
    return subprocess.run(['bash', '-c', script], cwd=cwd, capture_output=True, text=True, env={**os.environ, **env})


def test_each_step_is_timed_shown_sorted_and_kept_in_a_history_file(tmp_path):
    (tmp_path / 'logs').mkdir()
    result = bash(textwrap.dedent(f'''
        set -e
        DEPLOY_LOG=logs/deploy.log; : > "$DEPLOY_LOG"
        {TIMING_CODE}
        step_done "rapida"
        sleep 2
        step_done "lenta"
        step_done "outra"
        print_timings
    '''), tmp_path)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert '  > [tempo] rapida: 0s' in lines and '  > [tempo] lenta: 2s' in lines
    ranking = lines[lines.index(next(line for line in lines if line.startswith('Tempo por etapa'))) + 1:]
    assert ranking[0].strip().endswith('lenta') and ranking[0].strip().startswith('2s')
    history = (tmp_path / 'logs' / 'deploy-timings.log').read_text()
    assert history.startswith('=== ') and 'lenta' in history and 'total' in history.splitlines()[0]
    assert 'Tempo por etapa' in (tmp_path / 'logs' / 'deploy.log').read_text()
    bash(f'DEPLOY_LOG=/dev/null; {TIMING_CODE}\nstep_done "x"; print_timings', tmp_path)
    assert history in (tmp_path / 'logs' / 'deploy-timings.log').read_text()           # the history only grows


def test_with_nothing_timed_the_summary_prints_nothing_and_never_fails(tmp_path):
    (tmp_path / 'logs').mkdir()
    result = bash(f'set -e\nDEPLOY_LOG=/dev/null\n{TIMING_CODE}\nprint_timings\necho fim', tmp_path)
    assert result.returncode == 0 and result.stdout.strip() == 'fim' and not (tmp_path / 'logs' / 'deploy-timings.log').exists()


def fake_pip(tmp_path, output, code=0):
    pip = tmp_path / 'pip'
    pip.write_text(f'#!/bin/bash\necho "$@" >> "{tmp_path}/pip-args"\ncat <<"EOF"\n{output}\nEOF\nexit {code}\n')
    pip.chmod(0o755)
    return pip


def pending(tmp_path, pip, upgrade=None):
    (tmp_path / 'requirements.txt').write_text('x==1\n')
    result = bash(textwrap.dedent(f'''
        DEPLOY_LOG="{tmp_path}/deploy.log"; VENV_PIP="{pip}"
        {PIP_CODE}
        if pip_has_pending_changes; then echo PENDING; else echo CLEAN; fi
    '''), tmp_path, **({'PIP_UPGRADE': upgrade} if upgrade else {}))
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1], result.stdout, (tmp_path / 'pip-args').read_text()


def test_the_service_is_not_stopped_when_the_simulation_finds_nothing_to_install(tmp_path):
    verdict, _, args = pending(tmp_path, fake_pip(tmp_path, 'Requirement already satisfied: flask in ./venv'))
    assert verdict == 'CLEAN'
    assert '--dry-run' in args and '-r requirements.txt' in args and '--upgrade' not in args   # simulates, and never upgrades unasked


def test_the_service_stops_only_when_a_package_would_really_change(tmp_path):
    verdict, _, _ = pending(tmp_path, fake_pip(tmp_path, 'Requirement already satisfied: a\nWould install six-1.16.0 toolz-0.12.1'))
    assert verdict == 'PENDING'


def test_a_failed_simulation_falls_back_to_the_full_path(tmp_path):
    verdict, out, _ = pending(tmp_path, fake_pip(tmp_path, 'ERROR: ResolutionImpossible', code=1))
    assert verdict == 'PENDING' and 'simulacao do pip falhou' in out and 'ResolutionImpossible' in (tmp_path / 'deploy.log').read_text()


def test_upgrading_is_still_possible_on_purpose(tmp_path):
    verdict, _, args = pending(tmp_path, fake_pip(tmp_path, 'Requirement already satisfied: a'), upgrade='1')
    assert '--upgrade' in args


def test_the_deploy_script_wires_the_new_behaviour_in_the_right_order():
    gate = SCRIPT.index('if [ "$REQUIREMENTS_CHANGED" = "1" ] && pip_has_pending_changes; then')
    install = SCRIPT.index('"$VENV_PIP" install -r requirements.txt $PIP_UPGRADE_FLAG --quiet')
    assert SCRIPT.index('stop_service_for_deploy\n    "$VENV_PIP" install --upgrade pip') < install
    assert gate < SCRIPT.index('stop_service_for_deploy\n    "$VENV_PIP" install --upgrade pip')
    assert '-r requirements.txt --upgrade' not in SCRIPT                     # the unconditional upgrade is gone
    assert 'o servico nao para' in SCRIPT and 'requirements.txt sem alteracoes' in SCRIPT
    # every phase is timed, and the summary also prints when the deploy fails
    for label in ('git pull e artefatos gerados', 'dependencias Python', 'migracoes', 'build do frontend', 'parada do servico, nginx, importacao e workers', 'iniciar o servico',
                  'validacao das APIs', 'health check'):
        assert f'step_done "{label}' in SCRIPT, label
    failure = SCRIPT[SCRIPT.index('restore_service_on_error() {'):SCRIPT.index('trap restore_service_on_error ERR')]
    assert 'print_timings' in failure
    assert SCRIPT.index('print_timings\n\necho ""\necho "========================================"\necho "  Deploy concluido') > SCRIPT.index('step_done "health check"')


def test_requirements_pull_torch_for_cpu_on_fresh_installs_and_still_list_it():
    lines = [line for line in (ROOT / 'requirements.txt').read_text().splitlines() if line and not line.startswith('#')]
    assert lines[0] == '--extra-index-url https://download.pytorch.org/whl/cpu'
    assert any(line.startswith('torch') for line in lines) and any(line.startswith('sentence-transformers') for line in lines)


VERIFY_CODE = section('VERIFY_TIMEOUT="${VERIFY_TIMEOUT:-180}"', 'step_done "validacao das APIs"')


def run_verify(tmp_path, python_body, timeout_seconds, fake_timeout=None):
    python = tmp_path / 'python'
    python.write_text('#!/bin/bash\n' + python_body)
    python.chmod(0o755)
    (tmp_path / 'logs').mkdir(exist_ok=True)
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir(exist_ok=True)
    if fake_timeout is not None:                                  # stands in for GNU timeout, which the Linux server has and macOS does not
        shim = bin_dir / 'timeout'
        shim.write_text(f'#!/bin/bash\necho "$1" > "{tmp_path}/timeout-arg"\n{fake_timeout}\n')
        shim.chmod(0o755)
    import os
    return bash(f'''
        set -e
        DEPLOY_LOG="{tmp_path}/deploy.log"; VENV_PYTHON="{python}"; VERIFY_TIMEOUT={timeout_seconds}
        {VERIFY_CODE}
        echo CONCLUIDO
    ''', tmp_path, PATH=f"{bin_dir}:{os.environ['PATH']}")


def test_a_verification_that_hangs_is_cut_off_with_a_message_instead_of_blocking_the_deploy(tmp_path):
    result = run_verify(tmp_path, 'sleep 30', 7, fake_timeout='exit 124')          # GNU timeout exits 124 when it cuts a command off
    assert result.returncode == 124 and 'passou de 7s' in result.stdout and 'CONCLUIDO' not in result.stdout
    assert (tmp_path / 'timeout-arg').read_text().strip() == '7'                    # the limit is what is passed to timeout


def test_a_failing_verification_still_fails_the_deploy_and_a_passing_one_continues(tmp_path):
    failed = run_verify(tmp_path, 'echo "Verificacao falhou"; exit 3', 5)
    assert failed.returncode == 3 and 'CONCLUIDO' not in failed.stdout and 'passou de' not in failed.stdout
    assert 'Verificacao falhou' in (tmp_path / 'deploy.log').read_text()
    passed = run_verify(tmp_path, 'echo ok; exit 0', 5)
    assert passed.returncode == 0 and 'CONCLUIDO' in passed.stdout
