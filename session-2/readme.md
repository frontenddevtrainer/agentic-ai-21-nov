python3.13 -m venv venv  

mac / linux
source venv/bin/activate 

windows
venv\Scripts\activate

.\venv\Scripts\Activate.ps1

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned


To update requirements.txt 
pip freeze > requirements.txt

Install packages based on the requirements file 
pip install -r requirements.txt  