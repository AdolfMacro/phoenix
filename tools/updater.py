from colorama import Fore
from os.path import isfile
from requests import get
from os import system , chdir
def mainUpdater():
    UPtDATE=None
    vsersionNum=get("https://raw.githubusercontent.com/AdolfMacro/phoenix/main/VERSION.txt").text
    if not vsersionNum==open(f'{__file__.replace("tools/updater.py","")}VERSION.txt','r').read():
        UPtDATE=False
    else :
        UPtDATE=True
    if isfile("/usr/src/phoenix/VERSION.txt"):
        if UPtDATE:
            input(f"{Fore.LIGHTGREEN_EX}Your version is up to date!\n\nEnter to continue : {Fore.RESET}")
            return
        WtUpDate=input(f"{Fore.LIGHTRED_EX}Your version is not up to date!\n\nDo you want to be updated [y/n]? : {Fore.RESET}").lower()
        if WtUpDate=='y':
            chdir(__file__.replace("updater.py",""))
            system("bash updater.sh")
        else :
            input(f"{Fore.LIGHTCYAN_EX}\n\nEnter to continue : {Fore.RESET}")
    else :
        upErr=input(f"""{Fore.LIGHTRED_EX}Error: You did not install the tool! \nIf you are using Linux based systems, please install the tool with the tools/installer.sh file, or download the update manually.
    \nDo you want to check the version of your tool [y/n] ? {Fore.RESET}""").lower()
        if upErr=='y':
            if UPtDATE:
                input(f"{Fore.LIGHTGREEN_EX}Your version is up to date!\n\nEnter to continue : {Fore.RESET}")
            else :
                input(f"{Fore.LIGHTRED_EX}Your version is not up to date!\n\nEnter to continue : {Fore.RESET}")
