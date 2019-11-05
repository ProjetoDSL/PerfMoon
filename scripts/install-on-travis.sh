#!/bin/bash -e

export DEBIAN_FRONTEND=noninteractive

# Update apt-get's package lists.
sudo apt-get update -qq

# Use apt-get to install the PerfMoon webserver and mod_wsgi.
sudo apt-get install --yes apache2-mpm-prefork libapache2-mod-wsgi
