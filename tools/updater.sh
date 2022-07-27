crd=pwd
cd /tmp/
git clone https://github.com/AdolfMacro/phoenix.git
sudo -u root cp -R phoenix/* /usr/src/phoenix/
sudo -u root rm -rf phoenix
cd $prc