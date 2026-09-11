#!/usr/bin/env bash
# Install the existing ROS/Python dependencies, build, and persist runtime settings.
set -eo pipefail
umask 077

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_mode=all
skip_deps=false
skip_build=false
check_only=false
while (($#)); do
    case "$1" in
        --mode)
            [[ $# -ge 2 ]] || { echo '--mode requires mock, real or all' >&2; exit 2; }
            install_mode=$2; shift 2 ;;
        --configure-only) skip_deps=true; skip_build=true; shift ;;
        --check) check_only=true; skip_deps=true; skip_build=true; shift ;;
        --skip-deps) skip_deps=true; shift ;;
        --skip-build) skip_build=true; shift ;;
        -h|--help)
            echo 'Usage: bash install.sh [--mode mock|real|all] [--configure-only|--check] [--skip-deps] [--skip-build]'
            echo 'Setup details and the four runtime commands: README.md, 실행 section.'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done
[[ $install_mode == mock || $install_mode == real || $install_mode == all ]] || {
    echo '--mode must be mock, real or all' >&2; exit 2;
}
[[ $EUID -ne 0 ]] || { echo 'Run as your normal account; sudo is used only for OS packages.' >&2; exit 2; }

if ! $skip_deps; then
    . /etc/os-release
    [[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || {
        echo 'Automatic dependency installation supports Ubuntu 24.04 / ROS 2 Jazzy.' >&2; exit 1;
    }
    # The ROS apt repository must already be configured by the ROS installation.
    sudo apt-get update
    sudo apt-get install -y ros-jazzy-ros-base python3-colcon-common-extensions \
        python3-rosdep python3-psycopg python3-yaml python3-pytest build-essential
    source /opt/ros/jazzy/setup.bash
    if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
        sudo rosdep init
    fi
    rosdep update --rosdistro jazzy
    rosdep install --from-paths "$project_root/Ros2UnityEndopoint_PKG/src" \
        "$project_root/Farino_AIO_Mock/src" "$project_root/ASSEMBLY_SEQUENCER/src" \
        --ignore-src --rosdistro jazzy -y
fi

if ! $skip_build; then
    [[ -f /opt/ros/jazzy/setup.bash ]] || { echo 'ROS 2 Jazzy setup is missing.' >&2; exit 1; }
    source /opt/ros/jazzy/setup.bash
    # Build message providers before consumers; preserve each existing workspace.
    for workspace in Ros2UnityEndopoint_PKG Farino_AIO_Mock ASSEMBLY_SEQUENCER; do
        (cd "$project_root/$workspace" && colcon build --symlink-install)
        source "$project_root/$workspace/install/local_setup.bash"
    done
fi

python3 - "$project_root" "$install_mode" "$check_only" "$skip_build" <<'PY'
import getpass
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

import psycopg

root = Path(sys.argv[1])
modes = ('mock', 'real') if sys.argv[2] == 'all' else (sys.argv[2],)
check_only = sys.argv[3] == 'true'
skip_build = sys.argv[4] == 'true'


def save_private(path, content):
    # Replace only after validation; an interrupted write cannot truncate credentials.
    fd, temporary = tempfile.mkstemp(prefix='.env.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


try:
    for mode in modes:
        path = root / 'launch' / ('.env.' + mode)
        config = {}
        if path.exists():
            if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
                raise ValueError(f'{path}: current-user ownership and chmod 600 are required')
            config = json.loads(path.read_text())
        keys = ['MAIN_SERVER_DB_DSN', 'PRODUCTION_DB_DSN', 'DEFECT_IMAGE_ROOT']
        if not isinstance(config, dict) or any(k not in keys or not isinstance(v, str) for k, v in config.items()):
            raise ValueError(f'{path}: invalid runtime environment')
        for key in keys:
            # Mode-specific inputs prevent accidentally copying the same generic DSN to both modes.
            value = os.environ.get(mode.upper() + '_' + key, config.get(key, ''))
            if not value and key == 'DEFECT_IMAGE_ROOT' and mode == 'mock':
                value = str(root / 'UnityDT/Assets/StreamingAssets')
            if not value and not check_only:
                if not sys.stdin.isatty() and not os.path.exists('/dev/tty'):
                    raise ValueError(f'{mode}: supply {mode.upper()}_{key}')
                value = getpass.getpass(f'{mode} {key} (hidden input): ').strip()
            if not value:
                raise ValueError(f'{mode}: {key} is missing')
            config[key] = value

        identities = []
        users = []
        for key, role in [('MAIN_SERVER_DB_DSN', 'job_submitter'), ('PRODUCTION_DB_DSN', 'production_writer')]:
            try:
                with psycopg.connect(config[key], connect_timeout=5, options='-c default_transaction_read_only=on') as conn:
                    conn.execute("SET statement_timeout = '5s'")
                    actual = conn.execute("""
                        SELECT split_part(setting, '=', 2)
                        FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase,
                             unnest(s.setconfig) AS setting
                        WHERE d.datname = current_database() AND s.setrole = 0
                          AND split_part(setting, '=', 1) = 'app.runtime_mode'
                    """).fetchone()
                    if not actual or actual[0] != mode:
                        raise ValueError(f'{mode}: {key} DB app.runtime_mode does not match')
                    allowed, superuser = conn.execute(
                        'SELECT pg_has_role(current_user, %s, \'USAGE\'), '
                        '(SELECT rolsuper FROM pg_roles WHERE rolname = current_user)', (role,)
                    ).fetchone()
                    if not allowed or superuser:
                        raise ValueError(f'{mode}: {key} requires a non-superuser account with {role}')
                    if not conn.execute("SELECT to_regclass('production.jobs')").fetchone()[0]:
                        raise ValueError(f'{mode}: production schema is missing')
                    users.append(conn.execute('SELECT current_user').fetchone()[0])
                    identities.append(conn.execute(
                        'SELECT current_database(), inet_server_addr()::text, inet_server_port()'
                    ).fetchone())
            except psycopg.Error as error:
                # Driver diagnostics may contain the supplied password/DSN.
                raise ValueError(f'{mode}: {key} validation failed ({type(error).__name__})') from None
        if identities[0] != identities[1]:
            raise ValueError(f'{mode}: MainServer and Sequencer must use the same DB server and database')
        if users[0] == users[1]:
            raise ValueError(f'{mode}: MainServer and Sequencer require separate login accounts')
        image_root = Path(config['DEFECT_IMAGE_ROOT'])
        if not image_root.is_absolute() or not image_root.is_dir():
            raise ValueError(f'{mode}: DEFECT_IMAGE_ROOT must be an existing absolute directory')
        if not os.access(image_root, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError(f'{mode}: DEFECT_IMAGE_ROOT requires read/write access')
        if not check_only:
            save_private(path, json.dumps(config, indent=2) + '\n')
        print(f'{mode}: DB mode, roles, shared storage and settings verified' + (' (read-only check)' if check_only else ' and saved'))

    if not check_only and not skip_build:
        bashrc = Path.home() / '.bashrc'
        if bashrc.is_symlink():
            raise ValueError('~/.bashrc is a symlink; add the README setup sources manually')
        text = bashrc.read_text() if bashrc.exists() else ''
        marker = '# Main_Unity ROS workspace: ' + str(root)
        if marker not in text:
            lines = [marker, 'source /opt/ros/jazzy/setup.bash']
            for workspace in ('Ros2UnityEndopoint_PKG', 'Farino_AIO_Mock', 'ASSEMBLY_SEQUENCER'):
                setup = shlex.quote(str(root / workspace / 'install/local_setup.bash'))
                lines.append(f'[ ! -f {setup} ] || source {setup}')
            with bashrc.open('a') as stream:
                stream.write('\n' + '\n'.join(lines) + '\n')
        print('ROS workspace loading registered in ~/.bashrc. Open a new terminal for runtime commands.')
except (ValueError, OSError, EOFError) as error:
    print(f'Setup incomplete: {error}', file=sys.stderr)
    sys.exit(1)
PY
