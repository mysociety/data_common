#!/bin/bash 

curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -
echo "export PATH=\"$HOME/.poetry/bin:$PATH\"" > ~/.bashrc
export PATH="$HOME/.poetry/bin:$PATH" 
poetry config virtualenvs.create false


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

# get chromedriver
VERSION=$( curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$( google-chrome --version | awk '{print $NF}' | cut -d. -f1,2,3 ) )
wget -q https://chromedriver.storage.googleapis.com/${VERSION}/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
mv chromedriver /usr/bin/chromedriver
chown root:root /usr/bin/chromedriver
chmod +x /usr/bin/chromedriver
rm -f chromedriver_linux64.zip

apt-get update -y
apt-get install pandoc -y

# getfonts
mkdir /tmp/adodefont
cd /tmp/adodefont
mkdir -p ~/.fonts

wget https://github.com/adobe-fonts/source-code-pro/archive/2.030R-ro/1.050R-it.zip
unzip 1.050R-it.zip
cp source-code-pro-2.030R-ro-1.050R-it/OTF/*.otf ~/.fonts/

wget https://github.com/adobe-fonts/source-serif-pro/archive/2.000R.zip
unzip 2.000R.zip
cp source-serif-2.000R/OTF/*.otf ~/.fonts/

wget https://github.com/adobe-fonts/source-sans-pro/archive/2.020R-ro/1.075R-it.zip
unzip 1.075R-it.zip
cp source-sans-2.020R-ro-1.075R-it/OTF/*.otf ~/.fonts/

fc-cache -f -v

# add gh cli
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null
apt update
apt install gh
gh extension install ajparsons/gh-fix-submodule-remote
echo "gh extention installed"

# download ltex
cd /tmp/
echo "Downloading ltex"
wget https://github.com/valentjn/ltex-ls/releases/download/15.2.0/ltex-ls-15.2.0-linux-x64.tar.gz
echo "Untarring"
mkdir /ltex
tar -xf ltex-ls-15.2.0-linux-x64.tar.gz -C /ltex
echo "Removing source"
rm ltex-ls-15.2.0-linux-x64.tar.gz
echo "Finished ltex download"

