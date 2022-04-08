from colorama import Fore
from os import system
from os.path import isfile
from platform import system as osType
from cryptography.fernet import Fernet
def rgb(r, g, b):
    return "\033[38;2;{};{};{}m".format(r, g, b)
def clear():
    if "windows"in osType().lower():
        system("cls")
    else :
        system("clear")
def wr():
    print(f"{Fore.LIGHTRED_EX}Enter the data : {Fore.RESET}")
    data=''
    sen='1'
    while sen.strip():
        sen=input(f"{Fore.LIGHTCYAN_EX}>{Fore.RESET}")+"\n"
        data+=sen
    if input(f"{Fore.LIGHTYELLOW_EX}Do you want the data to be encrypted [Y/n] : {Fore.RESET}").lower() == 'y':
        key=Fernet.generate_key()
        while 1:
            if input(f"{Fore.LIGHTBLUE_EX}\nYour decryption key is {key.decode()}\n\nStore it in a safe place\n\ndo you accept [Y/n]?{Fore.RESET}").lower()=='y':
                break
        ferObj=Fernet(key)
        data=ferObj.encrypt(data.encode()).decode()
    fileName=input(f"{Fore.LIGHTCYAN_EX}\nEnter the image file name ({Fore.LIGHTRED_EX}Only png files are supported{Fore.LIGHTCYAN_EX}): {Fore.RESET}")
    outName=input(f"{Fore.LIGHTMAGENTA_EX}\nEnter the name of the output image file : ")
    if isfile(fileName):
        with open(fileName,"rb") as f:
            out=open(outName,"wb")
            out.write(f.read()+data.strip().encode())
            out.close()
    else:
        input(f"{Fore.LIGHTRED_EX}File not found : {fileName}\n\nEnter to continue : {Fore.RESET}")
def rd():
    fileName=input(f"{Fore.LIGHTCYAN_EX}\nEnter the image file name ({Fore.LIGHTRED_EX}Only png files are supported{Fore.LIGHTCYAN_EX}): {Fore.RESET}")    
    ferObj=False
    if input(f"{Fore.LIGHTBLUE_EX}Is the data encrypted ?[Y/n] {Fore.RESET}").lower()=="y":
        key=input(f"{Fore.LIGHTMAGENTA_EX}Enter the key : {Fore.RESET}").encode()
        try:
            ferObj=Fernet(key)
        except:
            print(f"{Fore.LIGHTRED_EX}Something is wrong, please check the decryption key.{Fore.RESET}")

    with open(fileName,"rb") as f:
        data = f.read().split(b'IEND\xaeB`\x82')[1].decode('utf-8')
    if ferObj:
        data=ferObj.decrypt(data.encode()).decode()
    input(f"{Fore.LIGHTYELLOW_EX}\n{data}\nEnter to return main menu : {Fore.RESET}")
def banner():
    clear()
    banner=r"""


{}     _/|       |\_								         _/|       |\_
    /  |       |  \								        /  |       |  \
{}   |    \     /    |  @@@@@@@   @@@  @@@   @@@@@@   @@@@@@@@  @@@  @@@  @@@  @@@  @@@  |    \     /    |
   |  \ /     \ /  |  @@@@@@@@  @@@  @@@  @@@@@@@@  @@@@@@@@  @@@@ @@@  @@@  @@@  @@@  |    \     /    |
{}   | \  |     |  / |  @@!  @@@  @@!  @@@  @@!  @@@  @@!       @@!@!@@@  @@!  @@!  !@@  | \  |     |  / |  
   | \ _\_/^\_/_ / |  !@!  @!@  !@!  @!@  !@!  @!@  !@!       !@!!@!@!  !@!  !@!  @!!  | \ _\_/^\_/_ / |  
{}   |    --\//--    |  @!@@!@!   @!@!@!@!  @!@  !@!  @!!!:!    @!@ !!@!  !!@   !@@!@!   |    --\//--    |
    \_  \     /  _/   !!@!!!    !!!@!!!!  !@!  !!!  !!!!!:    !@!  !!!  !!!    @!!!     \_  \     /  _/
{}      \__    __/      !!:       !!:  !!!  !!:  !!!  !!:       !!:  !!!  !!:   !: :!!	  \__  |  __/
         \ _ /	      :!:       :!:  !:!  :!:  !:!  :!:       :!:  !:!  :!:  :!:  !:!        \ _ /
{}        _/   \_        ::       ::   :::  ::::: ::   :: ::::   ::   ::   ::   ::  :::       _/   \_
       / _/|\_ \       :         :   : :   : :  :   : :: ::   ::    :   :     :   ::       / _/|\_ \
{}        /  |  \  									    /  |  \  
         / ࿕ \										     / ࿕ \

                    [ 1 ] Bind data to image                [ 2 ] Read data from an image

                    [ 3 ] Developer information             [ 4 ] Exit

Enter your selection : """.format(rgb(   116, 0, 0  ),rgb(   143, 0, 0   ),rgb(   178, 0, 0  ),rgb(  187, 0, 0  ),rgb( 201, 0, 0 ),rgb(  209, 0, 0   ),rgb(  255, 0, 0 ))
    return banner
def main():
    while 1 :
        selection=input(banner())
        if selection=='1':
            try:
                wr()
            except KeyboardInterrupt:
                pass
        elif selection=="2":
            try:
                rd()
            except KeyboardInterrupt:
                pass
        elif selection=="3":
            clear()
            try:
                print(Fore.LIGHTYELLOW_EX , """
      _---~~(~~-_.
    _{        )   )         
  ,   ) -~~- ( ,-' )_       Hi, I'm Mani
 (  `-,_..`., )-- '_,)      You can get my complete information from this site:
( ` _)  (  -~( -_ `,  }     https://adolfmacro.github.io/mani/
(_-  _  ~_-~~~~`,  ,' )     
  `~ -^(    __;-,((()))     My GitHub Address: https://github.com/adolfmacro
        ~~~~ {_ -_(())      E-mail : m4nikamran@gmail.com
               `\  }        Telegram : https://t.me/manikamran
                 { }      """)
                input(f"\n\n    Enter to exit : {Fore.RESET}")
            except KeyboardInterrupt:
                pass
        elif selection=="4":
            exit()
if __name__=="__main__"    :
    try:
        main()
    except KeyboardInterrupt:
        exit()