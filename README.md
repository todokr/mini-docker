# Mini docker
学習用のなんちゃってDocker

## セットアップ

### VMの作成と起動

```bash
$ vagrant up
$ vagrant ssh
```

```bash
$ sudo su -
# cat /etc/os-release
NAME="Ubuntu"
VERSION="20.10 (Groovy Gorilla)"
...
```

### syscall用のPythonラッパーライブラリのインストール

```bash
# cd /vagrant/libs
# python3 ./setup.py install

// インストールできているかの確認。linuxが出てくればOK
# pip3 list | grep linux
```

### Pythonライブラリのインストール

```bash
# cd /vagrant
# pipenv install --system
```

## コマンド
### Docker imageのpull

```bash
# ./bocker pull ubuntu

// or タグを指定
# ./bocker pull ubuntu:latest
```

### コンテナの起動

```bash
# ./bocker run ubuntu /bin/bash
```

#### 各種動作確認

##### hostとコンテナでPID名前空間が分離されている
コンテナから見ると、自身にPID = 1 が割り当てられている

*host (VM)*
```bash
# ps a
    PID TTY      STAT   TIME COMMAND
    698 tty1     Ss+    0:00 /sbin/agetty -o -p -- \u --noclear tty1 linux
  ...
  20414 pts/0    S      0:00 -bash
  20559 pts/0    S      0:00 /usr/bin/python3 ./bocker run --memory 100M ubuntu /bin/bash 
  ...
  20587 pts/1    R+     0:00 ps a
```

*container*
```bash
# ps a
    PID TTY      STAT   TIME COMMAND
      1 ?        S      0:00 /bin/bash
     24 ?        R+     0:00 ps a
```

##### hostとコンテナでUTS名前空間が分離されている

*host (VM)*
```bash
# hostname
vagrant
# hostname newhost
# hostname
newhost
```

*container*
```bash
# hostname
ubuntu_latest_e18ee394-791f-4df6-9833-2245f8fd5324
# hostname container
# hostname
container
```

*host (VM)*
```bash
# hostname
newhost
```

##### hostはコンテナのルートディレクトリ内を見られるが、コンテナは自身のルートディレクトリから外側を見ることができない

*host (VM)*
```bash
# touch /a.txt
# ls / | grep 'a.txt'
a.txt
```

*container*
```bash
# ls / | grep 'a.txt'
// nothing

# touch /b.txt
# ls / | grep 'b.txt'
b.txt
```

*host (VM)*
```bash
# ls /var/opt/app/container/ubuntu_latest_e18ee394-791f-4df6-9833-2245f8fd5324/cow_rw/ | grep 'b.txt'
b.txt
```

##### コンテナの最大CPU利用量を制限できる

*host (VM)*
```bash
// 1コアの25%までに制限
# ./bocker run --cpus 0.25 ubuntu /bin/bash
```

*host (VM - another terminal)*
```bash
// CPUの状況をグラフィカルに表示するかっこいいツールのインストール
# pip3 install s-tui
# s-tui
```

*container*
```bash
# yes > /dev/null
```

##### コンテナの最大メモリ利用量を制限できる

*host (VM)*
```bash
# ./bocker run --memory 100M ubuntu /bin/bash
```

*host (VM - another terminal)*
```bash
$ sudo su -
# htop -d 0.3 -p {pid}
```

*container*
```bash
# /dev/null < $(yes)
yes: standard output: Broken pipe
Killed
```

## 参考
- [Fewbytes/rubber-docker](https://github.com/Fewbytes/rubber-docker)
- [tonybaloney/mocker](https://github.com/tonybaloney/mocker)