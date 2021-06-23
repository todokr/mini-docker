# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-20.10"
  # config.vm.network "forwarded_port", guest: 80, host: 8080

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine and only allow access
  # via 127.0.0.1 to disable public access
  # config.vm.network "forwarded_port", guest: 80, host: 8080, host_ip: "127.0.0.1"

  config.vm.provider "virtualbox" do |vb|
    vb.name = "vm-for-mini-docker"
    vb.gui = false
    vb.cpus = 2
    vb.memory = "1024"
  end
  
  config.vm.provision "shell", inline: <<-EOL
    apt update
    apt upgrade
    apt install -y python3-distutils python3-pip
    pip3 install pipenv
  EOL
end
