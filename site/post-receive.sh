#!/bin/sh

echo "======Making Directory======"
mkdir -p /var/www/saints.benlocher.com
cd /var/www/saints.benlocher.com

echo "======Checking out code======"
git --work-tree=/var/www/saints.benlocher.com --git-dir=/var/repo/saints.benlocher.com/ checkout -f master

echo "======Making and activating venv======"
sudo rm -rf env
python3.13 -m venv env
. env/bin/activate
cd site

echo "======Installing Requirements======"
pip install -r requirements.txt --no-cache-dir

echo "======Installing Yarn Requirements and updating browserslist======"
rm -rf node_modules
npm install

echo "======Migrating Database======"
python3.13 manage.py migrate --no-input

echo "======Collecting Static Files======"
python3.13 manage.py collectstatic --noinput --clear

echo "======Clearing Python Cache======"
sudo find . -name "*.pyc" -exec rm -f {} \;
sudo find . -name "*.pyo" -exec rm -f {} \;

echo "======Restarting Uvicorn with Systemctl======"
systemctl stop dailyoffice
systemctl start dailyoffice
# systemctl status dailyoffice

echo "======Clearing Python Cache and Recompiling======"
sudo find . -name "*.pyc" -exec rm -f {} \;
sudo find . -name "*.pyo" -exec rm -f {} \;
python -m compileall .
