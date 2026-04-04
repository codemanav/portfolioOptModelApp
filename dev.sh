#! /bin/bash

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[0;33m'
blue='\033[0;34m'
magenta='\033[0;35m'
cyan='\033[0;36m'
clear='\033[0m'

echo -e "${yellow}Starting system${clear}"

echo -e "${yellow}Building apps${clear}"

nodemon -w . -e "py,js,html,css,txt" -x "docker compose build && docker compose up -d"