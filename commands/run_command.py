import stat
import os
import uuid
from dataclasses import dataclass
from typing import List

import commands.colors as colors
import linux

IMAGES_DIR = '/var/opt/app/images'
CONTAINER_DATA_DIR = '/var/opt/app/container'
CGROUP_CPU_DIR = '/sys/fs/cgroup/cpu'
CGROUP_MEMORY_DIR = '/sys/fs/cgroup/memory'

@dataclass(frozen=True)
class ContainerDir:
    root_dir: str
    rw_dir: str
    work_dir: str


def _init_container_dir(container_id: str) -> ContainerDir:
    root_dir = os.path.join(CONTAINER_DATA_DIR, container_id)
    rootfs_dir = os.path.join(root_dir, 'rootfs')
    rw_dir = os.path.join(root_dir, 'cow_rw')
    work_dir = os.path.join(root_dir, 'cow_workdir')

    for d in (rootfs_dir, rw_dir, work_dir):
        if not os.path.exists(d):
            os.makedirs(d)

    return ContainerDir(root_dir=root_dir, rw_dir=rw_dir, work_dir=work_dir)


def _exec_container(
        image: str,
        tag: str,
        container_id: str,
        container_dir: ContainerDir,
        cpus: float,
        memory: str,
        command: List[str]):
    try:
        # コンテナの最大CPU利用量を制限
        # See: https://gihyo.jp/admin/serial/01/linux_containers/0004?page=2
        container_cpu_cgroup_dir = os.path.join(CGROUP_CPU_DIR, 'bocker', container_id)
        if not os.path.exists(container_cpu_cgroup_dir):
            os.makedirs(container_cpu_cgroup_dir)
        cpu_task_file = os.path.join(container_cpu_cgroup_dir, 'tasks')
        open(cpu_task_file, 'w').write(str(os.getpid()))
        if cpus is not None:
            cpu_period_file = os.path.join(container_cpu_cgroup_dir, 'cpu.cfs_period_us')
            period_us = int(open(cpu_period_file).read())
            cpu_quota_file = os.path.join(container_cpu_cgroup_dir, 'cpu.cfs_quota_us')
            open(cpu_quota_file, 'w').write(str(int(period_us * cpus)))

        # コンテナの最大メモリ利用量を制限
        # See: https://gihyo.jp/admin/serial/01/linux_containers/0005
        container_memory_cgroup_dir = os.path.join(CGROUP_MEMORY_DIR, 'bocker', container_id)
        if not os.path.exists(container_memory_cgroup_dir):
            os.makedirs(container_memory_cgroup_dir)
        memory_tasks_file = os.path.join(container_memory_cgroup_dir, 'tasks')
        open(memory_tasks_file, 'w').write(str(os.getpid()))

        if memory is not None:
            mem_limit_file = os.path.join(container_memory_cgroup_dir, 'memory.limit_in_bytes')
            memsw_linit_file = os.path.join(container_memory_cgroup_dir, 'memory.memsw.limit_in_bytes')  # swapをさせない
            for f in (mem_limit_file, memsw_linit_file):
                open(f, 'w').write(str(memory))

        # コンテナにホスト名をセット
        linux.sethostname(container_id)

        # ルートディレクトリをプライベートにマウント
        # See: https://kernhack.hatenablog.com/entry/2015/05/30/115705
        print('mounting / privately')
        linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, '')

        # docker image ディレクトリを overlayfs としてマウント
        # See: https://gihyo.jp/admin/serial/01/linux_containers/0018
        print('mounting docker image directory')
        image_path = os.path.join(IMAGES_DIR, f'library_{image}_{tag}')
        image_root = os.path.join(image_path, 'layers/contents')
        linux.mount(
            'overlay',
            container_dir.root_dir,
            'overlay',
            linux.MS_NODEV,
            f"lowerdir={image_root},upperdir={container_dir.rw_dir},workdir={container_dir.work_dir}"
        )

        # proc, sys, dev の linux システムディレクトリの作成
        proc_dir = os.path.join(container_dir.root_dir, 'proc') # proc: PIDなどプロセスの情報
        sys_dir = os.path.join(container_dir.root_dir, 'sys')   # sys: ドライバ関連のプロセスの情報
        dev_dir = os.path.join(container_dir.root_dir, 'dev')   # dev: CPUやメモリなど基本デバイス
        for d in (proc_dir, sys_dir, dev_dir):
            if not os.path.exists(d):
                os.makedirs(d)

        # システムディレクトリのマウント
        print('mounting /proc, /sys, /dev, /dev/pts')
        linux.mount('proc', proc_dir, 'proc', 0, '')
        linux.mount('sysfs', sys_dir, 'sysfs', 0, '')
        linux.mount('tmpfs', dev_dir, 'tmpfs', linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

        print('mounting devices')
        for i, dev in enumerate(['stdin', 'stdout', 'stderror']):
            os.symlink(f'/proc/self/fd/{i}', os.path.join(dev_dir, dev))
        devices = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
                   'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1, 9),
                   'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
                   'full': (stat.S_IFCHR, 1, 7)}
        for device, (dev_type, major, minor) in devices.items():
            os.mknod(os.path.join(dev_dir, device), 0o666 | dev_type, os.makedev(major, minor))

        # コンテナのルートディレクトリを変更
        print('changing container root directory')
        old_root = os.path.join(container_dir.root_dir, 'old_root')
        os.makedirs(old_root)
        linux.pivot_root(container_dir.root_dir, old_root)
        os.chdir('/')
        linux.umount2('/old_root', linux.MNT_DETACH)
        os.rmdir('/old_root')

        print(f'🏃️💨 {colors.GREEN}Docker container {container_id} started! executing {command[0]}{colors.END}')
        os.execvp(command[0], command)

    except Exception as e:
        print(f'{colors.RED}{e}{colors.END}')
        os._exit(1)


def run_run(image: str, tag: str, cpus: float, memory: str, command: List[str]):
    print(f'Start running {image}:{tag} ...')
    print(f'cpus={cpus}, memory={memory}')

    id = uuid.uuid4()
    container_id = f'{image}_{tag}_{id}'
    container_dir = _init_container_dir(container_id)

    # 分離させる名前空間のフラグ
    # See: https://gihyo.jp/admin/serial/01/linux_containers/0002
    flags = (
        linux.CLONE_NEWPID | # PID名前空間: プロセスIDの分離。異なる名前空間同士では、同一のプロセスIDを持つことが可能になる
        linux.CLONE_NEWUTS | # UTS名前空間: ホスト名, ドメイン名の分離
        linux.CLONE_NEWNS  | # マウント名前空間: ファイルシステムのマウントポイントの分離
        linux.CLONE_NEWNET   # ネットワーク名前空間: ネットワークデバイス, ポート, ルーティングテーブル, ソケットなどの分離
    )

    # 子プロセスを作成。コンテナとして立ち上げる
    # See: https://linuxjm.osdn.jp/html/LDP_man-pages/man2/clone.2.html
    pid = linux.clone(_exec_container, flags, (image, tag, container_id, container_dir, cpus, memory, command))
    print(f'container process ID: {pid}')

    _, status = os.waitpid(pid, 0)
    print(f'{pid} exited with status {status}')
