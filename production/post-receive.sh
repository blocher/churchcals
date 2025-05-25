#!/bin/sh

echo "======Setting File Ownership======"
sudo chmod o+x /var
sudo chmod o+x /var/www
sudo chmod o+x /var/www/saints.benlocher.com
sudo chmod o+x /var/www/saints.benlocher.com/site
sudo chown -R saints:saints /var/www/saints.benlocher.com
sudo chmod -R 755 /var/www/saints.benlocher.com

echo "======Making Directory======"
mkdir -p /var/www/saints.benlocher.com/
cd /var/www/saints.benlocher.com/

echo "======Checking out code======"
git --work-tree=/var/www/saints.benlocher.com --git-dir=/var/repo/saints.benlocher.com/ checkout -f master

echo "======Setting File Ownership======"
sudo chmod o+x /var
sudo chmod o+x /var/www
sudo chmod o+x /var/www/saints.benlocher.com
sudo chmod o+x /var/www/saints.benlocher.com/site
sudo chown -R saints:saints /var/www/saints.benlocher.com
sudo chmod -R 755 /var/www/saints.benlocher.com

echo "======Setting Up Log File====="
sudo mkdir -p /home/saints/logs
sudo touch /home/saints/logs/gunicorn.log
sudo chown -R saints:saints /home/saints/logs
sudo chmod 755 /home/saints/logs
sudo chmod 644 /home/saints/logs/gunicorn.log

echo "======Making and activating venv======"
sudo rm -rf env
python3.13 -m venv env
. env/bin/activate
cd site

echo "======Installing Requirements======"
pip install -r requirements.txt --no-cache-dir

echo "======Migrating Database======"
python3.13 manage.py migrate --no-input

echo "======Collecting Static Files======"
python3.13 manage.py collectstatic --noinput --clear

echo "======Clearing Python Cache======"
sudo find . -name "*.pyc" -exec rm -f {} \;
sudo find . -name "*.pyo" -exec rm -f {} \;

echo "======Restarting Nginx======"
sudo nginx -t && sudo systemctl reload nginx

echo "======Restarting Uvicorn with Systemctl======"
systemctl stop saints
systemctl start saints
# systemctl status saints

echo "======Clearing Python Cache and Recompiling======"
sudo find . -name "*.pyc" -exec rm -f {} \;
sudo find . -name "*.pyo" -exec rm -f {} \;
python -m compileall .
