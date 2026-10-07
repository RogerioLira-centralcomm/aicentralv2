"""O pull do deploy não pode abortar por causa de arquivos que o próprio build do servidor reescreve.

Caso real: o servidor compilou aicentralv2/static/cadu_connect/react/untitled.css (versionado, fora do .gitignore) e um commit novo
trazia outra versão do mesmo arquivo; o git pull parou com "Your local changes ... would be overwritten".
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'deploy.sh').read_text()


def section(start, end):
    first = SCRIPT.index(start)
    return SCRIPT[first:SCRIPT.index(end, first)]


RESTORE_CODE = section('restore_generated_file() {', 'git pull origin main')


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def write_commit(repo, files, message):
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, 'add', '-A')
    git(repo, 'commit', '-m', message)


def make_server(tmp_path, generated):
    """origin <- author (pushes) and server (clone at the first commit)."""
    origin = tmp_path / 'origin.git'
    subprocess.run(['git', 'init', '--bare', '-b', 'main', str(origin)], check=True, capture_output=True)
    author = tmp_path / 'author'
    subprocess.run(['git', 'clone', str(origin), str(author)], check=True, capture_output=True)
    git(author, 'checkout', '-b', 'main')
    first = {name: 'v1\n' for name in generated}
    first['aicentralv2/static/js/hand-written.js'] = 'source v1\n'
    write_commit(author, first, 'v1')
    git(author, 'push', 'origin', 'main')
    server = tmp_path / 'server'
    subprocess.run(['git', 'clone', '-b', 'main', str(origin), str(server)], check=True, capture_output=True)
    return author, server


def run_deploy_pull(server):
    script = f'set -e\ncd "{server}"\n{RESTORE_CODE}\ngit pull origin main'
    return subprocess.run(['bash', '-c', script], capture_output=True, text=True, env={'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't',
                                                                                        'GIT_COMMITTER_EMAIL': 't@t', 'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin', 'HOME': str(server)})


GENERATED = ['aicentralv2/static/cadu_connect/react/untitled.css', 'aicentralv2/static/cadu_planner/react/untitled.css', 'aicentralv2/static/cadu_workspace/untitled/chat-kit.css',
             'aicentralv2/static/css/tailwind/artifact.css', 'aicentralv2/static/cadu_studio/lab/react/app.js']


def test_the_pull_survives_every_versioned_build_output_the_server_recompiled(tmp_path):
    author, server = make_server(tmp_path, GENERATED)
    write_commit(author, {name: 'v2 from the author\n' for name in GENERATED}, 'v2')
    git(author, 'push', 'origin', 'main')
    for name in GENERATED:                                              # the server build wrote something else
        (server / name).write_text('compiled on the server\n')
    # Without the restore the pull aborts: this is the failure that was seen in production.
    plain = subprocess.run(['git', 'pull', 'origin', 'main'], cwd=server, capture_output=True, text=True)
    assert plain.returncode != 0 and 'would be overwritten' in plain.stderr
    result = run_deploy_pull(server)
    assert result.returncode == 0, result.stdout + result.stderr
    assert all((server / name).read_text() == 'v2 from the author\n' for name in GENERATED)
    backups = list((server / 'logs' / 'deploy-backups').iterdir())
    assert len(backups) == len(GENERATED) and all(item.read_text() == 'compiled on the server\n' for item in backups)       # nothing is lost silently


def test_a_hand_edited_source_file_is_never_restored_behind_your_back(tmp_path):
    author, server = make_server(tmp_path, GENERATED)
    (server / 'aicentralv2/static/js/hand-written.js').write_text('edited on the server\n')
    (server / GENERATED[0]).write_text('compiled on the server\n')
    result = run_deploy_pull(server)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (server / 'aicentralv2/static/js/hand-written.js').read_text() == 'edited on the server\n'
    assert not (server / 'logs' / 'deploy-backups' / 'aicentralv2__static__js__hand-written.js').exists()


def test_nothing_changed_means_nothing_restored_and_no_backups(tmp_path):
    _, server = make_server(tmp_path, GENERATED)
    result = run_deploy_pull(server)
    assert result.returncode == 0 and not (server / 'logs' / 'deploy-backups').exists()


def test_every_build_output_of_the_deploy_is_covered_by_the_restore_list():
    """A new vite config or Tailwind output that is versioned must be added to BUILD_OUTPUT_PATHS, or the pull can abort again."""
    listed = re.findall(r'^\s+"(aicentralv2/static/[^"]+)"', section('BUILD_OUTPUT_PATHS=(', ')\nwhile'), re.M)
    assert listed
    covers = lambda output: any(output == path or output.startswith(path + '/') for path in listed)
    outputs = []
    for config in sorted(ROOT.glob('vite.*.config.mjs')):
        text = config.read_text()
        outputs += re.findall(r"outDir:\s*resolve\('(aicentralv2/static/[^']+)'\)", text)
        outputs += re.findall(r"const outputDir = resolve\('(aicentralv2/static/[^']+)'\)", text)
    scripts = [ROOT / 'package.json', *sorted((ROOT / 'frontend').glob('*/untitled-kit/package.json'))]
    for package in scripts:
        for output in re.findall(r'-o (\S*aicentralv2/static/\S+?\.css)', package.read_text()):
            outputs.append('aicentralv2/static/' + output.split('aicentralv2/static/')[1])
    assert len(outputs) >= 14, outputs                        # 8 vite bundles + 7 Tailwind outputs, less the ones that share a folder
    missing = [output for output in outputs if not covers(output)]
    assert not missing, f'saídas de build fora de BUILD_OUTPUT_PATHS: {missing}'


def test_the_restore_runs_before_the_pull_and_uses_the_modified_files_of_those_paths():
    assert SCRIPT.index('BUILD_OUTPUT_PATHS=(') < SCRIPT.index('git pull origin main >> "$DEPLOY_LOG"')
    assert 'git ls-files -m -- "${BUILD_OUTPUT_PATHS[@]}"' in SCRIPT
