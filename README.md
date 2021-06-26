# Mini docker

## Setup

### start linux VM

```bash
$ vagrant up
$ vagrant ssh
```

### install syscall python wrapper lib

```bash
$ sudo su -
$ cd /vagrant
$ cd libs
$ python3 ./setup.py install

# make sure the wrapper lib be installed
$ pip3 list | grep
```

### install python libs

```bash
$ pipenv install --system
```

## Pulling docker image

```bash
$ cd /vagrant
$ ./bocker pull {image_name}
```

or

```bash
$ ./bocker pull {image_name}:{tag}
```
