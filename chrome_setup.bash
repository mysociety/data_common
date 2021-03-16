#!/bin/bash 

curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - \
      && echo 'deb https://deb.nodesource.com/node_14.x buster main' > /etc/apt/sources.list.d/nodesource.list

curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - \
      && echo 'deb https://deb.nodesource.com/node_14.x buster main' > /etc/apt/sources.list.d/nodesource.list

curl -s https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
      && echo 'deb http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list

apt-get -qq update \
      && apt-get -qq install \
            google-chrome-stable \
      && rm -rf /var/lib/apt/lists/*

VERSION=$( curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$( google-chrome --version | awk '{print $NF}' | cut -d. -f1,2,3 ) )
wget -q https://chromedriver.storage.googleapis.com/${VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/bin/chromedriver
chown root:root /usr/bin/chromedriver
chmod +x /usr/bin/chromedriver
rm -f chromedriver_linux64.zip
