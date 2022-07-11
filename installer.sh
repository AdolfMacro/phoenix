echo -E """
         ___           _        _ _           
        |_ _|_ __  ___| |_ __ _| | | ___ _ __ 
         | || '_ \/ __| __/ _\` | | |/ _ \ '__|
         | || | | \__ \ || (_| | | |  __/ |   
        |___|_| |_|___/\__\__,_|_|_|\___|_|
        _____________________________________
    Installer for phoenix tool , Start installation
    
"""
pip install colorama
pip install cryptography

sudo -u root mkdir /usr/src/phoenix/
line="$0"
replace="/installer.sh"
replacewith=""
temp=$( realpath "$0"  )
line=$(dirname "$temp")
replace="/tools"
replacewith=""
line="${line/${replace}/${replacewith}}"
echo $line
sudo -u root cp -R $line/* /usr/src/phoenix/
sudo sh -c 'echo "python3 /usr/src/phoenix/main.py \$1" > /usr/local/bin/phoenix'
sudo -u root chmod +x /usr/local/bin/phoenix
echo """
██████╗  ██████╗ ███╗   ██╗███████╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝
██║  ██║██║   ██║██╔██╗ ██║█████╗  
██║  ██║██║   ██║██║╚██╗██║██╔══╝  
██████╔╝╚██████╔╝██║ ╚████║███████╗
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚══════╝
"""
