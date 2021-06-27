"""
TODO
- cgroups を利用して、コンテナが使用する CPU/メモリ を隔離・制限する
- コンテナのプロセスの uid を変更する
"""

import json
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
    cpus: int,
    memory: str,
    command: List[str]):

    # cgroup でコンテナが利用できるリソースに制限を加える
    #container_cgroup_cpu_dir = os.path.join(
    #    CGROUP_CPU_DIR,
    #    'bocker',
    #    container_id
    #)
    # if not os.path.exists(container_cgroup_cpu_dir):
        # os.makedirs(container_cgroup_cpu_dir)
    # task_file = os.path.join(container_cgroup_cpu_dir, 'tasks')
    # open(task_file, 'w').write(str(os.getpid()))

    # コンテナに対してメモリの制限を行う
    # See: https://gihyo.jp/admin/serial/01/linux_containers/0005
    container_memory_cgroup_dir = os.path.join(CGROUP_MEMORY_DIR, 'bocker', container_id)
    if not os.path.exists(container_memory_cgroup_dir):
        os.makedirs(container_memory_cgroup_dir)
    memory_tasks_file = os.path.join(container_memory_cgroup_dir, 'tasks')
    open(memory_tasks_file, 'w').write(str(os.getpid()))

    if memory is not None:
        mem_limit_file = os.path.join(container_memory_cgroup_dir, 'memory.limit_in_bytes')
        memsw_linit_file = os.path.join(container_memory_cgroup_dir, 'memory.memsw.limit_in_bytes') # swapをさせない
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
    sys_dir  = os.path.join(container_dir.root_dir, 'sys') # sys: ドライバ関連のプロセスの情報
    dev_dir  = os.path.join(container_dir.root_dir, 'dev') # dev: CPUやメモリなど基本デバイス
    for d in (proc_dir, sys_dir, dev_dir):
        if not os.path.exists(d):
            os.makedirs(d)

    # システムディレクトリのマウント
    print('mounting /proc')
    linux.mount('proc', proc_dir, 'proc', 0, '')
    print('mounting /sys')
    linux.mount('sysfs', sys_dir, 'sysfs', 0, '')
    print('mounting /dev')
    linux.mount('tmpfs', dev_dir, 'tmpfs', 0, '')

    # コンテナのルートディレクトリを変更
    old_root = os.path.join(container_dir.root_dir, 'old_root')
    os.makedirs(old_root)
    linux.pivot_root(container_dir.root_dir, old_root)
    os.chdir('/')
    linux.umount2('/old_root', linux.MNT_DETACH)
    os.rmdir('/old_root')

    print(f'👌 {colors.GREEN}Docker container {container_id} started! executing {command[0]}{colors.END}')
    os.execvp(command[0], command)

def run_run(image: str, tag: str, cpus: int, memory: str, command: List[str]):
    print(f'Start running {image}:{tag} ...')
    print(f'Resource: cpus={cpus}, memory={memory}')

    id = uuid.uuid4()
    container_id = f'{image}_{tag}_{id}'
    container_dir = _init_container_dir(container_id)

    flags = (
        linux.CLONE_NEWPID | # PID名前空間: プロセスIDの分離。異なる名前空間同士では、同一のプロセスIDを持つことが可能になる
        linux.CLONE_NEWUTS | # UTS名前空間: ホスト名, ドメイン名の分離 
        linux.CLONE_NEWNS  | # マウント名前空間: マウントの集合, 操作。ファイルシステムのマウントポイントを分離する。Namespace 内の mount / umount が他の Namespace に影響を与えないようにする
        linux.CLONE_NEWNET   # ネットワーク名前空間: ネットワークデバイス, ポート, ルーティングテーブル, ソケットなどの分離
    )
    
    # 子プロセスを作成。コンテナとして立ち上げる
    pid = linux.clone(_exec_container, flags, (image, tag, container_id, container_dir, cpus, memory, command))
    print(f'container process ID: {pid}')

    _, status = os.waitpid(pid, 0)
    print(f'{pid} exited with status {status}')