""" Lesson0: 子プロセスを生成し、任意のコマンドを実行させる

$ python3 ./00_fork_exec.py run /bin/echo "hello from child process!"
"""

import click
import os
import traceback

@click.group()
def cli():
    pass

@cli.command(context_settings=dict(ignore_unknown_options=True,))
@click.argument('Command', required=True, nargs=-1)
def run(command):
    pid = os.fork()
    if pid == 0:
        try:
            os.execvp(command[0], command)
        except Exception:
            traceback.print_exc()
            os._exit(1)

    # 親プロセスは子プロセスの終了を待機する
    _, status = os.waitpid(pid, 0)
    print(f'{pid} exited with status {status}')

if __name__ == '__main__':
    cli()    